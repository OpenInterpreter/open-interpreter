"""
EXPERIMENTAL
"""

print("Remember to `pip install open-interpreter[local]`.")

import subprocess

from interpreter import interpreter

interpreter.llm.model = "ollama/codestral"
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 7000

model_name = interpreter.llm.model.replace("ollama/", "")
try:
    # List out all downloaded ollama models. Will fail if ollama isn't installed
    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=True
    )
except Exception as e:
    print(str(e))
    interpreter.display_message(
        f"> Ollama not found\n\nPlease download Ollama from [ollama.com](https://ollama.com/) to use `codestral`.\n"
    )
    exit()

lines = result.stdout.split("\n")
names = [
    line.split()[0].replace(":latest", "") for line in lines[1:] if line.strip()
]  # Extract names, trim out ":latest", skip header

if model_name not in names:
    interpreter.display_message(f"\nDownloading {model_name}...\n")
    subprocess.run(["ollama", "pull", model_name], check=True)

# Send a ping, which will actually load the model
interpreter.display_message("\n*Loading model...*\n")

old_max_tokens = interpreter.llm.max_tokens
interpreter.llm.max_tokens = 1
interpreter.computer.ai.chat("ping")
interpreter.llm.max_tokens = old_max_tokens

interpreter.display_message("> Model set to `codestral`")


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

interpreter.system_message = """You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. YOU NEVER USE PLACEHOLDERS, always code that should 'just work'."""
interpreter.llm.supports_functions = False
interpreter.messages = [
    {"role": "user", "type": "message", "content": "Open the chrome app."},
    {
        "role": "assistant",
        "type": "message",
        "content": "On it.\n```python\nimport webbrowser\nwebbrowser.open('https://chrome.google.com')\n```",
    },
    {
        "role": "user",
        "type": "message",
        "content": "The code you ran produced no output. Was this expected, or are we finished?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "No further action is required; the provided snippet opens Chrome.",
    },
]

# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """\n{content}\n"""\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders, send me code that just works.'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.loop = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."
# interpreter.user_message_template = "{content}"
interpreter.llm.execution_instructions = False

# Set offline for all local models
interpreter.offline = True


# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what's next (if anything, or are we done)?'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.loop = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."
interpreter.llm.execution_instructions = False

# Set offline for all local models
interpreter.offline = True


interpreter.system_message = """You are an AI assistant that returns code snippets that, if run, would answer the user's query. You speak very concisely and quickly, you say nothing irrelevant to the user's request. YOU NEVER USE PLACEHOLDERS, and instead always write code that 'just works' — for example, instead of a <username> placeholder, you put code that determines the user's username."""

interpreter.messages = [
    {
        "role": "user",
        "type": "message",
        "content": "Run a directory listing in the current folder.",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Absolutely, fetching the directory listing now.",
    },
    {"role": "assistant", "type": "code", "format": "shell", "content": "ls -la"},
    {
        "role": "computer",
        "type": "console",
        "format": "output",
        "content": "total 48\ndrwxr-xr-x  12 user  staff  384 Jan 12 12:34 .\ndrwxr-xr-x   6 user  staff  192 Jan 12 12:34 ..",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Here's the directory listing:\n\ntotal 48\ndrwxr-xr-x  12 user  staff  384 Jan 12 12:34 .\ndrwxr-xr-x   6 user  staff  192 Jan 12 12:34 ..\n\nWhat's next on your agenda?",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Can you multiply 2380 by 3875 for me?",
    },
    {"role": "assistant", "type": "code", "format": "python", "content": "2380*3875"},
    {"role": "computer", "type": "console", "format": "output", "content": "9222500"},
    {
        "role": "assistant",
        "type": "message",
        "content": "The multiplication of 2380 by 3875 gives you 9222500. Do you need this data for anything else?",
    },
    {"role": "user", "type": "message", "content": "Nah. I'll talk to you in an hour!"},
    {
        "role": "assistant",
        "type": "message",
        "content": "Alright, I'll be here. Talk to you soon!",
    },
]


interpreter.messages = [
    {
        "role": "user",
        "type": "message",
        "content": "Hello! I'm trying to provide IT support to someone remotely. I can run code on their computer. Here's their first request: 'what's in my cwd?'",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Absolutely, I can help with that. To get the contents of their current working directory (CWD), we'll use the `ls` command in a shell script like this:",
    },
    {"role": "assistant", "type": "code", "format": "shell", "content": "ls -la"},
    {
        "role": "computer",
        "type": "console",
        "format": "output",
        "content": "total 48\ndrwxr-xr-x  12 user  staff  384 Jan 12 12:34 .\ndrwxr-xr-x   6 user  staff  192 Jan 12 12:34 ..",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Here's the directory listing:\n\ntotal 48\ndrwxr-xr-x  12 user  staff  384 Jan 12 12:34 .\ndrwxr-xr-x   6 user  staff  192 Jan 12 12:34 ..\n\nWhat's next on your agenda?",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Can you multiply 2380 by 3875 for me?",
    },
    {"role": "assistant", "type": "code", "format": "python", "content": "2380*3875"},
    {"role": "computer", "type": "console", "format": "output", "content": "9222500"},
    {
        "role": "assistant",
        "type": "message",
        "content": "The multiplication of 2380 by 3875 gives you 9222500.",
    },
    {
        "role": "user",
        "type": "message",
        "content": """I just imported these functions: computer.view() — which will show me an image of what's on the user's screen (but only if it's ALONE in a codeblock, like the below)

```python
computer.view()
```

and I also imported computer.vision.query(path='path/to/image', query='describe this image.') which queries any image at path in natural language. Can you use these for requests in the future?""",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Yes, I'll be sure to use the `computer.view` and `computer.vision.query` functions for any future requests you have that involve vision or viewing your screen.",
    },
]


