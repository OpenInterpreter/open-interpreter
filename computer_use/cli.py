import importlib.util
import json
import os
import random
import sys
import time

import platformdirs

from .loop import run_async_main
from .ui.edit import CodeStreamView


def feed_json_in_chunks(
    json_str: str, streamer: CodeStreamView, min_chunk=1, max_chunk=5
):
    """Feed a JSON string to the streamer in random sized chunks"""

    i = 0
    while i < len(json_str):
        # Get random chunk size between min and max
        chunk_size = random.randint(min_chunk, max_chunk)
        # Get next chunk, ensuring we don't go past end of string
        chunk = json_str[i : i + chunk_size]
        # Feed the chunk
        streamer.feed(chunk)
        # Increment position
        i += chunk_size
        # Sleep for random delay between 0.01 and 0.3
        time.sleep(random.uniform(0.001, 0.003))

    streamer.close()


def help_message():
    tips = [
        "\033[38;5;240mTip: Pipe in prompts using `$ANYTHING | i`\033[0m",
        "\033[38;5;240mTip: Type `wtf` in your terminal to fix the last error\033[0m",
        "\033[38;5;240mTip: Your terminal is a chatbox. Type `i want to...`\033[0m",
    ]
    BLUE_COLOR = "\033[94m"
    RESET_COLOR = "\033[0m"

    content = f"""
A standard interface for computer-controlling agents.

Run {BLUE_COLOR}interpreter{RESET_COLOR} or {BLUE_COLOR}i [prompt]{RESET_COLOR} to begin.

{BLUE_COLOR}--gui{RESET_COLOR} Enable display, mouse, and keyboard control
{BLUE_COLOR}--model{RESET_COLOR} Specify language model or OpenAI-compatible URL
{BLUE_COLOR}--serve{RESET_COLOR} Start an OpenAI-compatible server at {BLUE_COLOR}/{RESET_COLOR}

{BLUE_COLOR}-y{RESET_COLOR} Automatically approve tools
{BLUE_COLOR}-d{RESET_COLOR} Run in debug mode

Examples:

{BLUE_COLOR}i need help with my code{RESET_COLOR}
{BLUE_COLOR}i --model gpt-4o-mini --serve{RESET_COLOR}
{BLUE_COLOR}i --model https://localhost:1234/v1{RESET_COLOR}

{random.choice(tips)}
""".strip()

    # Example JSON to stream
    json_str = json.dumps(
        {"command": "Open Interpreter", "path": "", "file_text": content}
    )

    # Feed the JSON string in chunks
    streamer = CodeStreamView()
    streamer.name = "str_replace_editor"
    feed_json_in_chunks(json_str, streamer)

    time.sleep(0.03)
    print("")
    time.sleep(0.04)
    # print("\033[38;5;238mA.C., 2024. https://openinterpreter.com/\033[0m\n")
    print("\033[38;5;238mhttps://openinterpreter.com/\033[0m\n")
    time.sleep(0.05)


def main():
    oi_dir = platformdirs.user_config_dir("open-interpreter")
    profiles_dir = os.path.join(oi_dir, "profiles")

    # Get profile path from command line args
    profile = None
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
            break

    if profile:
        if not os.path.isfile(profile):
            profile = os.path.join(profiles_dir, profile)
            if not os.path.isfile(profile):
                profile += ".py"
                if not os.path.isfile(profile):
                    print(f"Invalid profile path: {profile}")
                    exit(1)

        # Load the profile module from the provided path
        spec = importlib.util.spec_from_file_location("profile", profile)
        profile_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(profile_module)

        # Get the interpreter from the profile
        interpreter = profile_module.interpreter

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        help_message()
    else:
        run_async_main()
