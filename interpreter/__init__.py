import sys
from .core.core import Interpreter
from .cli.cli import cli



def create_interpreter(**kwargs):
    """
    Factory function to create an instance of Interpreter with the provided keyword arguments.
    
    Parameters:
        **kwargs: Keyword arguments to be set as attributes in the Interpreter instance.
    
    Returns:
        An instance of Interpreter initialized with the provided arguments.
    """
    # Create a new interpreter instance
    new_interpreter = Interpreter()
    
    # Iterate through the provided keyword arguments
    for key, value in kwargs.items():
        # Check if the attribute exists in the interpreter
        if hasattr(new_interpreter, key):
            # Check if the provided value is of the correct type
            if isinstance(value, type(getattr(new_interpreter, key))):
                setattr(new_interpreter, key, value)
            else:
                print(
                    f"Type mismatch: '{key}' should be of type {type(getattr(new_interpreter, key))}. Using the default value instead.")
                
        else:
            print(
                f"Unknown attribute: '{key}'. Ignoring.")
            
    
    return new_interpreter



#     ____                      ____      __                            __           
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /    
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/     
#      /_/                                         /_/                               