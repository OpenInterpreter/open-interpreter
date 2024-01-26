import argparse
import sys
import time

import pkg_resources

from ..core.core import OpenInterpreter
from .config.config import configure, open_config_dir, reset_config
from .conversation_navigator import conversation_navigator
from .utils.check_for_update import check_for_update
from .utils.display_markdown_message import display_markdown_message
from .validate_llm_settings import validate_llm_settings


def start_terminal_interface(interpreter):
    """
    Meant to be used from the command line. Parses arguments, starts OI's terminal interface.
    """

    arguments = [
        # Profiles coming soon— after we seperate core from TUI
        {
            "name": "config",
            "nickname": "c",
            "help_text": "name of config file. run `--config` without an argument to open config directory",
            "type": str,
            "default": "default.yaml",
            "nargs": "?",  # This means you can pass in nothing if you want
        },
        {
            "name": "custom_instructions",
            "nickname": "ci",
            "help_text": "custom instructions for the language model. will be appended to the system_message",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "custom_instructions"},
        },
        {
            "name": "system_message",
            "nickname": "s",
            "help_text": "(we don't recommend changing this) base prompt for the language model",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "system_message"},
        },
        {
            "name": "auto_run",
            "nickname": "y",
            "help_text": "automatically run generated code",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "auto_run"},
        },
        {
            "name": "verbose",
            "nickname": "v",
            "help_text": "print detailed logs",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "verbose"},
        },
        {
            "name": "model",
            "nickname": "m",
            "help_text": "language model to use",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "model"},
        },
        {
            "name": "temperature",
            "nickname": "t",
            "help_text": "optional temperature setting for the language model",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "temperature"},
        },
        {
            "name": "llm_supports_vision",
            "nickname": "lsv",
            "help_text": "inform OI that your model supports vision, and can recieve vision inputs",
            "type": bool,
            "action": argparse.BooleanOptionalAction,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_vision"},
        },
        {
            "name": "llm_supports_functions",
            "nickname": "lsf",
            "help_text": "inform OI that your model supports OpenAI-style functions, and can make function calls",
            "type": bool,
            "action": argparse.BooleanOptionalAction,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_functions"},
        },
        {
            "name": "context_window",
            "nickname": "cw",
            "help_text": "optional context window size for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "context_window"},
        },
        {
            "name": "max_tokens",
            "nickname": "x",
            "help_text": "optional maximum number of tokens for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "max_tokens"},
        },
        {
            "name": "max_budget",
            "nickname": "b",
            "help_text": "optionally set the max budget (in USD) for your llm calls",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "max_budget"},
        },
        {
            "name": "api_base",
            "nickname": "ab",
            "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_base"},
        },
        {
            "name": "api_key",
            "nickname": "ak",
            "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_key"},
        },
        {
            "name": "api_version",
            "nickname": "av",
            "help_text": "optionally set the API version for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_version"},
        },
        {
            "name": "max_output",
            "nickname": "xo",
            "help_text": "optional maximum number of characters for code outputs",
            "type": int,
            "attribute": {"object": interpreter, "attr_name": "max_output"},
        },
        {
            "name": "force_task_completion",
            "nickname": "fc",
            "help_text": "runs OI in a loop, requiring it to admit to completing/failing task",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "force_task_completion"},
        },
        {
            "name": "disable_telemetry",
            "nickname": "dt",
            "help_text": "disables sending of basic anonymous usage stats",
            "type": bool,
            "default": True,
            "action": "store_false",
            "attribute": {"object": interpreter, "attr_name": "anonymous_telemetry"},
        },
        {
            "name": "offline",
            "nickname": "o",
            "help_text": "turns off all online features (except the language model, if it's hosted)",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "offline"},
        },
        {
            "name": "speak_messages",
            "nickname": "sm",
            "help_text": "(Mac only, experimental) use the applescript `say` command to read messages aloud",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "speak_messages"},
        },
        {
            "name": "safe_mode",
            "nickname": "safe",
            "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
            "type": str,
            "choices": ["off", "ask", "auto"],
            "default": "off",
            "attribute": {"object": interpreter, "attr_name": "safe_mode"},
        },
        {
            "name": "fast",
            "nickname": "f",
            "help_text": "runs `interpreter --model gpt-3.5-turbo` and asks OI to be extremely concise",
            "type": bool,
        },
        {
            "name": "local",
            "nickname": "l",
            "help_text": "experimentally run the LLM locally via LM Studio (this changes many more settings than `--offline`)",
            "type": bool,
        },
        {
            "name": "vision",
            "nickname": "vi",
            "help_text": "experimentally use vision for supported languages",
            "type": bool,
        },
        {
            "name": "os",
            "nickname": "os",
            "help_text": "experimentally let Open Interpreter control your mouse and keyboard",
            "type": bool,
        },
        # Special commands
        {
            "name": "reset_config",
            "help_text": "reset a config file. run `--reset_config` without an argument to reset all default configs",
            "type": str,
            "default": "NOT_PROVIDED",
            "nargs": "?",  # This means you can pass in nothing if you want
        },
        {
            "name": "conversations",
            "help_text": "list conversations to resume",
            "type": bool,
        },
        {
            "name": "version",
            "help_text": "get Open Interpreter's version number",
            "type": bool,
        },
    ]

    # Check for deprecated flags before parsing arguments
    deprecated_flags = {
        "--debug_mode": "--verbose",
        "-d": "-v",
    }

    for old_flag, new_flag in deprecated_flags.items():
        if old_flag in sys.argv:
            print(f"\n`{old_flag}` has been renamed to `{new_flag}`.\n")
            time.sleep(1.5)
            sys.argv.remove(old_flag)
            sys.argv.append(new_flag)

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        action = arg.get("action", "store_true")
        nickname = arg.get("nickname")
        default = arg.get("default")

        if arg["type"] == bool:
            if nickname:
                parser.add_argument(
                    f"-{nickname}",
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=default,
                )
            else:
                parser.add_argument(
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=default,
                )
        else:
            choices = arg.get("choices")

            if nickname:
                parser.add_argument(
                    f"-{nickname}",
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    type=arg["type"],
                    choices=choices,
                    default=default,
                    nargs=arg.get("nargs"),
                )
            else:
                parser.add_argument(
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    type=arg["type"],
                    choices=choices,
                    default=default,
                    nargs=arg.get("nargs"),
                )

    args = parser.parse_args()

    if args.config == None:  # --config was provided without a value
        open_config_dir()
        return

    if args.reset_config != "NOT_PROVIDED":
        reset_config(
            args.reset_config
        )  # This will be None if they just ran `--reset_config`
        return

    if args.version:
        version = pkg_resources.get_distribution("open-interpreter").version
        update_name = "New Computer Update"  # Change this with each major update
        print(f"Open Interpreter {version} {update_name}")
        return

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and (
        interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto"
    ):
        setattr(interpreter, "auto_run", False)

    if args.fast:
        if not (args.local or args.vision or args.os):
            args.model = "gpt-3.5-turbo"
        interpreter.system_message += "\n\nThe user has set you to FAST mode. **No talk, just code.** Be as brief as possible. No comments, no unnecessary messages. Assume as much as possible, rarely ask the user for clarification. Once the task has been completed, say 'The task is done.'"

    if args.vision:
        interpreter.llm.supports_vision = True

        if not args.model:
            # This will cause it to override the config, which is what we want
            args.model = "gpt-4-vision-preview"

        interpreter.system_message += "\nThe user will show you an image of the code you write. You can view images directly.\n\nFor HTML: This will be run STATELESSLY. You may NEVER write '<!-- previous code here... --!>' or `<!-- header will go here -->` or anything like that. It is CRITICAL TO NEVER WRITE PLACEHOLDERS. Placeholders will BREAK it. You must write the FULL HTML CODE EVERY TIME. Therefore you cannot write HTML piecemeal—write all the HTML, CSS, and possibly Javascript **in one step, in one code block**. The user will help you review it visually.\nIf the user submits a filepath, you will also see the image. The filepath and user image will both be in the user's message.\n\nIf you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you."
        interpreter.llm.supports_functions = False
        interpreter.llm.context_window = 110000
        interpreter.llm.max_tokens = 4096
        interpreter.force_task_completion = True

        if (
            not args.local
        ):  # We'll display this in a moment— after local's message prints
            display_markdown_message("> `Vision` enabled (experimental)\n")

    if args.os:
        args.config = "os.py"

    if args.local:
        args.config = "local.py"

    ### Set attributes on interpreter, so that a config script can read the arguments passed in via the CLI

    set_attributes(args, arguments)

    ### Apply config file

    interpreter = configure(interpreter, args.config)

    ### Set attributes on interpreter, because the arguments passed in via the CLI should override config

    set_attributes(args, arguments)

    ### Set some helpful settings we know are likely to be true

    if interpreter.llm.model == "gpt-4-1106-preview":
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 128000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = True

    if interpreter.llm.model == "gpt-3.5-turbo-1106":
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 16000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = True

    ### Check for update

    try:
        if not interpreter.offline:
            # This message should actually be pushed into the utility
            if check_for_update():
                display_markdown_message(
                    "> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---"
                )
    except:
        # Doesn't matter
        pass

    # If we've set a custom api base, we want it to be sent in an openai compatible way.
    # So we need to tell LiteLLM to do this by changing the model name:
    if interpreter.llm.api_base:
        if (
            not interpreter.llm.model.lower().startswith("openai/")
            and not interpreter.llm.model.lower().startswith("azure/")
            and not interpreter.llm.model.lower().startswith("ollama")
        ):
            interpreter.llm.model = "openai/" + interpreter.llm.model

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    validate_llm_settings(interpreter)

    interpreter.in_terminal_interface = True

    interpreter.chat()


def set_attributes(args, arguments):
    for argument_name, argument_value in vars(args).items():
        if argument_value is not None:
            argument_dictionary = [a for a in arguments if a["name"] == argument_name]
            if len(argument_dictionary) > 0:
                argument_dictionary = argument_dictionary[0]
                if "attribute" in argument_dictionary:
                    attr_dict = argument_dictionary["attribute"]
                    setattr(attr_dict["object"], attr_dict["attr_name"], argument_value)

                    if args.verbose:
                        print(
                            f"Setting attribute {attr_dict['attr_name']} on {attr_dict['object'].__class__.__name__.lower()} to '{argument_value}'..."
                        )


def main():
    interpreter = OpenInterpreter()
    try:
        start_terminal_interface(interpreter)
    except KeyboardInterrupt:
        pass
