import os
import platform
import subprocess
import time

from interpreter import interpreter

if platform.system() == "Darwin":  # Check if the system is MacOS
    result = subprocess.run(
        ["xcode-select", "-p"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        interpreter.display_message(
            "To use the new, fully-managed `interpreter --local` (powered by Llamafile) Open Interpreter requires Mac users to have Xcode installed. You can install Xcode from https://developer.apple.com/xcode/ .\n\nAlternatively, you can use `LM Studio`, `Jan.ai`, or `Ollama` to manage local language models. Learn more at https://docs.openinterpreter.com/guides/running-locally ."
        )
        time.sleep(7)
        raise Exception("Xcode is not installed. Please install Xcode and try again.")

# Define the path to the models directory
models_dir = os.path.join(interpreter.get_oi_dir(), "models")

# Check and create the models directory if it doesn't exist
if not os.path.exists(models_dir):
    os.makedirs(models_dir)

# Define the path to the new llamafile
llamafile_path = os.path.join(models_dir, "phi-2.Q4_K_M.llamafile")

# Check if the new llamafile exists, if not download it
if not os.path.exists(llamafile_path):
    interpreter.display_message(
        "Open Interpreter will attempt to download and run the `Phi-2` language model. This should take ~10 minutes."
    )
    time.sleep(7)
    subprocess.run(
        [
            "wget",
            "-O",
            llamafile_path,
            "https://huggingface.co/jartine/phi-2-llamafile/resolve/main/phi-2.Q4_K_M.llamafile",
        ],
        check=True,
    )

# Make the new llamafile executable
subprocess.run(["chmod", "+x", llamafile_path], check=True)

# Run the new llamafile in the background
subprocess.Popen([llamafile_path])

interpreter.system_message = "You are Open Interpreter, a world-class programmer that can execute code on the user's machine."
interpreter.offline = True

interpreter.llm.model = "local"
interpreter.llm.temperature = 0
interpreter.llm.api_base = "https://localhost:8080/v1"
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 3000
