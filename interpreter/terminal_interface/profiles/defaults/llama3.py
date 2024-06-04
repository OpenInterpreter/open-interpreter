import subprocess

from interpreter import interpreter

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
interpreter.force_task_completion = False
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
interpreter.force_task_completion = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."
interpreter.llm.execution_instructions = False

# Set offline for all local models
interpreter.offline = True


interpreter.system_message = """You are an AI assistant that returns code snippets that, if run, would answer the user's query. You speak very concisely and quickly, you say nothing irrelevant to the user's request. YOU NEVER USE PLACEHOLDERS, and instead always write code that 'just works' — for example, instead of a <username> placeholder, you put code that determines the user's username."
# specialized in coding and automation, providing concise code snippets and friendly responses to enhance the user's productivity."""

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


interpreter.llm.supports_functions = False

# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders.'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.force_task_completion = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."
interpreter.user_message_template = "I'm trying to help someone use their computer. Here's the last thing they said: '{content}'. What is some code that might be able to answer that question / what should I say to them? DONT USE PLACEHOLDERS! It needs to just work."
# interpreter.user_message_template = "{content}"
interpreter.llm.execution_instructions = False
interpreter.auto_run = False

# Set offline for all local models
interpreter.offline = True


##### FOR LLAMA3
interpreter.messages = []
interpreter.system_message = """You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. For example:

User: Open the chrome app.
Assistant: On it. 
```python
import webbrowser
webbrowser.open('https://chrome.google.com')
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: No further action is required; the provided snippet opens Chrome.

Now, your turn:"""


interpreter.llm.model = "ollama/llama3"
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 7000

# The below should be pushed into interpreter.llm.load()?

model_name = interpreter.llm.model.replace("ollama/", "")
try:
    # List out all downloaded ollama models. Will fail if ollama isn't installed
    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=True
    )
except Exception as e:
    print(str(e))
    interpreter.display_message(
        f"> Ollama not found\n\nPlease download Ollama from [ollama.com](https://ollama.com/) to use `llama3`.\n"
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

interpreter.display_message("> Model set to `llama3`")
