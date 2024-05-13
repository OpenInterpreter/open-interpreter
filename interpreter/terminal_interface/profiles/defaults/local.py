import os
import platform
import subprocess
import sys
import time

import inquirer
import psutil
import wget

from interpreter import interpreter

model = None


def download_model(models_dir, models, interpreter):
    # Get RAM and disk information
    total_ram = psutil.virtual_memory().total / (
        1024 * 1024 * 1024
    )  # Convert bytes to GB
    free_disk_space = psutil.disk_usage("/").free / (
        1024 * 1024 * 1024
    )  # Convert bytes to GB

    # Display the users hardware specs
    interpreter.display_message(
        f"Your machine has `{total_ram:.2f}GB` of RAM, and `{free_disk_space:.2f}GB` of free storage space."
    )

    if total_ram < 10:
        interpreter.display_message(
            f"\nYour computer realistically can only run smaller models less than 4GB, Phi-2 might be the best model for your computer.\n"
        )
    elif 10 <= total_ram < 30:
        interpreter.display_message(
            f"\nYour computer could handle a mid-sized model (4-10GB), Mistral-7B might be the best model for your computer.\n"
        )
    else:
        interpreter.display_message(
            f"\nYour computer should have enough RAM to run any model below.\n"
        )

    interpreter.display_message(
        f"In general, the larger the model, the better the performance, but choose a model that best fits your computer's hardware. \nOnly models you have the storage space to download are shown:\n"
    )

    try:
        model_list = [
            {
                "name": "Llama-3-8B-Instruct",
                "file_name": " Meta-Llama-3-8B-Instruct.Q5_K_M.llamafile",
                "size": 5.76,
                "url": "https://huggingface.co/jartine/Meta-Llama-3-8B-Instruct-llamafile/resolve/main/Meta-Llama-3-8B-Instruct.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "Phi-3-mini",
                "file_name": "Phi-3-mini-4k-instruct.Q5_K_M.llamafile",
                "size": 2.84,
                "url": "https://huggingface.co/jartine/Phi-3-mini-4k-instruct-llamafile/resolve/main/Phi-3-mini-4k-instruct.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "TinyLlama-1.1B",
                "file_name": "TinyLlama-1.1B-Chat-v1.0.Q5_K_M.llamafile",
                "size": 0.76,
                "url": "https://huggingface.co/jartine/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/TinyLlama-1.1B-Chat-v1.0.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "Rocket-3B",
                "file_name": "rocket-3b.Q5_K_M.llamafile",
                "size": 1.89,
                "url": "https://huggingface.co/jartine/rocket-3B-llamafile/resolve/main/rocket-3b.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "Phi-2",
                "file_name": "phi-2.Q5_K_M.llamafile",
                "size": 1.96,
                "url": "https://huggingface.co/jartine/phi-2-llamafile/resolve/main/phi-2.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "LLaVA 1.5",
                "file_name": "llava-v1.5-7b-q4.llamafile",
                "size": 3.97,
                "url": "https://huggingface.co/jartine/llava-v1.5-7B-GGUF/resolve/main/llava-v1.5-7b-q4.llamafile?download=true",
            },
            {
                "name": "Mistral-7B-Instruct",
                "file_name": "mistral-7b-instruct-v0.2.Q5_K_M.llamafile",
                "size": 5.15,
                "url": "https://huggingface.co/jartine/Mistral-7B-Instruct-v0.2-llamafile/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "WizardCoder-Python-13B",
                "file_name": "wizardcoder-python-13b.llamafile",
                "size": 7.33,
                "url": "https://huggingface.co/jartine/wizardcoder-13b-python/resolve/main/wizardcoder-python-13b.llamafile?download=true",
            },
            {
                "name": "WizardCoder-Python-34B",
                "file_name": "wizardcoder-python-34b-v1.0.Q5_K_M.llamafile",
                "size": 22.23,
                "url": "https://huggingface.co/jartine/WizardCoder-Python-34B-V1.0-llamafile/resolve/main/wizardcoder-python-34b-v1.0.Q5_K_M.llamafile?download=true",
            },
            {
                "name": "Mixtral-8x7B-Instruct",
                "file_name": "mixtral-8x7b-instruct-v0.1.Q5_K_M.llamafile",
                "size": 30.03,
                "url": "https://huggingface.co/jartine/Mixtral-8x7B-Instruct-v0.1-llamafile/resolve/main/mixtral-8x7b-instruct-v0.1.Q5_K_M.llamafile?download=true",
            },
        ]

        # Filter models based on available disk space and RAM
        filtered_models = [
            model
            for model in model_list
            if model["size"] <= free_disk_space and model["file_name"] not in models
        ]
        if filtered_models:
            time.sleep(1)

            # Prompt the user to select a model
            model_choices = [
                f"{model['name']} ({model['size']:.2f}GB)" for model in filtered_models
            ]
            questions = [
                inquirer.List(
                    "model",
                    message="Select a model to download:",
                    choices=model_choices,
                )
            ]
            answers = inquirer.prompt(questions)

            if answers == None:
                exit()

            # Get the selected model
            selected_model = next(
                model
                for model in filtered_models
                if f"{model['name']} ({model['size']}GB)" == answers["model"]
            )

            # Download the selected model
            model_url = selected_model["url"]
            # Extract the basename and remove query parameters
            filename = os.path.basename(model_url).split("?")[0]
            model_path = os.path.join(models_dir, filename)

            time.sleep(1)
            print(f"\nDownloading {selected_model['name']}...\n")
            wget.download(model_url, model_path)

            # Make the model executable if not on Windows
            if platform.system() != "Windows":
                subprocess.run(["chmod", "+x", model_path], check=True)

            print(f"\nModel '{selected_model['name']}' downloaded successfully.\n")

            interpreter.display_message(
                "To view or delete downloaded local models, run `interpreter --local_models`\n\n"
            )

            return model_path
        else:
            print(
                "\nYour computer does not have enough storage to download any local LLMs.\n"
            )
            return None
    except Exception as e:
        print(e)
        print(
            "\nAn error occurred while trying to download the model. Please try again or use a different local model provider.\n"
        )
        return None


