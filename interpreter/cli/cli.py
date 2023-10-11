import argparse
import subprocess
import os
import platform
import pkg_resources
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
    },
    {
        "name": "safe_mode",
        "nickname": "safe",
        "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
        "type": str,
        "choices": ["off", "ask", "auto"]
    },
    {
        "name": "n_threads",
        "nickname": "thr",
        "help_text": "number of threads on cpu",
        "type": int
    },
    {
        "name": "n_gpu_layers",
        "nickname": "ngl",
        "help_text": "number of layers to offload to gpu",
        "type": int
    },
    {
        "name": "gguf_quality",
        "nickname": "q",
        "help_text": "(experimental) value from 0-1 which will select the gguf quality/quantization level. lower = smaller, faster, more quantized",
        "type": float,
    }
]

def cli(interpreter):

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        if arg["type"] == bool:
            parser.add_argument(f'-{arg["nickname"]}', f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], action='store_true', default=None)
        else:
            choices = arg["choices"] if "choices" in arg else None
            default = arg["default"] if "default" in arg else None

            parser.add_argument(f'-{arg["nickname"]}', f'--{arg["name"]}', dest=arg["name"], help=arg["help_text"], type=arg["type"], choices=choices, default=default)

    # Add special arguments
    parser.add_argument('--config', dest='config', action='store_true', help='open config.yaml file in text editor')
    parser.add_argument('--conversations', dest='conversations', action='store_true', help='list conversations to resume')
    parser.add_argument('-f', '--fast', dest='fast', action='store_true', help='(depracated) runs `interpreter --model gpt-3.5-turbo`')
    parser.add_argument('--version', dest='version', action='store_true', help="get Open Interpreter's version number")

    # TODO: Implement model explorer
    # parser.add_argument('--models', dest='models', action='store_true', help='list avaliable models')

    args = parser.parse_args()

    # This should be pushed into an open_config.py util
    # If --config is used, open the config.yaml file in the Open Interpreter folder of the user's config dir
    if args.config:
        config_dir = appdirs.user_config_dir("Open Interpreter")
        config_path = os.path.join(config_dir, 'config.yaml')
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

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and not interpreter.safe_mode == "off":
        setattr(interpreter, "auto_run", False)

    # Default to CodeLlama if --local is on but --model is unset
    if interpreter.local and args.model is None:
        # This will cause the terminal_interface to walk the user through setting up a local LLM
        interpreter.model = ""

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return
    
    if args.version:
        version = pkg_resources.get_distribution("open-interpreter").version
        print(f"Open Interpreter {version}")
        return
    
    # Depracated --fast
    if args.fast:
        # This will cause the terminal_interface to walk the user through setting up a local LLM
        interpreter.model = "gpt-3.5-turbo"
        print("`interpreter --fast` is depracated and will be removed in the next version. Please use `interpreter --model gpt-3.5-turbo`")

    interpreter.chat()