import json
import random
import time

from ..ui.tool import ToolRenderer
from .stream_text import stream_text


def help_message(arguments_string):
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

{BLUE_COLOR}--model{RESET_COLOR} Specify language model or OpenAI-compatible URL
{BLUE_COLOR}--serve{RESET_COLOR} Start an OpenAI-compatible server at {BLUE_COLOR}/{RESET_COLOR}

{BLUE_COLOR}-y{RESET_COLOR} Automatically approve tools
{BLUE_COLOR}-d{RESET_COLOR} Run in debug mode

Examples:

{BLUE_COLOR}i need help with my code{RESET_COLOR}
{BLUE_COLOR}i --model gpt-4o-mini --serve{RESET_COLOR}
{BLUE_COLOR}i --model https://localhost:1234/v1{RESET_COLOR}

{arguments_string}

{random.choice(tips)}
""".strip()

    string = json.dumps(
        {"command": "Open Interpreter", "path": "", "file_text": content}
    )

    renderer = ToolRenderer(name="str_replace_editor")

    for chunk in stream_text(string):
        renderer.feed(chunk)

    renderer.close()

    time.sleep(0.03)
    print("")
    time.sleep(0.04)
    # print("\033[38;5;238mA.C., 2024. https://openinterpreter.com/\033[0m\n")
    print("\033[38;5;238mhttps://openinterpreter.com/\033[0m\n")
    time.sleep(0.05)
