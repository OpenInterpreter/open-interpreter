import os
import random
import time

from ..ui.markdown import MarkdownRenderer
from .stream_text import stream_text


def welcome_message():
    terminal_width = os.get_terminal_size().columns
    print()
    renderer = MarkdownRenderer()

    import random

    tips = [
        # "You can type `i` in your terminal to use Open Interpreter.",
        "**Tip:** Type `wtf` in your terminal to have Open Interpreter fix the last error.",
        # "You can type prompts after `i` in your terminal, for example, `i want you to install node`. (Yes, really.)",
        "We recommend using our desktop app for the best experience. Type `d` for early access.",
        "**Tip:** Reduce display resolution for better performance.",
    ]

    random_tip = random.choice(tips)

    model = "` ✳ CLAUDE-3.5-SONNET `"  # {"-" * (terminal_width - len(model))}

    second_column_from_left = 20

    markdown_text = f"""●
        
Welcome to **Open Interpreter**. 

**MODEL:** {model}

**TOOLS**{" "*(second_column_from_left-len("TOOLS"))}**MODEL**
` ❯ INTERPRETER `{" "*(second_column_from_left-len(" ❯ INTERPRETER "))}{model}
` ❚ FILE EDITOR `{" "*(second_column_from_left-len(" ❚ FILE EDITOR "))}**PROFILE**
` ⎋ GUI CONTROL `{" "*(second_column_from_left-len(" ⎋ GUI CONTROL "))}` ● i.com/FAST `


{"-" * terminal_width}

{random_tip}

**Warning:** This AI has full system access and can modify files, install software, and execute commands. By continuing, you accept all risks and responsibility.

Move your mouse to any corner of the screen to exit.

{"-" * terminal_width}
"""

    for chunk in stream_text(markdown_text, max_chunk=1):
        renderer.feed(chunk)

    renderer.close()


# ⧳ ❚ ❯ ✦ ⬤ ● ▶ ⚈ ⌖ ⎋ ⬤ ◉
