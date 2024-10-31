"""
This is an Open Interpreter profile. It configures Open Interpreter to run Gemini 1.5 Pro.

Make sure to set GEMINI_API_KEY environment variable to your API key.
"""

from interpreter import interpreter

interpreter.llm.model = "gemini/gemini-1.5-pro"
interpreter.llm.supports_functions = True
interpreter.llm.context_window = 2000000
interpreter.llm.max_tokens = 4096
