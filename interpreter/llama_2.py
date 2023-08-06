import os
import time
import subprocess

# Define the file name to search for
file_name = "llama-2-13b-chat.ggmlv3.q4_0.bin"

# Start the timer
start_time = time.time()

# Check for the file in each path
for path in [os.path.expanduser("~"), os.getcwd()]:
    print(f"Searching for Llama-2 in {path} ...")
    for root, _, files in os.walk(path):
        if time.time() - start_time > 5:
            print("Search timed out after 5 seconds.")
            break
        if file_name in files:
            model_path = os.path.join(root, file_name)
            print(f"Found Llama-2 at {model_path}")
            break
    else:
        continue
    break
else:
    # If the file was not found, download it
    download_path = os.path.expanduser("~") + "/llama-2/" + file_name
    print(f"Llama-2 not found. Downloading it to {download_path} ...")
    url = "https://huggingface.co/TheBloke/Llama-2-13B-chat-GGML/resolve/main/llama-2-13b-chat.ggmlv3.q4_0.bin"
    subprocess.run(f"curl -L '{url}' -o {download_path}", shell=True)
    model_path = download_path

try:
  from llama_cpp import Llama
except:
  print("Downloading Llama-2 interface (llama-cpp-python)...")
  subprocess.run(["pip", "install", "llama-cpp-python"])
  from llama_cpp import Llama

# Initialize Llama-2
llama_2 = Llama(model_path=model_path)