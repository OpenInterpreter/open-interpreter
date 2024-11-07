import argparse
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from .misc.help import help_message
from .misc.welcome import welcome_message


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", "-h", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--serve", "-s", action="store_true", help="Start the server")
    parser.add_argument("--model", "-m", help="Specify the model name")
    parser.add_argument("--api-base", "-b", help="Specify the API base URL")
    parser.add_argument("--api-key", "-k", help="Specify the API key")
    parser.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")
    parser.add_argument("--gui", "-g", action="store_true", help="Enable GUI control")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Automatically approve tools"
    )
    parser.add_argument("--input-message", help=argparse.SUPPRESS)

    # If second argument exists and doesn't start with '-', don't parse args. This is an `i` style input
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return {**vars(parser.parse_args([])), "input_message": " ".join(sys.argv[1:])}

    args = vars(parser.parse_args())

    if args["help"]:
        arguments_string = ""
        for action in parser._actions:
            if action.help != argparse.SUPPRESS:
                arguments_string += f"\n  {action.option_strings[0]:<12} {action.help}"
        help_message(arguments_string)
        sys.exit(0)

    return args


def main():
    args = parse_args()

    if sys.stdin.isatty() and not args["input_message"]:
        welcome_message(args)
    else:
        from yaspin import yaspin
        from yaspin.spinners import Spinners

        spinner = yaspin(Spinners.simpleDots, text="")
        spinner.start()

    def load_main():
        global main
        from .main import main

    async def async_load():
        # Write initial prompt with placeholder
        sys.stdout.write(
            '\n> Use """ for multi-line prompts'
        )  # Write prompt and placeholder
        sys.stdout.write("\r> ")  # Move cursor back to after >
        sys.stdout.flush()

        # Load main in background
        with ThreadPoolExecutor() as pool:
            await asyncio.get_event_loop().run_in_executor(pool, load_main)

        # Clear the line when done
        sys.stdout.write("\r\033[K")  # Clear entire line
        sys.stdout.flush()

    if sys.stdin.isatty() and not args["input_message"]:
        asyncio.run(async_load())
        # print("\r", end="", flush=True)
    else:
        load_main()
        spinner.stop()

    main(args)


if __name__ == "__main__":
    main()
