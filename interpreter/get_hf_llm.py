import os
import sys
import wget
import appdirs
import inquirer
import subprocess
import contextlib
from rich import print
from rich.markdown import Markdown
import os
import inquirer
from huggingface_hub import list_files_info, hf_hub_download


def get_hf_llm(repo_id):

    if "TheBloke/CodeLlama-" not in repo_id:
      # ^ This means it was prob through the old --local, so we have already displayed this message.
      print('', Markdown(f"**Open Interpreter** will use `{repo_id}` for local execution. Use your arrow keys to set up the model."), '')

    raw_models = list_gguf_files(repo_id)
    
    if not raw_models:
        print(f"Failed. Are you sure there are GGUF files in `{repo_id}`?")
        return None

    combined_models = group_and_combine_splits(raw_models)

    # Display to user
    choices = [format_quality_choice(model) for model in combined_models]
    questions = [inquirer.List('selected_model', message="Quality (lower is faster, higher is more capable)", choices=choices)]
    answers = inquirer.prompt(questions)
    for model in combined_models:
        if format_quality_choice(model) == answers["selected_model"]:
            filename = model["filename"]
            break

    # Third stage: GPU confirm
    if confirm_action("Use GPU? (Large models might crash on GPU, but will run more quickly)"):
      n_gpu_layers = -1
    else:
      n_gpu_layers = 0

    # Get user data directory
    user_data_dir = appdirs.user_data_dir("Open Interpreter")
    default_path = os.path.join(user_data_dir, "models")

    # Ensure the directory exists
    os.makedirs(default_path, exist_ok=True)

    # Define the directories to check
    directories_to_check = [
        default_path,
        "llama.cpp/models/",
        os.path.expanduser("~") + "/llama.cpp/models/",
        "/"
    ]

    # Check for the file in each directory
    for directory in directories_to_check:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            model_path = path
            break
    else:
        # If the file was not found, ask for confirmation to download it
        download_path = os.path.join(default_path, filename)
      
        print("This language model was not found on your system.")
        message = f"Would you like to download it to {default_path}?"
        
        if confirm_action(message):
          
            # Check if model was originally split
            split_files = [model["filename"] for model in raw_models if selected_model in model["filename"]]
            
            if len(split_files) > 1:
                # Download splits
                for split_file in split_files:
                    hf_hub_download(repo_id=repo_id, filename=split_file)
                
                # Combine and delete splits
                actually_combine_files(selected_model, split_files)
            else:
                hf_hub_download(repo_id=repo_id, filename=selected_model)
        
        else:
            print('\n', "Download cancelled. Exiting.", '\n')
            return None

    # This is helpful for folks looking to delete corrupted ones and such
    print(f"Model found at {download_path}")
  
    try:
        from llama_cpp import Llama
    except:
        # Ask for confirmation to install the required pip package
        message = "Local LLM interface package not found. Install `llama-cpp-python`?"
        if confirm_action(message):
            
            # We're going to build llama-cpp-python correctly for the system we're on

            import platform
            
            def check_command(command):
                try:
                    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    return True
                except subprocess.CalledProcessError:
                    return False
                except FileNotFoundError:
                    return False
            
            def install_llama(backend):
                env_vars = {
                    "FORCE_CMAKE": "1"
                }
                
                if backend == "cuBLAS":
                    env_vars["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
                elif backend == "hipBLAS":
                    env_vars["CMAKE_ARGS"] = "-DLLAMA_HIPBLAS=on"
                elif backend == "Metal":
                    env_vars["CMAKE_ARGS"] = "-DLLAMA_METAL=on"
                else:  # Default to OpenBLAS
                    env_vars["CMAKE_ARGS"] = "-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS"
                
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", "llama-cpp-python"], env=env_vars, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error during installation with {backend}: {e}")
            
            def supports_metal():
                # Check for macOS version
                if platform.system() == "Darwin":
                    mac_version = tuple(map(int, platform.mac_ver()[0].split('.')))
                    # Metal requires macOS 10.11 or later
                    if mac_version >= (10, 11):
                        return True
                return False
            
            # Check system capabilities
            if check_command(["nvidia-smi"]):
                install_llama("cuBLAS")
            elif check_command(["rocminfo"]):
                install_llama("hipBLAS")
            elif supports_metal():
                install_llama("Metal")
            else:
                install_llama("OpenBLAS")
          
            from llama_cpp import Llama
            print('', Markdown("Finished downloading `Code-Llama` interface."), '')

            # Tell them if their architecture won't work well

            # Check if on macOS
            if platform.system() == "Darwin":
                # Check if it's Apple Silicon
                if platform.machine() == "arm64":
                    # Check if Python is running under 'arm64' architecture
                    if platform.architecture()[0] != "arm64":
                        print("Warning: You are using Apple Silicon (M1) Mac but your Python is not of 'arm64' architecture.")
                        print("The llama.ccp x86 version will be 10x slower on Apple Silicon (M1) Mac.")
                        print("\nTo install the correct version of Python that supports 'arm64' architecture:")
                        print("1. Download Miniforge for M1:")
                        print("wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh")
                        print("2. Install it:")
                        print("bash Miniforge3-MacOSX-arm64.sh")
                        print("")
      
        else:
            print('', "Installation cancelled. Exiting.", '')
            return None

    # Initialize and return Code-Llama
    llama_2 = Llama(model_path=model_path, n_gpu_layers=n_gpu_layers, verbose=False, n_ctx=1800) # n_ctx = context window. smaller is faster
      
    return llama_2

