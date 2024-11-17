import argparse
import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from .misc.spinner import SimpleSpinner
from .profiles import Profile


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
        # Server configuration
        "server": {
            "flags": ["--serve", "-s"],
            "action": "store_true",
            "default": profile.serve,
            "help": "Start the server",
        },
        # Model and API configuration
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
        # Tool configuration
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
        # Behavior configuration
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
        },
        # Debugging
        "debug": {
            "flags": ["--debug", "-d"],
            "action": "store_true",
            "default": profile.debug,
            "help": "Run in debug mode",
        },
    }


def parse_args():
    # Create profile with defaults
    profile = Profile()
    # Load from default location if it exists
    default_profile_path = os.path.expanduser(Profile.DEFAULT_PROFILE_PATH)
    if os.path.exists(default_profile_path):
        profile.load(Profile.DEFAULT_PROFILE_PATH)

    parser = argparse.ArgumentParser(add_help=False)

    # Hidden arguments
    parser.add_argument("--help", "-h", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input", action="store", help=argparse.SUPPRESS)
    parser.add_argument(
        "--profiles", action="store_true", help="Open profiles directory"
    )

    # Add arguments programmatically from config
    arg_params = _profile_to_arg_params(profile)
    for param in arg_params.values():
        flags = param.pop("flags")
        parser.add_argument(*flags, **param)

    # If second argument exists and doesn't start with '-', treat as input message
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return {**vars(parser.parse_args([])), "input": "i " + " ".join(sys.argv[1:])}

    args = vars(parser.parse_args())

    # Handle profiles flag
    if args["profiles"]:
        profile_dir = os.path.expanduser(Profile.DEFAULT_PROFILE_FOLDER)
        if sys.platform == "win32":
            os.startfile(profile_dir)
        else:
            import subprocess

            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, profile_dir])
        sys.exit(0)

    # If a different profile is specified, load it
    if args["profile"] != profile.profile_path:
        profile.load(args["profile"])
        # Update any values that weren't explicitly set in CLI
        for key, value in vars(profile).items():
            if key in args and args[key] is None:
                args[key] = value

    return args


def main():
    args = parse_args()

    def load_interpreter():
        global interpreter
        from .interpreter import Interpreter

        interpreter = Interpreter()
        # Configure interpreter from args
        for key, value in args.items():
            if hasattr(interpreter, key) and value is not None:
                setattr(interpreter, key, value)

    if args["help"]:
        from .misc.help import help_message

        help_message()
        sys.exit(0)

    if args["version"]:
        # Print version of currently installed interpreter
        # Get this from the package metadata
        from importlib.metadata import version

        print("Open Interpreter " + version("open-interpreter"))
        sys.exit(0)

    # Check if we should start the server
    if args["serve"]:
        # Load interpreter immediately for server mode
        load_interpreter()
        print("Starting server...")
        interpreter.server()
        return

    async def async_load():
        # Write initial prompt with placeholder
        sys.stdout.write(
            '\n> Use """ for multi-line prompts'
        )  # Write prompt and placeholder
        sys.stdout.write("\r> ")  # Move cursor back to after >
        sys.stdout.flush()

        # Load interpreter in background
        with ThreadPoolExecutor() as pool:
            await asyncio.get_event_loop().run_in_executor(pool, load_interpreter)

        # Clear the line when done
        sys.stdout.write("\r\033[K")  # Clear entire line
        sys.stdout.flush()

    if args["input"] is None and sys.stdin.isatty():
        from .misc.welcome import welcome_message

        welcome_message(args)
        asyncio.run(async_load())
        interpreter.chat()
    else:
        print()
        spinner = SimpleSpinner("")
        spinner.start()
        load_interpreter()
        spinner.stop()

        if args["input"] is not None:
            message = args["input"]
        else:
            message = sys.stdin.read().strip()
        interpreter.messages = [{"role": "user", "content": message}]

        # Run the generator until completion
        for _ in interpreter.respond():
            pass
        print()

        if interpreter.interactive:
            interpreter.chat()  # Continue in interactive mode


if __name__ == "__main__":
    main()
