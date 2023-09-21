import importlib

def get_code_interpreter(language):
    try:
        # Import the code_interpreter dynamically
        code_interpreter = importlib.import_module(f'languages.{language}')
        return code_interpreter
    except ImportError:
        print(f"{language} is not supported.")
        return None