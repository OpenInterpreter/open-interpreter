import sys

# Help message
if "--help" in sys.argv:
    from .misc.help import help_message

    help_message()
    sys.exit(0)

# Version message
if "--version" in sys.argv:
    from interpreter import __version__
    print(f"Open Interpreter {__version__}")
    sys.exit(0)

import argparse
import asyncio
import os
import subprocess
import threading
from typing import Any, Dict

from .misc.get_input import async_get_input
from .misc.spinner import SimpleSpinner
from .profiles import Profile

# Global interpreter object
global_interpreter = None


def _parse_list_arg(value: str) -> list:
    """Parse a comma-separated or JSON-formatted string into a list"""
    if not value:
        return []

    # Try parsing as JSON first
    if value.startswith("["):
        try:
            import json

            return json.loads(value)
        except json.JSONDecodeError:
            pass

    # Fall back to comma-separated parsing
    return [item.strip() for item in value.split(",") if item.strip()]


def _profile_to_arg_params(profile: Profile) -> Dict[str, Dict[str, Any]]:
    """Convert Profile attributes to argparse parameter definitions"""
    return {
        "server": {
            "flags": ["--serve", "-s"],
            "action": "store_true",
            "default": profile.serve,
            "help": "Start the server",
        },
        "model": {
            "flags": ["--model", "-m"],
            "default": profile.model,
            "help": "Specify the model name",
        },
        "provider": {
            "flags": ["--provider"],
            "default": profile.provider,
            "help": "Specify the API provider",
        },
        "api_base": {
            "flags": ["--api-base", "-b"],
            "default": profile.api_base,
            "help": "Specify the API base URL",
        },
        "api_key": {
            "flags": ["--api-key", "-k"],
            "default": profile.api_key,
            "help": "Specify the API key",
        },
        "api_version": {
            "flags": ["--api-version"],
            "default": profile.api_version,
            "help": "Specify the API version",
        },
        "temperature": {
            "flags": ["--temperature"],
            "default": profile.temperature,
            "help": "Specify the temperature",
        },
        "max_tokens": {
            "flags": ["--max-tokens"],
            "default": profile.max_tokens,
            "help": "Specify the maximum number of tokens",
        },
        "tools": {
            "flags": ["--tools"],
            "default": profile.tools,
            "help": "Specify enabled tools (comma-separated or JSON list)",
            "type": _parse_list_arg,
        },
        "allowed_commands": {
            "flags": ["--allowed-commands"],
            "default": profile.allowed_commands,
            "help": "Specify allowed commands (comma-separated or JSON list)",
            "type": _parse_list_arg,
        },
        "allowed_paths": {
            "flags": ["--allowed-paths"],
            "default": profile.allowed_paths,
            "help": "Specify allowed paths (comma-separated or JSON list)",
            "type": _parse_list_arg,
        },
        "auto_run": {
            "flags": ["--auto-run", "-y"],
            "action": "store_true",
            "default": profile.auto_run,
            "help": "Automatically run tools",
        },
        "tool_calling": {
            "flags": ["--no-tool-calling"],
            "action": "store_false",
            "default": profile.tool_calling,
            "dest": "tool_calling",
            "help": "Disable tool calling (enabled by default)",
        },
        "interactive": {
            "flags": ["--interactive"],
            "action": "store_true",
            "default": profile.interactive,
            "help": "Enable interactive mode (enabled by default)",
        },
        "no_interactive": {
            "flags": ["--no-interactive"],
            "action": "store_false",
            "default": profile.interactive,
            "dest": "interactive",
            "help": "Disable interactive mode",
        },
        "system_message": {
            "flags": ["--system-message"],
            "default": profile.system_message,
            "help": "Overwrite system message",
        },
        "custom_instructions": {
            "flags": ["--instructions"],
            "default": profile.instructions,
            "help": "Appended to default system message",
        },
        "input": {
            "flags": ["--input"],
            "default": profile.input,
            "help": "Pre-fill first user message",
        },
        "max_turns": {
            "flags": ["--max-turns"],
            "type": int,
            "default": profile.max_turns,
            "help": "Set maximum conversation turns, defaults to -1 (unlimited)",
        },
        "profile": {
            "flags": ["--profile"],
            "default": profile.profile_path,
            "help": "Path to profile configuration",
            "metavar": "PATH",
        },
        "debug": {
            "flags": ["--debug", "-d"],
            "action": "store_true",
            "default": profile.debug,
            "help": "Run in debug mode",
        },
    }


