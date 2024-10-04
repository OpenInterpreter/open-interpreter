"""
This is an Open Interpreter profile. It configures Open Interpreter to run `llama3` using Ollama.

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

Now, your turn:""".strip()

# Message templates
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what code needs to be run next (if anything, or are we done)? I can't replace any placeholders.'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. What's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"

# LLM settings
interpreter.llm.model = "ollama/llama3"
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

# Final message
interpreter.display_message(
    "> Model set to `llama3`\n\n**Open Interpreter** will require approval before running code.\n\nUse `interpreter -y` to bypass this.\n\nPress `CTRL-C` to exit.\n"
)