def confirm_action(message):
    question = [
        inquirer.Confirm('confirm',
                         message=message,
                         default=True),
    ]

    answers = inquirer.prompt(question)
    return answers['confirm']






import os
import inquirer
from huggingface_hub import list_files_info, hf_hub_download
from typing import Dict, List, Union

def list_gguf_files(repo_id: str) -> List[Dict[str, Union[str, float]]]:
    """
    Fetch all files from a given repository on Hugging Face Model Hub that contain 'gguf'.

    :param repo_id: Repository ID on Hugging Face Model Hub.
    :return: A list of dictionaries, each dictionary containing filename, size, and RAM usage of a model.
    """
    files_info = list_files_info(repo_id=repo_id)
    gguf_files = [file for file in files_info if "gguf" in file.rfilename]

    # Prepare the result
    result = []
    for file in gguf_files:
        size_in_gb = file.size / (1024**3)
        filename = file.rfilename
        result.append({
            "filename": filename,
            "Size": size_in_gb,
            "RAM": size_in_gb + 2.5,
        })

    return result

def group_and_combine_splits(models: List[Dict[str, Union[str, float]]]) -> List[Dict[str, Union[str, float]]]:
    """
    Groups filenames based on their base names and combines the sizes and RAM requirements.

    :param models: List of model details.
    :return: A list of combined model details.
    """
    grouped_files = {}
    for model in models:
        base_name = model["filename"].split('-split-')[0]
        if base_name in grouped_files:
            grouped_files[base_name]["Size"] += model["Size"]
            grouped_files[base_name]["RAM"] += model["Size"]
        else:
            grouped_files[base_name] = model

    return list(grouped_files.values())

def actually_combine_files(base_name: str, files: List[str]) -> None:
    """
    Combines files together and deletes the original split files.

    :param base_name: The base name for the combined file.
    :param files: List of files to be combined.
    """
    files.sort()    
    with open(base_name, 'wb') as outfile:
        for file in files:
            with open(file, 'rb') as infile:
                outfile.write(infile.read())
            os.remove(file)

def format_quality_choice(model: Dict[str, Union[str, float]]) -> str:
    """
    Formats the model choice for display in the inquirer prompt.
    """
    return f"{model['filename']} | Size: {model['Size']:.1f} GB, RAM usage: {model['RAM']:.1f} GB"

