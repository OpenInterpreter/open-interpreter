import json
import random
import sys
import time

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
    content = f"""
A standard interface for computer-controlling agents.

Run \033[34minterpreter\033[0m or \033[34mi [prompt]\033[0m to begin.

\033[34m--gui\033[0m Enable display, mouse, and keyboard control
\033[34m--model\033[0m Specify language model or OpenAI-compatible URL
\033[34m--serve\033[0m Start an OpenAI-compatible server at \033[34m/\033[0m

\033[34m-y\033[0m Automatically approve tools
\033[34m-d\033[0m Run in debug mode

Examples:

\033[34mi need help with my code\033[0m
\033[34mi --model gpt-4o-mini --serve\033[0m
\033[34mi --model https://localhost:1234/v1\033[0m

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
    print("\033[38;5;238mA.C., 2024. https://openinterpreter.com/\033[0m\n")
    time.sleep(0.05)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        help_message()
    else:
        run_async_main()
