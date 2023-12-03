import argparse
import os
import platform
import subprocess

import pkg_resources

from .conversation_navigator import conversation_navigator
from .utils.check_for_update import check_for_update
from .utils.display_markdown_message import display_markdown_message
from .utils.get_config import get_config_path
from .validate_llm_settings import validate_llm_settings

arguments = [
    {
        "name": "system_message",
        "nickname": "s",
        "help_text": "prompt / custom instructions for the language model",
        "type": str,
    },
    {
        "name": "local",
        "nickname": "l",
        "help_text": "experimentally run the language model locally (via LM Studio)",
        "type": bool,
    },
    {
        "name": "auto_run",
        "nickname": "y",
        "help_text": "automatically run generated code",
        "type": bool,
    },
    {
        "name": "debug_mode",
        "nickname": "d",
        "help_text": "run in debug mode",
        "type": bool,
    },
    {
        "name": "disable_procedures",
        "nickname": "dp",
        "help_text": "disables procedures (RAG of some common OI use-cases). disable to shrink system message. auto-disabled for non-OpenAI models",
        "type": bool,
    },
    {
        "name": "model",
        "nickname": "m",
        "help_text": "language model to use",
        "type": str,
    },
    {
        "name": "temperature",
        "nickname": "t",
        "help_text": "optional temperature setting for the language model",
        "type": float,
    },
    {
        "name": "context_window",
        "nickname": "c",
        "help_text": "optional context window size for the language model",
        "type": int,
    },
    {
        "name": "max_tokens",
        "nickname": "x",
        "help_text": "optional maximum number of tokens for the language model",
        "type": int,
    },
    {
        "name": "max_output",
        "nickname": "xo",
        "help_text": "optional maximum number of characters for code outputs",
        "type": int,
    },
    {
        "name": "max_budget",
        "nickname": "b",
        "help_text": "optionally set the max budget (in USD) for your llm calls",
        "type": float,
    },
    {
        "name": "api_base",
        "nickname": "ab",
        "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
        "type": str,
    },
    {
        "name": "api_key",
        "nickname": "ak",
        "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
        "type": str,
    },
    {
        "name": "safe_mode",
        "nickname": "safe",
        "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
        "type": str,
        "choices": ["off", "ask", "auto"],
        "default": "off",
    },
    {
        "name": "config_file",
        "nickname": "cf",
        "help_text": "optionally set a custom config file to use",
        "type": str,
    },
    {
        "name": "vision",
        "nickname": "v",
        "help_text": "experimentally use vision for supported languages (HTML)",
        "type": bool,
    },
]


