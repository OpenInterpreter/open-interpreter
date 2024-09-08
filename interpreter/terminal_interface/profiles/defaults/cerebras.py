"""
This is an Open Interpreter profile to use Cerebras. 

Please set the CEREBRAS_API_KEY environment variable.

See https://inference-docs.cerebras.ai/introduction for more information.
"""

from interpreter import interpreter
import os

# LLM settings
interpreter.llm.api_base = "https://api.cerebras.ai/v1"
interpreter.llm.model = "openai/llama3.1-70b"  # or "openai/Llama-3.1-8B"
interpreter.llm.api_key = os.environ.get("CEREBRAS_API_KEY")
interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False
interpreter.llm.max_tokens = 4096
interpreter.llm.context_window = 8192


# Computer settings
interpreter.computer.import_computer_api = False

# Misc settings
interpreter.offline = False
interpreter.auto_run = False

# Custom Instructions
interpreter.custom_instructions = f"""

    """
