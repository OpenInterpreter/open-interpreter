import os
import sys
import appdirs
import inquirer
import subprocess
import contextlib
from rich import print
from rich.markdown import Markdown


def get_llama_2_instance():

    # First, we ask them which model they want to use.
    print('', Markdown("**Open Interpreter** will use `Code Llama` for local execution.\n\nUse your arrow keys then press `enter` to set up the model."), '')
        
    models = {
        '7B': {
            'Low': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q2_K.gguf', 'Size': '3.01 GB', 'RAM': '5.51 GB'},
            'Medium': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/blob/main/codellama-7b.Q4_K_M.gguf', 'Size': '4.24 GB', 'RAM': '6.74 GB'},
            'High': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q8_0.gguf', 'Size': '7.16 GB', 'RAM': '9.66 GB'}
        },
        '16B': {
            'Low': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-13B-GGUF/resolve/main/codellama-13b.Q2_K.gguf', 'Size': '5.66 GB', 'RAM': '8.16 GB'},
            'Medium': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-13B-GGUF/resolve/main/codellama-13b.Q4_K_M.gguf', 'Size': '8.06 GB', 'RAM': '10.56 GB'},
            'High': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-13B-GGUF/resolve/main/codellama-13b.Q8_0.gguf', 'Size': '13.83 GB', 'RAM': '16.33 GB'}
        },
        '34B': {
            'Low': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-34B-GGUF/resolve/main/codellama-34b.Q2_K.gguf', 'Size': '14.21 GB', 'RAM': '16.71 GB'},
            'Medium': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-34B-GGUF/resolve/main/codellama-34b.Q4_K_M.gguf', 'Size': '20.22 GB', 'RAM': '22.72 GB'},
            'High': {'URL': 'https://huggingface.co/TheBloke/CodeLlama-34B-GGUF/resolve/main/codellama-34b.Q8_0.gguf', 'Size': '35.79 GB', 'RAM': '38.29 GB'}
        }
    }
    
    # First stage: Select parameter size
    parameter_choices = list(models.keys())
    questions = [inquirer.List('param', message="Parameter count (smaller is faster, larger is more capable)", choices=parameter_choices)]
    answers = inquirer.prompt(questions)
    chosen_param = answers['param']
    
    # Second stage: Select quality level
    def format_quality_choice(quality, model):
        return f"{quality} | Size: {model['Size']}, RAM usage: {model['RAM']}"
    quality_choices = [format_quality_choice(quality, models[chosen_param][quality]) for quality in models[chosen_param]]
  
    questions = [inquirer.List('quality', message="Quality (lower is faster, higher is more capable)", choices=quality_choices)]
    answers = inquirer.prompt(questions)
    chosen_quality = answers['quality'].split(' ')[0]  # Extracting the 'small', 'medium', or 'large' from the selected choice

    # Get the URL based on choices 
    url = models[chosen_param][chosen_quality]['URL']
    file_name = url.split("/")[-1]

    # Get user data directory
    user_data_dir = appdirs.user_data_dir("open-interpreter")
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
        path = os.path.join(directory, file_name)
        if os.path.exists(path):
            model_path = path
            break
    else:
        # If the file was not found, ask for confirmation to download it
        download_path = os.path.join(default_path, file_name)
        message = f"This instance of `Llama-2` was not found. Would you like to download it to `{download_path}`?"
        if confirm_action(message):
            subprocess.run(f"curl -L '{url}' -o '{download_path}'", shell=True)
            model_path = download_path
            print('\n', "Finished downloading `Llama-2`.", '\n')
        else:
            print('\n', "Download cancelled. Exiting.", '\n')
            return None

    try:
        from llama_cpp import Llama
    except:
        # Ask for confirmation to install the required pip package
        message = "`Llama-2` interface package not found. Install `llama-cpp-python` package?"
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
            print('', "Finished downloading `Llama-2` interface.", '')

            # Tell them if their architecture is bad

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
                        # You might want to exit the script or add further instructions based on your requirements            
      
        else:
            print('', "Installation cancelled. Exiting.", '')
            return None

    if confirm_action("Use GPU? (Large models might crash on GPU, but will run more quickly)"):
      n_gpu_layers = -1
    else:
      n_gpu_layers = 0

    # Initialize and return Llama-2
    llama_2 = Llama(model_path=model_path, n_gpu_layers=n_gpu_layers)
    print(llama_2.__dict__)
      
    return llama_2

def confirm_action(message):
    # Print message with newlines on either side (aesthetic choice)
    print('', Markdown(f"{message} (y/n)"), '')
    response = input().strip().lower()
    print('') # <- Aesthetic choice
    return response == 'y'