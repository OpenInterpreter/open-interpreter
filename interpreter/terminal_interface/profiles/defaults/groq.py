"""
This is an Open Interpreter profile. It configures Open Interpreter to run `Llama 3.1 70B` using Groq.

Make sure to set GROQ_API_KEY environment variable to your API key.
"""

from interpreter import interpreter

interpreter.llm.model = "groq/llama-3.1-70b-versatile"

interpreter.computer.import_computer_api = True

interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False
interpreter.llm.context_window = 110000
interpreter.llm.max_tokens = 4096