def load_interpreter(args):
    from .interpreter import Interpreter

    interpreter = Interpreter()
    for key, value in args.items():
        if hasattr(interpreter, key) and value is not None:
            setattr(interpreter, key, value)
    return interpreter


async def async_load_interpreter(args):
    return load_interpreter(args)


async def async_main(args):
    global global_interpreter

    if (
        args["input"] is None
        and sys.stdin.isatty()
        and sys.argv[0].endswith("interpreter")
    ):
        from .misc.welcome import welcome_message

        welcome_message()

    if args["input"] is None and (
        sys.stdin.isatty() and args.get("no_interactive") is not True
    ):
        # Load the interpreter in a separate thread
        def load_interpreter_thread(args):
            loop = asyncio.new_event_loop()
            global global_interpreter
            global_interpreter = loop.run_until_complete(async_load_interpreter(args))

        thread = threading.Thread(target=load_interpreter_thread, args=(args,))
        thread.start()

        # Get user input
        message = await async_get_input()

        # Wait for the thread to finish
        thread.join()
    else:
        spinner = SimpleSpinner()
        spinner.start()
        global_interpreter = await async_load_interpreter(args)
        message = args["input"] if args["input"] is not None else sys.stdin.read()
        spinner.stop()
    print()
    global_interpreter.messages = [{"role": "user", "content": message}]
    try:
        async for _ in global_interpreter.async_respond():
            pass
    except KeyboardInterrupt:
        global_interpreter._spinner.stop()
    except asyncio.CancelledError:
        global_interpreter._spinner.stop()
    print()

    if global_interpreter.interactive:
        await global_interpreter.async_chat()


def parse_args():
    profile = Profile()
    default_profile_path = os.path.expanduser(Profile.DEFAULT_PROFILE_PATH)
    if os.path.exists(default_profile_path):
        profile.load(Profile.DEFAULT_PROFILE_PATH)

    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("--help", "-h", action="store_true", help="Show help")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument(
        "--profiles", action="store_true", help="Open profiles directory"
    )
    parser.add_argument(
        "--save", action="store", metavar="PATH", help="Save profile to path"
    )

    arg_params = _profile_to_arg_params(profile)
    for param in arg_params.values():
        flags = param.pop("flags")
        parser.add_argument(*flags, **param)

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return {**vars(parser.parse_args([])), "input": "i " + " ".join(sys.argv[1:])}

    args = vars(parser.parse_args())

    if args["profiles"]:
        profile_dir = os.path.expanduser(Profile.DEFAULT_PROFILE_FOLDER)
        if sys.platform == "win32":
            os.startfile(profile_dir)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, profile_dir])
        sys.exit(0)

    if args["profile"] != profile.profile_path:
        profile.load(args["profile"])
        for key, value in vars(profile).items():
            if key in args and args[key] is None:
                args[key] = value

    if args["save"]:
        # Apply CLI args to profile
        for key, value in args.items():
            if key in vars(profile) and value is not None:
                setattr(profile, key, value)
        profile.save(args["save"])
        sys.exit(0)

    return args


def main():
    """Entry point for the CLI"""
    try:
        args = parse_args()

        if args["serve"]:
            print("Starting OpenAI-compatible server...")
            global_interpreter = load_interpreter(args)
            global_interpreter.server()
            return

        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        sys.exit(0)
    except asyncio.CancelledError:
        sys.exit(0)


if __name__ == "__main__":
    main()
