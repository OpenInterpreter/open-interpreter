"""
This is an Open Interpreter profile. It configures Open Interpreter to run `llama3` using Ollama.

Images sent to the model will be described with `moondream`. The model will be instructed how to control your mouse and keyboard.
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

You also have access to a special function called `computer.view()`. This will return a description of the user's screen. Do NOT use pyautogui. For example:

User: What's on my screen?
Assistant: Viewing screen. 
```python
computer.view()
```
User: The code you ran produced this output: "A code editor". I don't understand it, what does it mean?
Assistant: The output means you have a code editor on your screen.

You have exactly three more special computer functions:

`computer.mouse.click("button text")` which clicks the specified text on-screen.
`computer.keyboard.hotkey(" ", "command")` which presses the hotkeys at the same time.
`computer.keyboard.write("hello")` which types the specified text.

For example:

User: Can you compose a new email for me
Assistant: On it. First I will open Mail.
```python
# Open Spotlight
computer.keyboard.hotkey(" ", "command")
# Type Mail
computer.keyboard.write("Mail")
# Press enter
computer.keyboard.write("\n")
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: We are not finished. We will now view the screen.
```python
computer.view()
```
User: The code you ran produced this output: "A mail app with a 'Compose' button". I don't understand it, what does it mean?
Assistant: The output means we can click the Compose button.
```python
computer.mouse.click("Compose")
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: We are finished.

Now, your turn:"""

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
interpreter.computer.import_computer_api = True
interpreter.computer.system_message = ""  # The default will explain how to use the full Computer API, and append this to the system message. For local models, we want more control, so we set this to "". The system message will ONLY be what's above ^

# Misc settings
interpreter.auto_run = True
interpreter.offline = True
interpreter.os = True

# Final message
interpreter.display_message(
    "**Warning:** In this mode, Open Interpreter will not require approval before performing actions. Be ready to close your terminal."
)
interpreter.display_message(
    "\n**Note:** Llama-3 is a relatively weak model, so OS mode is highly experimental. Try using a more powerful model for OS mode with `interpreter --os`."
)
interpreter.display_message("> Model set to `llama3`, experimental OS control enabled")
