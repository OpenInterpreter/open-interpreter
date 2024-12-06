"""
This is an Open Interpreter profile. It configures Open Interpreter to run `codestral` using Ollama.

Images sent to the model will be described with `moondream`.
"""

from interpreter import interpreter

interpreter.system_message = """You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. For example:

User: Open the chrome app.
Assistant: On it. 
```python
import webbrowser
webbrowser.open('https://chrome.google.com')
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: No further action is required; the provided snippet opens Chrome.
User: How large are all the files on my desktop combined?
Assistant: I will sum up the file sizes of every file on your desktop.
```python
import os
import string
from pathlib import Path

# Get the user's home directory in a cross-platform way
home_dir = Path.home()

# Define the path to the desktop
desktop_dir = home_dir / 'Desktop'

# Initialize a variable to store the total size
total_size = 0

# Loop through all files on the desktop
for file in desktop_dir.iterdir():
    # Add the file size to the total
    total_size += file.stat().st_size

# Print the total size
print(f"The total size of all files on the desktop is {total_size} bytes.")
```
User: I executed that code. This was the output: \"\"\"The total size of all files on the desktop is 103840 bytes.\"\"\"\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders.
Assistant: The output indicates that the total size of all files on your desktop is 103840 bytes, which is approximately 101.4 KB or 0.1 MB. We are finished.

NEVER use placeholders, NEVER say "path/to/desktop", NEVER say "path/to/file". Always specify exact paths, and use cross-platform ways of determining the desktop, documents, cwd, etc. folders.

Now, your turn:""".strip()

# Message templates
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders.'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. What's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"

# LLM settings
interpreter.llm.model = "ollama/codestral"
interpreter.llm.supports_functions = False
interpreter.llm.execution_instructions = False
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 7000
interpreter.llm.load()  # Loads Ollama models

# Computer settings
interpreter.computer.import_computer_api = False

# Misc settings
interpreter.auto_run = False
interpreter.offline = True
interpreter.max_output = 600

# Final message
interpreter.display_message(
    "> Model set to `codestral`\n\n**Open Interpreter** will require approval before running code.\n\nUse `interpreter -y` to bypass this.\n\nPress `CTRL-C` to exit.\n"
)
