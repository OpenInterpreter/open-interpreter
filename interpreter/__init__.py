from .interpreter import Interpreter

# Create an instance of the Interpreter class
interpreter = Interpreter()

# Expose the methods of the Interpreter instance as package-level functions
chat = interpreter.chat
reset = interpreter.reset
load = interpreter.load

# Expose the openai_api_key attribute as a package-level variable
openai_api_key = interpreter.openai_api_key