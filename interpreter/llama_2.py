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
    print('', Markdown("Please select a `Llama-2` model (use arrow keys)."), '')
    
    llama_2_7b = [
        # Smallest/Fastest
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-7B-chat-GGML/resolve/main/llama-2-7b-chat.ggmlv3.q2_K.bin', 'Param': '7B', 'Bits': 2, 'Size': '2.87 GB', 'RAM': '5.37 GB', 'Description': 'New k-quant method. Uses GGML_TYPE_Q4_K for the attention.vw and feed_forward.w2 tensors, GGML_TYPE_Q2_K for the other tensors.'},
        # Middle Ground
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-7B-chat-GGML/resolve/main/llama-2-7b-chat.ggmlv3.q4_1.bin', 'Param': '7B', 'Bits': 4, 'Size': '4.21 GB', 'RAM': '6.71 GB', 'Description': 'Original quant method, 4-bit. Higher accuracy than q4_0 but not as high as q5_0. However has quicker inference than q5 models.'},
        # Middle Ground
        # {'URL': 'https://huggingface.co/TheBloke/Llama-2-7B-chat-GGML/resolve/main/llama-2-7b-chat.ggmlv3.q5_0.bin', 'Param': '7B', 'Bits': 5, 'Size': '4.63 GB', 'RAM': '7.13 GB', 'Description': 'Original quant method, 5-bit. Higher accuracy, higher resource usage and slower inference.'},
        # Best/Slowest
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-7B-chat-GGML/resolve/main/llama-2-7b-chat.ggmlv3.q8_0.bin', 'Param': '7B', 'Bits': 8, 'Size': '7.16 GB', 'RAM': '9.66 GB', 'Description': 'Original quant method, 8-bit. Almost indistinguishable from float16. High resource use and slow. Not recommended for most users.'}
    ]
    llama_2_13b = [
        # Smallest/Fastest
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-13B-chat-GGML/resolve/main/llama-2-13b-chat.ggmlv3.q2_K.bin', 'Param': '13B', 'Bits': 2, 'Size': '5.51 GB', 'RAM': '8.01 GB', 'Description': 'New k-quant method. Uses GGML_TYPE_Q4_K for the attention.vw and feed_forward.w2 tensors, GGML_TYPE_Q2_K for the other tensors.'},
        # Middle Ground
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-13B-chat-GGML/resolve/main/llama-2-13b-chat.ggmlv3.q3_K_L.bin', 'Param': '13B', 'Bits': 3, 'Size': '6.93 GB', 'RAM': '9.43 GB', 'Description': 'New k-quant method. Uses GGML_TYPE_Q5_K for the attention.wv, attention.wo, and feed_forward.w2 tensors, else GGML_TYPE_Q3_K'},
        # Middle Ground
        # {'URL': 'https://huggingface.co/TheBloke/Llama-2-13B-chat-GGML/resolve/main/llama-2-13b-chat.ggmlv3.q4_1.bin', 'Param': '13B', 'Bits': 4, 'Size': '8.14 GB', 'RAM': '10.64 GB', 'Description': 'Original quant method, 4-bit. Higher accuracy than q4_0 but not as high as q5_0. However has quicker inference than q5 models.'},
        # Best/Slowest
        {'URL': 'https://huggingface.co/TheBloke/Llama-2-13B-chat-GGML/resolve/main/llama-2-13b-chat.ggmlv3.q8_0.bin', 'Param': '13B', 'Bits': 8, 'Size': '13.83 GB', 'RAM': '16.33 GB', 'Description': 'Original quant method, 8-bit. Almost indistinguishable from float16. High resource use and slow. Not recommended for most users.'}
    ]
    code_llama_13b = [
        {'URL': 'https://huggingface.co/TheBloke/CodeLlama-13B-oasst-sft-v10-GGUF/resolve/main/codellama-13b-oasst-sft-v10.Q4_K_M.gguf', 'Param': '13B', 'Bits': 8, 'Size': '13.83 GB', 'RAM': '16.33 GB', 'Description': 'Original quant method, 8-bit. Almost indistinguishable from float16. High resource use and slow. Not recommended for most users.'}
    ]
    
    #all_models = llama_2_7b + llama_2_13b + code_llama_13b
    all_models = code_llama_13b
  
    
    # Function to format the model choice for display
    def format_choice(model):
        return f"{model['Param']} Parameter, {model['Bits']}-Bit | Size: {model['Size']}, RAM usage: {model['RAM']}"
    
    questions = [
        inquirer.List('URL',
                      choices=[(format_choice(m), m['URL']) for m in all_models])
    ]
    
    answers = inquirer.prompt(questions)
    
    url = answers['URL']
    file_name = url.split("/")[-1]

    # Get user data directory for your application
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

            import subprocess
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

    # Initialize and return Llama-2
    # n_gpu_layers=1 should use GPU, but frankly I can't tell if it does (Mac OSX)
    if confirm_action("1 or -1"):
      llama_2 = Llama(model_path=model_path, n_gpu_layers=-1, n_ctx=2000)
    else:
      llama_2 = Llama(model_path=model_path, n_gpu_layers=1, n_ctx=2000)
      
    return llama_2

def confirm_action(message):
    # Print message with newlines on either side (aesthetic choice)
    print('', Markdown(f"{message} (y/n)"), '')
    response = input().strip().lower()
    print('') # <- Aesthetic choice
    return response == 'y'