def start_terminal_interface(interpreter):
    """
    Meant to be used from the command line. Parses arguments, starts OI's terminal interface.
    """

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        if arg["type"] == bool:
            parser.add_argument(
                f'-{arg["nickname"]}',
                f'--{arg["name"]}',
                dest=arg["name"],
                help=arg["help_text"],
                action="store_true",
                default=None,
            )
        else:
            choices = arg["choices"] if "choices" in arg else None
            default = arg["default"] if "default" in arg else None

            parser.add_argument(
                f'-{arg["nickname"]}',
                f'--{arg["name"]}',
                dest=arg["name"],
                help=arg["help_text"],
                type=arg["type"],
                choices=choices,
                default=default,
            )

    # Add special arguments
    parser.add_argument(
        "--config",
        dest="config",
        action="store_true",
        help="open config.yaml file in text editor",
    )
    parser.add_argument(
        "--conversations",
        dest="conversations",
        action="store_true",
        help="list conversations to resume",
    )
    parser.add_argument(
        "-f",
        "--fast",
        dest="fast",
        action="store_true",
        help="run `interpreter --model gpt-3.5-turbo`",
    )
    parser.add_argument(
        "--version",
        dest="version",
        action="store_true",
        help="get Open Interpreter's version number",
    )

    args = parser.parse_args()

    # This should be pushed into an open_config.py util
    # If --config is used, open the config.yaml file in the Open Interpreter folder of the user's config dir
    if args.config:
        if args.config_file:
            config_file = get_config_path(args.config_file)
        else:
            config_file = get_config_path()

        print(f"Opening `{config_file}`...")

        # Use the default system editor to open the file
        if platform.system() == "Windows":
            os.startfile(
                config_file
            )  # This will open the file with the default application, e.g., Notepad
        else:
            try:
                # Try using xdg-open on non-Windows platforms
                subprocess.call(["xdg-open", config_file])
            except FileNotFoundError:
                # Fallback to using 'open' on macOS if 'xdg-open' is not available
                subprocess.call(["open", config_file])
        return

    if args.local:
        # Default local (LM studio) attributes
        interpreter.system_message = "You are an AI."
        interpreter.model = (
            "openai/" + interpreter.model
        )  # This tells LiteLLM it's an OpenAI compatible server
        interpreter.api_base = "http://localhost:1234/v1"
        interpreter.max_tokens = 1000
        interpreter.context_window = 3000
        interpreter.api_key = "0"

        display_markdown_message(
            """
> Open Interpreter's local mode is powered by **`LM Studio`**.


You will need to run **LM Studio** in the background.

1. Download **LM Studio** from [https://lmstudio.ai/](https://lmstudio.ai/) then start it.
2. Select a language model then click **Download**.
3. Click the **<->** button on the left (below the chat button).
4. Select your model at the top, then click **Start Server**.


Once the server is running, you can begin your conversation below.

> **Warning:** This feature is highly experimental.
> Don't expect `gpt-3.5` / `gpt-4` level quality, speed, or reliability yet!

"""
        )

    # Set attributes on interpreter
    for attr_name, attr_value in vars(args).items():
        # Ignore things that aren't possible attributes on interpreter
        if attr_value is not None and hasattr(interpreter, attr_name):
            # If the user has provided a config file, load it and extend interpreter's configuration
            if attr_name == "config_file":
                user_config = get_config_path(attr_value)
                interpreter.config_file = user_config
                interpreter.extend_config(config_path=user_config)
            else:
                setattr(interpreter, attr_name, attr_value)

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and (
        interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto"
    ):
        setattr(interpreter, "auto_run", False)

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    if args.version:
        version = pkg_resources.get_distribution("open-interpreter").version
        update_name = "New Computer"  # Change this with each major update
        print(f"Open Interpreter {version} {update_name}")
        return

    if args.fast:
        interpreter.model = "gpt-3.5-turbo"

    if args.vision:
        interpreter.vision = True
        interpreter.model = "gpt-4-vision-preview"
        interpreter.system_message += "\nThe user will show you an image of the code you write. You can view images directly. Be sure to actually write a markdown code block for almost every user request! Almost EVERY message should include a markdown code block. Do not end your message prematurely!\n\nFor HTML: This will be run STATELESSLY. You may NEVER write '<!-- previous code here... --!>' or `<!-- header will go here -->` or anything like that. It is CRITICAL TO NEVER WRITE PLACEHOLDERS. Placeholders will BREAK it. You must write the FULL HTML CODE EVERY TIME. Therefore you cannot write HTML piecemeal—write all the HTML, CSS, and possibly Javascript **in one step, in one code block**. The user will help you review it visually.\nIf the user submits a filepath, you will also see the image. The filepath and user image will both be in the user's message."
        interpreter.function_calling_llm = False
        interpreter.context_window = 110000
        interpreter.max_tokens = 4096

        display_markdown_message("> `Vision` enabled **(experimental)**\n")

    # Check for update
    try:
        if not interpreter.local:
            # This should actually be pushed into the utility
            if check_for_update():
                display_markdown_message(
                    "> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---"
                )
    except:
        # Doesn't matter
        pass

    if not interpreter.local and interpreter.model == "gpt-4-1106-preview":
        if interpreter.context_window is None:
            interpreter.context_window = 128000
        if interpreter.max_tokens is None:
            interpreter.max_tokens = 4096
        if interpreter.function_calling_llm is None:
            interpreter.function_calling_llm = True

    if not interpreter.local and interpreter.model == "gpt-3.5-turbo-1106":
        if interpreter.context_window is None:
            interpreter.context_window = 16000
        if interpreter.max_tokens is None:
            interpreter.max_tokens = 4096
        if interpreter.function_calling_llm is None:
            interpreter.function_calling_llm = True

    validate_llm_settings(interpreter)

    interpreter.chat()
