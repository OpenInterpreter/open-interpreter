"""
This is an Open Interpreter profile. It configures Open Interpreter to run `gemma2` using Ollama.
"""

from interpreter import interpreter

interpreter.system_message = """You are an AI assistant that writes tiny markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. For example:

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
interpreter.code_output_template = """I executed that code. This was the output: \n\n{content}\n\nWhat does this output mean? I can't understand it, please help / what code needs to be run next (if anything, or are we done with my query)?"""
interpreter.empty_code_output_template = "I executed your code snippet. It produced no text output. What's next (if anything, or are we done?)"
interpreter.user_message_template = (
    "Write a ```python code snippet that would answer this query: `{content}`"
)
interpreter.code_output_sender = "user"

# LLM settings
interpreter.llm.model = "ollama/gemma2"
interpreter.llm.supports_functions = False
interpreter.llm.execution_instructions = False
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 7000
interpreter.llm.load()  # Loads Ollama models

# Computer settings
interpreter.computer.import_computer_api = False

# Misc settings
interpreter.auto_run = True
interpreter.offline = True

# Final message
interpreter.display_message(
    "> Model set to `gemma2`\n\n**Open Interpreter** will require approval before running code.\n\nUse `interpreter -y` to bypass this.\n\nPress `CTRL-C` to exit.\n"
)
