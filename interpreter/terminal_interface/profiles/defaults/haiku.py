"""
This is an Open Interpreter profile. It configures Open Interpreter to run Anthropic's `Claude 3.5 Haiku` model.

Make sure to set ANTHROPIC_API_KEY environment variable to your API key.

This profile is optimized for quick, concise responses while maintaining high accuracy.
Learn more about Claude 3.5 Haiku: https://www.anthropic.com/claude/haiku
"""

# Configure Open Interpreter
from interpreter import interpreter

interpreter.llm.model = "anthropic/claude-3-5-haiku-20241022"
interpreter.computer.import_computer_api = True
interpreter.llm.supports_functions = True
interpreter.llm.supports_vision = False
interpreter.llm.context_window = 200000
interpreter.llm.max_tokens = 4096
