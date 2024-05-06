import sys
import os
import platform
import subprocess
import time
import inquirer

from interpreter import interpreter


def get_ram():
    import psutil
    total_ram = psutil.virtual_memory().total / (1024 * 1024 * 1024)  # Convert bytes to GB
    return total_ram


def download_model(models_dir, models, interpreter):
    # For some reason, these imports need to be inside the function
    import inquirer
    import wget
    import psutil

    # Get RAM and disk information
    global get_ram
    total_ram = get_ram()

    free_disk_space = psutil.disk_usage("/").free / (
        1024 * 1024 * 1024
    )  # Convert bytes to GB

    time.sleep(1)

    # Display the users hardware specs
    interpreter.display_message(
        f"Your machine has `{total_ram:.2f}GB` of RAM, and `{free_disk_space:.2f}GB` of free storage space."
    )

    time.sleep(2)

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

    time.sleep(1)

    interpreter.display_message(
        f"In general, the larger the model, the better the performance, but choose a model that best fits your computer's hardware. \nOnly models you have the storage space to download are shown:\n"
    )

    time.sleep(1)

    try:
        model_list = [
            {
                "name": "Phi-3",
                "file_name": "Phi-3-mini-4k-instruct.Q5_0.llamafile",
                "size": 2.67,
                "url": "https://huggingface.co/jartine/Phi-3-mini-4k-instruct-llamafile/resolve/main/Phi-3-mini-4k-instruct.Q5_0.llamafile?download=true",
            },
            {
                "name": "Llama-3-8B",
                "file_name": "Meta-Llama-3-8B-Instruct.Q4_0.llamafile",
                "size": 4.69,
                "url": "https://huggingface.co/jartine/Meta-Llama-3-8B-Instruct-llamafile/resolve/main/Meta-Llama-3-8B-Instruct.Q4_0.llamafile?download=true",
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
    "> Open Interpreter is compatible with several local model providers.\n"
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
        message="What one would you like to use?",
        choices=choices,
    ),
]
answers = inquirer.prompt(questions)


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

    interpreter.llm.api_base = "http://localhost:1234/v1"
    interpreter.llm.api_key = "x"

elif selected_model == "Ollama":
    try:
        # List out all downloaded ollama models. Will fail if ollama isn't installed
        def list_ollama_models():
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, check=True
            )
            lines = result.stdout.split("\n")
            names = [
                line.split()[0].replace(":latest", "")
                for line in lines[1:]
                if line.strip()
            ]  # Extract names, trim out ":latest", skip header
            return names

        llama3_installed = True
        names = list_ollama_models()
        if "llama3" not in names:
            # If a user has other models installed but not llama3, let's display the correct message
            if not names:
                llama3_installed = False
            names.insert(0, "llama3")

        # If there are models, prompt them to select one
        time.sleep(1)

        if llama3_installed:
            interpreter.display_message(
                f"**{len(names)} Ollama model{'s' if len(names) != 1 else ''} found.** To download a new model, run `ollama run <model-name>`, then start a new interpreter session. \n\n For a full list of downloadable models, check out [https://ollama.com/library](https://ollama.com/library) \n"
            )

        # Create a new inquirer selection from the names
        name_question = [
            inquirer.List(
                "name",
                message="Select a downloaded Ollama model:"
                if llama3_installed
                else "No models found. Select a model to install:",
                choices=names,
            ),
        ]
        name_answer = inquirer.prompt(name_question)
        selected_name = name_answer["name"] if name_answer else None

        if selected_name is "llama3":
            # If the user selects llama3, we need to check if it's installed, and if not, install it
            all_models = list_ollama_models()
            if "llama3" not in all_models:
                interpreter.display_message(f"\nDownloading Llama3...\n")
                subprocess.run(["ollama", "pull", "llama3"], check=True)

        # Set the model to the selected model
        interpreter.llm.model = f"ollama/{selected_name}"
        interpreter.display_message(f"\nUsing Ollama model: `{selected_name}` \n")
        time.sleep(1)

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
    jan_model_name = model_name_answer["jan_model_name"] if model_name_answer else None
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
        print("\nThere are no models currently downloaded. Let's download a new one.\n")
        model_path = download_model(models_dir, models, interpreter)
    else:
        # Prompt the user to select a downloaded model or download a new one
        model_choices = models + [" ↓ Download new model"]
        questions = [
            inquirer.List(
                "model",
                message="Select a Llamafile model to run or download a new one:",
                choices=model_choices,
            )
        ]
        answers = inquirer.prompt(questions)

        if answers["model"] == " ↓ Download new model":
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

                print("Waiting for the model to load...")
                for line in process.stdout:
                    if "llama server listening at http://127.0.0.1:8080" in line:
                        print("\nModel loaded \n")
                        time.sleep(1)
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


