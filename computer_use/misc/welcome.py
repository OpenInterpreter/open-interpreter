import os
import random
import time

from ..ui.markdown import MarkdownRenderer
from .stream_text import stream_text


def welcome_message(args):
    terminal_width = os.get_terminal_size().columns
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

    if args["model"]:
        model = f"` ✳ {args['model']} `"  # {"-" * (terminal_width - len(model))} # ⎇
    else:
        model = "` ✳ CLAUDE-3.5-SONNET `"  # {"-" * (terminal_width - len(model))} # ⎇

    if args["gui"]:
        gui = "` ✳ GUI CONTROL `"
    else:
        gui = " " * len(" ✳ GUI CONTROL ")

    second_column_from_left = 20

    markdown_text = f"""●
        
Welcome to **Open Interpreter**. 


**TOOLS**{" "*(second_column_from_left-len("TOOLS"))}**MODEL**
` ❯ INTERPRETER `{" "*(second_column_from_left-len(" ❯ INTERPRETER "))}{model}
` ❚ FILE EDITOR `{" "*(second_column_from_left-len(" ❚ FILE EDITOR "))}**MODE**
{gui}{" "*(second_column_from_left-len(" ⎋ GUI CONTROL "))}` ? ASK CONFIRMATION `


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
