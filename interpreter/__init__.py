from .interpreter import Interpreter

# Create an instance of the Interpreter class
interpreter = Interpreter()

# Expose the methods of the Interpreter instance as package-level functions
chat = interpreter.chat
reset = interpreter.reset
load = interpreter.load

# Expose the openai_api_key attribute as a package-level variable with only setter
def set_openai_api_key(key):
    interpreter.openai_api_key = key

# Assign the setter to the openai_api_key at package level
openai_api_key = property(None, set_openai_api_key)