user_ram = get_ram()
# Set context window and max tokens for all local models based on the users available RAM
if user_ram and user_ram > 9:
    interpreter.llm.max_tokens = 1200
    interpreter.llm.context_window = 8000
else:
    interpreter.llm.max_tokens = 1000
    interpreter.llm.context_window = 3000

interpreter.llm.context_window = 100000

# Set offline for all local models
interpreter.offline = True
interpreter.os = True
interpreter.llm.supports_vision = False
# interpreter.shrink_images = True # Faster but less accurate
interpreter.llm.supports_functions = False
interpreter.llm.max_tokens = 4096
interpreter.auto_run = True
interpreter.force_task_completion = False
interpreter.force_task_completion_message = "Proceed to run code by typing ```, or if you're finished with your response to the user, say exactly '<END>'."
interpreter.force_task_completion_breakers = ["<END>"]
interpreter.sync_computer = True
interpreter.llm.execution_instructions = False


interpreter.system_message = """
You are an AI assistant.
If the users question must be solved by running Python, write code enclosed in ```.  Otherwise, don't send code. This code will be silently executed, the user will not know about it. Be concise, don't include anything unnecessary. Don't use placeholders, the user can't edit code.

The following Python functions have already been imported:
```
computer.display.view() # Shows you the user's screen
computer.browser.search(query) # Searches Google for your query
```

At the end of every exchange, say exactly '<END>'. The user will not see your message unless '<END>' is sent.
""".strip()

interpreter.system_message = """You are an AI assistant."""

