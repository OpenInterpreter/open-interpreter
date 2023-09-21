import argparse
import subprocess
import os
import appdirs

arguments = [
    {
        "name": "system_message",
        "help_text": "prompt / custom instructions for the language model",
        "type": str
    },
    {
        "name": "local",
        "help_text": "run in local mode",
        "type": bool
    },
    {
        "name": "auto_run",
        "help_text": "automatically run the interpreter",
        "type": bool
    },
    {
        "name": "debug_mode",
        "help_text": "run in debug mode",
        "type": bool
    },
    {
        "name": "model",
        "help_text": "model to use for the language model",
        "type": str
    },
    {
        "name": "temperature",
        "help_text": "temperature setting for the language model",
        "type": float
    },
    {
        "name": "context_window",
        "help_text": "context window size for the language model",
        "type": int
    },
    {
        "name": "max_tokens",
        "help_text": "maximum number of tokens for the language model",
        "type": int
    }
]

def cli(interpreter):

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        if arg["type"] == bool:
            parser.add_argument(f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], action='store_true')
        else:
            parser.add_argument(f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], type=arg["type"])

    # Add special --config argument
    parser.add_argument('--config', dest='config', action='store_true', help='open config.yaml file in text editor')

    args = parser.parse_args()

    # If --config is used, open the config.yaml file in the user's favorite text editor
    if args.config:
        config_path = os.path.join(appdirs.user_config_dir(), 'config.yaml')
        editor = os.environ.get('EDITOR','vi') # default to 'vi' if no editor set
        subprocess.call([editor, config_path])
        return

    # Set attributes on interpreter
    for attr_name, attr_value in vars(args).items():
        if attr_value is not None:
            setattr(interpreter, attr_name, attr_value)

    interpreter.chat()