# START OF LOCAL MODEL PROVIDER LOGIC
interpreter.display_message(
    "\n**Open Interpreter** supports multiple local model providers.\n"
)

# Define the choices for local models
choices = [
    "Ollama",
    "Llamafile",
    "LM Studio",
    "Jan",
]

# Use inquirer to let the user select an option
questions = [
    inquirer.List(
        "model",
        message="Select a provider",
        choices=choices,
    ),
]
answers = inquirer.prompt(questions)

if answers == None:
    exit()

selected_model = answers["model"]


if selected_model == "LM Studio":
    interpreter.display_message(
        """
To use use Open Interpreter with **LM Studio**, you will need to run **LM Studio** in the background.

1. Download **LM Studio** from [https://lmstudio.ai/](https://lmstudio.ai/), then start it.
2. Select a language model then click **Download**.
3. Click the **<->** button on the left (below the chat button).
4. Select your model at the top, then click **Start Server**.


Once the server is running, you can begin your conversation below.

"""
    )
    interpreter.llm.supports_functions = False
    interpreter.llm.api_base = "http://localhost:1234/v1"
    interpreter.llm.api_key = "x"

elif selected_model == "Ollama":
    try:
        # List out all downloaded ollama models. Will fail if ollama isn't installed
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        )
        lines = result.stdout.split("\n")
        names = [
            line.split()[0].replace(":latest", "") for line in lines[1:] if line.strip()
        ]  # Extract names, trim out ":latest", skip header

        for model in ["llama3", "phi3", "wizardlm2"]:
            if model not in names:
                names.append("→ Download " + model)

        # Create a new inquirer selection from the names
        name_question = [
            inquirer.List(
                "name",
                message="Select a model",
                choices=names,
            ),
        ]
        name_answer = inquirer.prompt(name_question)

        if name_answer == None:
            exit()

        selected_name = name_answer["name"]

        if "download" in selected_name.lower():
            model = selected_name.split(" ")[-1]
            interpreter.display_message(f"\nDownloading {model}...\n")
            subprocess.run(["ollama", "pull", model], check=True)
        else:
            model = selected_name.strip()

        # Set the model to the selected model
        interpreter.llm.model = f"ollama/{model}"
        interpreter.display_message(f"> Model set to `{model}`")

    # If Ollama is not installed or not recognized as a command, prompt the user to download Ollama and try again
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("Ollama is not installed or not recognized as a command.")
        time.sleep(1)
        interpreter.display_message(
            f"\nPlease visit [https://ollama.com/](https://ollama.com/) to download Ollama and try again\n"
        )
        time.sleep(2)
        sys.exit(1)

elif selected_model == "Jan":
    interpreter.display_message(
        """
To use use Open Interpreter with **Jan**, you will need to run **Jan** in the background.

1. Download **Jan** from [https://jan.ai/](https://jan.ai/), then start it.
2. Select a language model from the "Hub" tab, then click **Download**.
3. Copy the ID of the model and enter it below.
3. Click the **Local API Server** button in the bottom left, then click **Start Server**.


Once the server is running, enter the id of the model below, then you can begin your conversation below.

"""
    )
    interpreter.llm.api_base = "http://localhost:1337/v1"
    time.sleep(1)

    # Prompt the user to enter the name of the model running on Jan
    model_name_question = [
        inquirer.Text(
            "jan_model_name",
            message="Enter the id of the model you have running on Jan",
        ),
    ]
    model_name_answer = inquirer.prompt(model_name_question)

    if model_name_answer == None:
        exit()

    jan_model_name = model_name_answer["jan_model_name"]
    interpreter.llm.model = f"jan/{jan_model_name}"
    interpreter.display_message(f"\nUsing Jan model: `{jan_model_name}` \n")
    time.sleep(1)


