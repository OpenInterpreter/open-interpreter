import argparse
import subprocess
import os
import appdirs
from ..utils.display_markdown_message import display_markdown_message

arguments = [
    {
        "name": "system_message",
        "nickname": "s",
        "help_text": "prompt / custom instructions for the language model",
        "type": str
    },
    {
        "name": "local",
        "nickname": "l",
        "help_text": "run in local mode",
        "type": bool
    },
    {
        "name": "auto_run",
        "nickname": "y",
        "help_text": "automatically run the interpreter",
        "type": bool
    },
    {
        "name": "debug_mode",
        "nickname": "d",
        "help_text": "run in debug mode",
        "type": bool
    },
    {
        "name": "model",
        "nickname": "m",
        "help_text": "model to use for the language model",
        "type": str
    },
    {
        "name": "temperature",
        "nickname": "t",
        "help_text": "temperature setting for the language model",
        "type": float
    },
    {
        "name": "context_window",
        "nickname": "c",
        "help_text": "context window size for the language model",
        "type": int
    },
    {
        "name": "max_tokens",
        "nickname": "x",
        "help_text": "maximum number of tokens for the language model",
        "type": int
    }
]

def cli(interpreter):

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        if arg["type"] == bool:
            parser.add_argument(f'-{arg["nickname"]}', f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], action='store_true')
        else:
            parser.add_argument(f'-{arg["nickname"]}', f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], type=arg["type"])

    # Add special arguments
    parser.add_argument('--config', dest='config', action='store_true', help='open config.yaml file in text editor')
    parser.add_argument('--models', dest='models', action='store_true', help='list avaliable models')

    args = parser.parse_args()

    # If --config is used, open the config.yaml file in the Open Interpreter folder of the user's config dir
    if args.config:
        config_path = os.path.join(appdirs.user_config_dir(), 'Open Interpreter', 'config.yaml')
        print(f"Opening `{config_path}`...")
        # Use the default system editor to open the file
        subprocess.call(['open', config_path])
        return
    
    # TODO Implement model explorer
    """
    # If --models is used, list models
    if args.models:
        # If they pick a model, set model to that then proceed
        args.model = model_explorer()
    """

    # Set attributes on interpreter
    for attr_name, attr_value in vars(args).items():
        # Ignore things that aren't possible attributes on interpreter
        if attr_value is not None and hasattr(interpreter, attr_name):
            setattr(interpreter, attr_name, attr_value)

    # Default to CodeLlama if --local is on but --model is unset
    if interpreter.local and args.model is None:
        # This will cause the terminal_interface to walk the user through setting up a local LLM
        interpreter.model = ""

    interpreter.chat()