"""
This is an Open Interpreter profile for using Llama 3.2:3b served locally by Cortex.

This profile configures Open Interpreter to use a locally hosted Llama 3.2 model through Cortex.

Run `cortex start` before running Open Interpreter.

More information about Cortex: https://cortex.so/docs/

"""

from interpreter import interpreter


# Update the model to match t
interpreter.llm.model = "llama3.2:3b-gguf-q8-0"
interpreter.llm.context_window = 8192
interpreter.llm.max_tokens = 4096
interpreter.llm.api_base = "http://127.0.0.1:39281/v1"
interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False

interpreter.offline = True
interpreter.loop = True
interpreter.auto_run = False
