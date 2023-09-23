import argparse
import subprocess
import os
import platform
import appdirs
from ..utils.display_markdown_message import display_markdown_message
from ..terminal_interface.conversation_navigator import conversation_navigator

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
        "help_text": "optional temperature setting for the language model",
        "type": float
    },
    {
        "name": "context_window",
        "nickname": "c",
        "help_text": "optional context window size for the language model",
        "type": int
    },
    {
        "name": "max_tokens",
        "nickname": "x",
        "help_text": "optional maximum number of tokens for the language model",
        "type": int
    },
    {
        "name": "max_budget",
        "nickname": "b",
        "help_text": "optionally set the max budget (in USD) for your llm calls",
        "type": float
    },
    {
        "name": "api_base",
        "nickname": "ab",
        "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
        "type": str
    },
    {
        "name": "api_key",
        "nickname": "ak",
        "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
        "type": str
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
    parser.add_argument('--conversations', dest='conversations', action='store_true', help='list conversations to resume')
    parser.add_argument('-f', '--fast', dest='fast', action='store_true', help='(depracated) runs `interpreter --model gpt-3.5-turbo`')

    args = parser.parse_args()

    # This should be pushed into an open_config.py util
    # If --config is used, open the config.yaml file in the Open Interpreter folder of the user's config dir
    if args.config:
        config_path = os.path.join(appdirs.user_config_dir(), 'Open Interpreter', 'config.yaml')
        print(f"Opening `{config_path}`...")
        # Use the default system editor to open the file
        if platform.system() == 'Windows':
            os.startfile(config_path)  # This will open the file with the default application, e.g., Notepad
        else:
            try:
                # Try using xdg-open on non-Windows platforms
                subprocess.call(['xdg-open', config_path])
            except FileNotFoundError:
                # Fallback to using 'open' on macOS if 'xdg-open' is not available
                subprocess.call(['open', config_path])
    
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

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return
    
    # Depracated --fast
    if args.fast:
        # This will cause the terminal_interface to walk the user through setting up a local LLM
        interpreter.model = "gpt-3.5-turbo"
        print("`interpreter --fast` is depracated and will be removed in the next version. Please use `interpreter --model gpt-3.5-turbo`")

    interpreter.chat()