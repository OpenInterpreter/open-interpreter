import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from yaspin import yaspin
from yaspin.spinners import Spinners

from .profiles import Profile


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
        # Tool configuration
        "tools": {
            "flags": ["--tools"],
            "default": profile.tools,
            "help": "Specify enabled tools (comma-separated)",
        },
        "allowed_commands": {
            "flags": ["--allowed-commands"],
            "default": profile.allowed_commands,
            "help": "Specify allowed commands",
        },
        "allowed_paths": {
            "flags": ["--allowed-paths"],
            "default": profile.allowed_paths,
            "help": "Specify allowed paths",
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
        # Behavior configuration
        "system_message": {
            "flags": ["--system-message"],
            "default": profile.system_message,
            "help": "Overwrite system message",
        },
        "custom_instructions": {
            "flags": ["--custom-instructions"],
            "default": profile.custom_instructions,
            "help": "Appended to default system message",
        },
        "max_budget": {
            "flags": ["--max-budget"],
            "type": float,
            "default": profile.max_budget,
            "help": f"Set maximum budget, defaults to -1 (unlimited)",
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
    profile.load(Profile.DEFAULT_PROFILE_PATH)

    parser = argparse.ArgumentParser(add_help=False)

    # Hidden arguments
    parser.add_argument("--help", "-h", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input-message", help=argparse.SUPPRESS)

    # Add arguments programmatically from config
    arg_params = _profile_to_arg_params(profile)
    for param in arg_params.values():
        flags = param.pop("flags")
        parser.add_argument(*flags, **param)

    # If second argument exists and doesn't start with '-', treat as input message
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return {**vars(parser.parse_args([])), "input_message": " ".join(sys.argv[1:])}

    args = vars(parser.parse_args())

    # If a different profile is specified, load it
    if args["profile"] != profile.profile_path:
        profile.load_from_profile(args["profile"])
        # Update any values that weren't explicitly set in CLI
        for key, value in vars(profile).items():
            if key in args and args[key] is None:
                args[key] = value

    if args["help"]:
        from .misc.help import help_message

        arguments_string = ""
        for action in parser._actions:
            if action.help != argparse.SUPPRESS:
                arguments_string += f"\n  {action.option_strings[0]:<12} {action.help}"
        help_message(arguments_string)
        sys.exit(0)

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

    # Check if we should start the server
    if args["serve"]:
        # Load interpreter immediately for server mode
        load_interpreter()
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

    if args["input_message"] is None:
        from .misc.welcome import welcome_message

        welcome_message(args)
        asyncio.run(async_load())
        interpreter.chat()
    else:
        print()
        spinner = yaspin(Spinners.simpleDots, text="")
        spinner.start()
        load_interpreter()
        spinner.stop()
        if args["input_message"]:
            message = args["input_message"]
        else:
            message = sys.stdin.read().strip()
        interpreter.messages = [{"role": "user", "content": message}]

        # Run the generator until completion
        for _ in interpreter.respond():
            pass
        print()

        if sys.stdin.isatty():
            interpreter.chat()  # Continue in interactive mode


if __name__ == "__main__":
    main()
