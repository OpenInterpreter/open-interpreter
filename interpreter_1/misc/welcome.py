import os
import random
import time

from ..ui.markdown import MarkdownRenderer
from .stream_text import stream_text


def welcome_message(args):
    try:
        terminal_width = os.get_terminal_size().columns
    except:
        terminal_width = 80
    print()
    renderer = MarkdownRenderer()

    import random

    tips = [
        # "You can type `i` in your terminal to use Open Interpreter.",
        "**Tip:** Type `wtf` in your terminal to instantly fix the last error.",
        # "**Tip:** Type `wtf` in your terminal to have Open Interpreter fix the last error.",
        '**Tip:** You can paste content into Open Interpreter by typing `"""` first.',
        # "**Tip:** Type prompts after `i` in your terminal, for example, `i want deno`.",
        "**Tip:** You can type `i [your prompt]` directly into your terminal, e.g. `i want a venv`.",  # \n\nThese are all valid commands: `i want deno`, `i dont understand`, `i want a venv`",
        # "**Tip:** Type your prompt directly into your CLI by starting with `i `, like `i want node`.", # \n\nThese are all valid commands: `i want deno`, `i dont understand`, `i want a venv`",
        # "Our desktop app provides the best experience. Type `d` for early access.",
        # "**Tip:** Reduce display resolution for better performance.",
    ]

    random_tip = random.choice(tips)

    model = args["model"]

    if model == "claude-3-5-sonnet-20241022":
        model = "CLAUDE-3.5-SONNET"

    model = f"` ✳ {model.upper()} `"  # {"-" * (terminal_width - len(model))} # ⎇

    tool_displays = []
    for tool in ["interpreter", "editor", "gui"]:
        if args["tools"] and tool in args["tools"]:
            if tool == "interpreter":
                tool_displays.append("` ❯ INTERPRETER `")
            elif tool == "editor":
                tool_displays.append("` ❚ FILE EDITOR `")
            elif tool == "gui":
                tool_displays.append("` ✳ GUI CONTROL `")
        else:
            if tool == "interpreter":
                tool_displays.append(" " * len(" ❯ INTERPRETER "))
            elif tool == "editor":
                tool_displays.append(" " * len(" ❚ FILE EDITOR "))
            elif tool == "gui":
                tool_displays.append(" " * len(" ✳ GUI CONTROL "))

    # Sort tool_displays so that empty tools are at the end
    tool_displays = sorted(
        tool_displays, key=lambda x: x == " " * len(" ❯ INTERPRETER ")
    )

    auto_run_display = (
        "` ! AUTOMATIC (UNSAFE) `" if args["auto_run"] else "` ? REQUIRES PERMISSION `"
    )

    second_column_from_left = 20

    markdown_text = f"""●
        
Welcome to **Open Interpreter**. 


**TOOLS**{" "*(second_column_from_left-len("TOOLS"))}**MODEL**
{tool_displays[0]}{" "*(second_column_from_left-len(" ❯ INTERPRETER "))}{model}
{tool_displays[1]}{" "*(second_column_from_left-len(" ❯ INTERPRETER "))}**TOOL EXECUTION**
{tool_displays[2]}{" "*(second_column_from_left-len(" ❯ INTERPRETER "))}{auto_run_display}


{random_tip}


{"─" * terminal_width}
"""

    """
    **Warning:** This AI has full system access and can modify files, install software, and execute commands. By continuing, you accept all risks and responsibility.

    Move your mouse to any corner of the screen to exit.
    """

    # for chunk in stream_text(markdown_text, max_chunk=1, min_delay=0.0001, max_delay=0.001):
    #     renderer.feed(chunk)

    renderer.feed(markdown_text)

    renderer.close()


# ⧳ ❚ ❯ ✦ ⬤ ● ▶ ⚈ ⌖ ⎋ ⬤ ◉ ⎇
