"""
This is the template Open Interpreter profile.

A starting point for creating a new profile.

Learn about all the available settings - https://docs.openinterpreter.com/settings/all-settings

"""

# Import the interpreter
from interpreter import interpreter

# You can import other libraries too
from datetime import date

# You can set variables
today = date.today()

# LLM Settings
interpreter.llm.model = "groq/llama-3.1-70b-versatile"
interpreter.llm.context_window = 110000
interpreter.llm.max_tokens = 4096
interpreter.llm.api_base = "https://api.example.com"
interpreter.llm.api_key = "your_api_key_here"
interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False


# Interpreter Settings
interpreter.offline = False
interpreter.loop = True
interpreter.auto_run = False

# Toggle OS Mode - https://docs.openinterpreter.com/guides/os-mode
interpreter.os = False

# Import Computer API - https://docs.openinterpreter.com/code-execution/computer-api
interpreter.computer.import_computer_api = True


# Set Custom Instructions to improve your Interpreter's performance at a given task
interpreter.custom_instructions = f"""
    Today's date is {today}.
    """