elif selected_model == "Llamafile":
    if platform.system() == "Darwin":  # Check if the system is MacOS
        result = subprocess.run(
            ["xcode-select", "-p"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if result.returncode != 0:
            interpreter.display_message(
                "To use Llamafile, Open Interpreter requires Mac users to have Xcode installed. You can install Xcode from https://developer.apple.com/xcode/ .\n\nAlternatively, you can use `LM Studio`, `Jan.ai`, or `Ollama` to manage local language models. Learn more at https://docs.openinterpreter.com/guides/running-locally ."
            )
            time.sleep(3)
            raise Exception(
                "Xcode is not installed. Please install Xcode and try again."
            )

    # Define the path to the models directory
    models_dir = os.path.join(interpreter.get_oi_dir(), "models")

    # Check and create the models directory if it doesn't exist
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    # Check if there are any models in the models folder
    models = [f for f in os.listdir(models_dir) if f.endswith(".llamafile")]

    if not models:
        print(
            "\nNo models currently downloaded. Please select a new model to download.\n"
        )
        model_path = download_model(models_dir, models, interpreter)
    else:
        # Prompt the user to select a downloaded model or download a new one
        model_choices = models + ["↓ Download new model"]
        questions = [
            inquirer.List(
                "model",
                message="Select a model",
                choices=model_choices,
            )
        ]
        answers = inquirer.prompt(questions)

        if answers == None:
            exit()

        if answers["model"] == "↓ Download new model":
            model_path = download_model(models_dir, models, interpreter)
        else:
            model_path = os.path.join(models_dir, answers["model"])

        if model_path:
            try:
                # Run the selected model and hide its output
                process = subprocess.Popen(
                    f'"{model_path}" ' + " ".join(["--nobrowser", "-ngl", "9999"]),
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                for line in process.stdout:
                    if "llama server listening at http://127.0.0.1:8080" in line:
                        break  # Exit the loop once the server is ready
            except Exception as e:
                process.kill()  # Force kill if not terminated after timeout
                print(e)
                print("Model process terminated.")

    # Set flags for Llamafile to work with interpreter
    interpreter.llm.model = "openai/local"
    interpreter.llm.temperature = 0
    interpreter.llm.api_base = "http://localhost:8080/v1"
    interpreter.llm.supports_functions = False

    model_name = model_path.split("/")[-1]
    interpreter.display_message(f"> Model set to `{model_name}`")

user_ram = total_ram = psutil.virtual_memory().total / (
    1024 * 1024 * 1024
)  # Convert bytes to GB
# Set context window and max tokens for all local models based on the users available RAM
if user_ram and user_ram > 9:
    interpreter.llm.max_tokens = 1200
    interpreter.llm.context_window = 8000
else:
    interpreter.llm.max_tokens = 1000
    interpreter.llm.context_window = 3000

# Display intro message
if interpreter.auto_run == False:
    interpreter.display_message(
        "**Open Interpreter** will require approval before running code."
        + "\n\nUse `interpreter -y` to bypass this."
        + "\n\nPress `CTRL-C` to exit.\n"
    )

# Set the system message to a minimal version for all local models.
interpreter.system_message = """
You are Open Interpreter, a world-class programmer that can execute code on the user's machine.
First, list all of the information you know related to the user's request.
Next, write a plan. **Always recap the plan between each code block** (you have extreme short-term memory loss, so you need to recap the plan between each message block to retain it).
The code you write must be able to be executed as is. Invalid syntax will cause a catastrophic failure. Do not include the language of the code in the response.
When you execute code, it will be executed **on the user's machine**. The user has given you **full and complete permission** to execute any code necessary to complete the task. Execute the code.
You can access the internet. Run **any code** to achieve the goal, and if at first you don't succeed, try again and again.
You can install new packages.
When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.
Write messages to the user in Markdown.
In general, try to **make plans** with as few steps as possible. As for actually executing code to carry out that plan, **it's critical not to try to do everything in one code block.** You should try something, print information about it, then continue from there in tiny, informed steps. You will never get it on the first try, and attempting it in one go will often lead to errors you cant see.
You are capable of **any** task.
Once you have accomplished the task, ask the user if they are happy with the result and wait for their response. It is very important to get feedback from the user. 
The user will tell you the next task after you ask them.
"""

interpreter.system_message = """You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. For example:

User: Open the chrome app.
Assistant: On it. 
```python
import webbrowser
webbrowser.open('https://chrome.google.com')
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: No further action is required; the provided snippet opens Chrome.

Now, your turn:
"""

# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what's next (if anything, or are we done)?'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.force_task_completion = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."
interpreter.llm.execution_instructions = False

# Set offline for all local models
interpreter.offline = True