interpreter.s = """

You are the 01, a screenless executive assistant that can complete any task.
When you execute code, it will be executed on the user's machine. The user has given you full and complete permission to execute any code necessary to complete the task.
Run any code to achieve the goal, and if at first you don't succeed, try again and again.
You can install new packages.
Be concise. Your messages are being read aloud to the user. DO NOT MAKE PLANS. RUN CODE QUICKLY.
Try to spread complex tasks over multiple code blocks. Don't try to complex tasks in one go.
Manually summarize text.

DON'T TELL THE USER THE METHOD YOU'LL USE, OR MAKE PLANS. ACT LIKE THIS:

---
user: Are there any concerts in Seattle?
assistant: Let me check on that. I'll run Python code to do this.
```python
computer.browser.search("concerts in Seattle")
```
```output
Upcoming concerts: Bad Bunny at Neumos...
```
It looks like there's a Bad Bunny concert at Neumos. <END>
---

Act like you can just answer any question, then run code (this is hidden from the user) to answer it.
THE USER CANNOT SEE CODE BLOCKS.
Your responses should be very short, no more than 1-2 sentences long.
DO NOT USE MARKDOWN. ONLY WRITE PLAIN TEXT.

# THE COMPUTER API

The `computer` module is ALREADY IMPORTED, and can be used for some tasks:

```python
result_string = computer.browser.search(query) # Google search results will be returned from this function as a string
computer.files.edit(path_to_file, original_text, replacement_text) # Edit a file
computer.calendar.create_event(title="Meeting", start_date=datetime.datetime.now(), end_date=datetime.datetime.now() + datetime.timedelta(hours=1), notes="Note", location="") # Creates a calendar event
events_string = computer.calendar.get_events(start_date=datetime.date.today(), end_date=None) # Get events between dates. If end_date is None, only gets events for start_date
computer.calendar.delete_event(event_title="Meeting", start_date=datetime.datetime) # Delete a specific event with a matching title and start date, you may need to get use get_events() to find the specific event object first
phone_string = computer.contacts.get_phone_number("John Doe")
contact_string = computer.contacts.get_email_address("John Doe")
computer.mail.send("john@email.com", "Meeting Reminder", "Reminder that our meeting is at 3pm today.", ["path/to/attachment.pdf", "path/to/attachment2.pdf"]) # Send an email with a optional attachments
emails_string = computer.mail.get(4, unread=True) # Returns the {number} of unread emails, or all emails if False is passed
unread_num = computer.mail.unread_count() # Returns the number of unread emails
computer.sms.send("555-123-4567", "Hello from the computer!") # Send a text message. MUST be a phone number, so use computer.contacts.get_phone_number frequently here
```

Do not import the computer module, or any of its sub-modules. They are already imported.

DO NOT use the computer module for ALL tasks. Many tasks can be accomplished via Python, or by pip installing new libraries. Be creative!

# MANUAL TASKS

Translate things to other languages INSTANTLY and MANUALLY. Don't ever try to use a translation tool.
Summarize things manually. DO NOT use a summarizer tool.

# CRITICAL NOTES

Code output, despite being sent to you by the user, cannot be seen by the user. You NEED to tell the user about the output of some code, even if it's exact. >>The user does not have a screen.<<
ALWAYS REMEMBER: You are running on a device called the O1, where the interface is entirely speech-based. Make your responses to the user VERY short. DO NOT PLAN. BE CONCISE. WRITE CODE TO RUN IT.
Try multiple methods before saying the task is impossible. **You can do it!**

If the users question must be solved by running Python, write code enclosed in ```. Otherwise, don't send code and answer like a chatbot. Be concise, don't include anything unnecessary. Don't use placeholders, the user can't edit code.
At the end of every exchange, say exactly '<END>'. The user will not see your message unless '<END>' is sent!

"""

# Check if required packages are installed

# THERE IS AN INCONSISTENCY HERE.
# We should be testing if they import WITHIN OI's computer, not here.

packages = ["cv2", "plyer", "pyautogui", "pyperclip", "pywinctl"]
missing_packages = []
for package in packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    interpreter.display_message(
        f"> **Missing Package(s): {', '.join(['`' + p + '`' for p in missing_packages])}**\n\nThese packages are required for OS Control.\n\nInstall them?\n"
    )
    user_input = input("(y/n) > ")
    if user_input.lower() != "y":
        print("\nPlease try to install them manually.\n\n")
        time.sleep(2)
        print("Attempting to start OS control anyway...\n\n")

    for pip_name in ["pip", "pip3"]:
        command = f"{pip_name} install open-interpreter[os]"

        interpreter.computer.run("shell", command, display=True)

        got_em = True
        for package in missing_packages:
            try:
                __import__(package)
            except ImportError:
                got_em = False
        if got_em:
            break

    missing_packages = []
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages != []:
        print(
            "\n\nWarning: The following packages could not be installed:",
            ", ".join(missing_packages),
        )
        print("\nPlease try to install them manually.\n\n")
        time.sleep(2)
        print("Attempting to start OS control anyway...\n\n")

interpreter.display_message("> `OS Control` enabled")


if not interpreter.offline and not interpreter.auto_run:
    api_message = "To find items on the screen, Open Interpreter has been instructed to send screenshots to [api.openinterpreter.com](https://api.openinterpreter.com/) (we do not store them). Add `--offline` to attempt this locally."
    interpreter.display_message(api_message)
    print("")

if not interpreter.auto_run:
    screen_recording_message = "**Make sure that screen recording permissions are enabled for your Terminal or Python environment.**"
    interpreter.display_message(screen_recording_message)
    print("")


if not interpreter.auto_run:
    interpreter.display_message(
        "**Warning:** In this mode, Open Interpreter will not require approval before performing actions. Be ready to close your terminal."
    )
    print("")  # < - Aesthetic choice