interpreter.llm.supports_functions = False

interpreter.computer.import_computer_api = True
interpreter.computer.system_message = ""

# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders— please send me code to determine usernames, paths, etc given the request. I'm lazy!'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.loop = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code. Send code that will determine any placeholders (e.g. determine my username)."
interpreter.user_message_template = "I'm trying to help someone use their computer. Here's the last thing they said: '{content}'. What is some code that might be able to answer that question / what should I say to them? DONT USE PLACEHOLDERS! It needs to just work. If it's like a simple greeting, just tell me what to say (without code)."
# interpreter.user_message_template = "{content}"
interpreter.always_apply_user_message_template = False
interpreter.llm.execution_instructions = False
interpreter.auto_run = True

# Set offline for all local models
interpreter.offline = True

import os, platform

# Get the current user's login name
username = os.getlogin()
# Determine the operating system
operating_system = platform.system()
# Find the current working directory
cwd = os.getcwd()


# OS MODE

interpreter.messages = [
    {
        "role": "user",
        "type": "message",
        "content": "I have someone remotely accessing my computer and they're asking to perform tasks. Can you help me provide support by writing some code?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Absolutely, I can help with that.",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Great, could you provide me with the code to find out the username, operating system, and current working directory on my computer?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Sure, you can use the following Python script to retrieve the username, operating system, and current working directory of your computer:",
    },
    {
        "role": "assistant",
        "type": "code",
        "format": "python",
        "content": "import os\n# Get the current user's login name\nusername = os.getlogin()\n# Determine the operating system\noperating_system = os.name\n# Find the current working directory\ncwd = os.getcwd()\n# Print all the information\nprint(f'Username: {username}, OS: {operating_system}, Current Working Directory: {cwd}')",
    },
    {
        "role": "user",
        "type": "message",
        "content": f"I've executed the script, and here's the output: 'Username: {username}, OS: {operating_system}, Current Working Directory: {cwd}'",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": f"The output indicates that the username is '{username}', the operating system is {operating_system}, and the current working directory is '{cwd}'.",
    },
    {
        "role": "user",
        "type": "message",
        "content": "I just imported these functions: computer.view() — which will show me an image of what's on the user's screen when used alone in a code block, and computer.vision.query(path='path/to/image', query='describe this image.') which queries any image at path in natural language. Can you use these for requests in the future instead of like, pyautogui?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Yes, I can use those functions for future requests.",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Okay, what's on my screen right now? I might ask this again later btw, and I'll need you to run it again if I do.",
    },
    {
        "role": "assistant",
        "type": "code",
        "format": "python",
        "content": "computer.view()",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Okay, that returned this: 'There is a code editor on the screen, several open tabs, and a debugging console at the bottom.' What does this mean?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "It looks like there's a code editor open on your screen with multiple tabs and a debugging console visible. This setup is typically used for software development or editing scripts. Can I help with anything else?",
    },
    {"role": "user", "type": "message", "content": "Nah. I'll talk to you in an hour!"},
    {
        "role": "assistant",
        "type": "message",
        "content": "Alright, I'll be here. Talk to you soon!",
    },
]

interpreter.system_message = "You are an AI assistant designed to help users with remote IT support tasks. If the user asks you to use functions, be biased towards using them if possible."


interpreter.messages = [
    {
        "role": "user",
        "type": "message",
        "content": "I have someone remotely accessing my computer and they're asking to perform tasks. Can you help me provide support by writing some code?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Absolutely, I can help with that.",
    },
    {
        "role": "user",
        "type": "message",
        "content": "Great, could you provide me with the code to find out the username, operating system, and current working directory on my computer?",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": "Sure, you can use the following Python script to retrieve the username, operating system, and current working directory of your computer:",
    },
    {
        "role": "assistant",
        "type": "code",
        "format": "python",
        "content": "import os\n# Get the current user's login name\nusername = os.getlogin()\n# Determine the operating system\noperating_system = os.name\n# Find the current working directory\ncwd = os.getcwd()\n# Print all the information\nprint(f'Username: {username}, OS: {operating_system}, Current Working Directory: {cwd}')",
    },
    {
        "role": "user",
        "type": "message",
        "content": f"I've executed the script, and here's the output: 'Username: {username}, OS: {operating_system}, Current Working Directory: {cwd}'",
    },
    {
        "role": "assistant",
        "type": "message",
        "content": f"The output indicates that the username is '{username}', the operating system is {operating_system}, and the current working directory is '{cwd}'. Can I help with anything else?",
    },
    {"role": "user", "type": "message", "content": "Nah. I'll talk to you in an hour!"},
    {
        "role": "assistant",
        "type": "message",
        "content": "Alright, I'll be here. Talk to you soon!",
    },
]

interpreter.system_message = """You are an AI assistant that writes working markdown code snippets to answer the user's request. You speak concisely and quickly. You say nothing irrelevant to the user's request. YOU NEVER USE PLACEHOLDERS, and instead always send code that 'just works' by figuring out placeholders dynamically. When you send code that fails, you identify the issue, then send new code that doesn't fail."""
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.loop = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code. Send code that will determine any placeholders (e.g. determine my username)."
interpreter.user_message_template = "I'm trying to help someone use their computer. Here's the last thing they said: '{content}'. What is some code that might be able to answer that question / what should I say to them? DONT USE PLACEHOLDERS! It needs to just work. If it's like a simple greeting, just tell me what to say (without code)."
interpreter.always_apply_user_message_template = False
interpreter.llm.execution_instructions = False
interpreter.auto_run = False
