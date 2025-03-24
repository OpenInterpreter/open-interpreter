import os
import random
from interpreter import __version__


def welcome_message(args):
    print(
        f"""
\033[7m ✳ CLAUDE 3.5 SONNET \033[0m

This AI can modify files, install software, and execute commands.

By continuing, you accept all risks and responsibility.
"""
    )


def welcome_message(args):
    print(
        f'''
\033[7m ✳ CLAUDE 3.5 SONNET \033[0m

Tip: You can paste content by typing """ first.
'''
    )


def welcome_message(args):
    print(
        f"""
\033[94m✳ claude 3.5 sonnet
❯ runs code, ≣ edits files
⌘ requires approval\033[0m
"""
    )  # , ⌖ controls gui


def welcome_message(args):
    # Define color combinations
    COLORS = {
        "medium_blue": ("\033[48;5;27m", "\033[38;5;27m"),
        #'bright_blue': ("\033[48;5;33m", "\033[38;5;33m"),
        "dark_blue": ("\033[48;5;20m", "\033[38;5;20m"),
        "light_blue": ("\033[48;5;39m", "\033[38;5;39m"),
        #'sky_blue': ("\033[48;5;117m", "\033[38;5;117m"),
        #'steel_blue': ("\033[48;5;67m", "\033[38;5;67m"),
        #'powder_blue': ("\033[48;5;153m", "\033[38;5;153m"),
        #'royal_blue': ("\033[48;5;62m", "\033[38;5;62m"),
        #'navy_blue': ("\033[48;5;17m", "\033[38;5;17m"),
        #'azure_blue': ("\033[48;5;111m", "\033[38;5;111m"),
        #'cornflower_blue': ("\033[48;5;69m", "\033[38;5;69m"),
        "deep_sky_blue": ("\033[48;5;32m", "\033[38;5;32m"),
        "dodger_blue": ("\033[48;5;33m", "\033[38;5;33m"),
        #'sapphire_blue': ("\033[48;5;25m", "\033[38;5;25m")
        # 'dark_gray': ("\033[48;5;240m", "\033[38;5;240m"),
        # 'light_gray': ("\033[48;5;248m", "\033[38;5;248m"),
        # 'white': ("\033[48;5;231m", "\033[38;5;231m"),
        # 'black': ("\033[48;5;232m", "\033[38;5;232m"),
    }

    WHITE_FG = "\033[97m"
    BLACK_FG = "\033[30m"
    RESET = "\033[0m"

    # Different text layouts
    LAYOUTS = {
        "basic_background": lambda bg, fg: f"""
{bg} * CLAUDE 3.5 SONNET {RESET}

{fg}❯{RESET} runs code
{fg}≣{RESET} edits files
{fg}⌘{RESET} requires approval
""",
        "compact": lambda bg, fg: f"""
{bg} * CLAUDE 3.5 SONNET {RESET} {fg}❯{RESET} code {fg}≣{RESET} files {fg}⌘{RESET} approval
""",
        "white_on_color": lambda bg, fg: f"""
{bg}{WHITE_FG} * CLAUDE 3.5 SONNET {RESET}

{bg}{WHITE_FG}❯{RESET} runs code
{bg}{WHITE_FG}≣{RESET} edits files
{bg}{WHITE_FG}⌘{RESET} requires approval
""",
        "white_on_color_2": lambda bg, fg: f"""
{bg}{WHITE_FG} * CLAUDE 3.5 SONNET {RESET}

{bg}{WHITE_FG}❯{RESET} interpreter {bg}{WHITE_FG}≣{RESET} file editor
{bg}{WHITE_FG}⌘{RESET} actions require approval
""",
        "black_on_color": lambda bg, fg: f"""
{bg}{BLACK_FG} * CLAUDE 3.5 SONNET {RESET}

{bg}{BLACK_FG}❯{RESET} runs code
{bg}{BLACK_FG}≣{RESET} edits files
{bg}{BLACK_FG}⌘{RESET} requires approval
""",
        "minimal": lambda bg, fg: f"""
* CLAUDE 3.5 SONNET

{fg}$ runs code
≣ edits files
! requires approval{RESET}
""",
        "double_line": lambda bg, fg: f"""
{bg} * CLAUDE 3.5 SONNET {RESET}

{fg}❯ runs code{RESET} {fg}≣ edits files{RESET}
{fg}⌘ requires approval{RESET}
""",
        "modern": lambda bg, fg: f"""
{bg} >> CLAUDE 3.5 SONNET << {RESET}

{fg}▶{RESET} executes commands
{fg}□{RESET} manages files
{fg}△{RESET} needs approval
""",
        "technical": lambda bg, fg: f"""
{bg} CLAUDE 3.5 SONNET {RESET}

{fg}${RESET} runs code
{fg}#{RESET} edits files
{fg}@{RESET} needs ok
""",
        "technical_2": lambda bg, fg: f"""
{bg}{WHITE_FG} CLAUDE 3.5 SONNET {RESET}

# edits files
$ executes commands
@ actions require approval
""",
        "technical_3": lambda bg, fg: f"""
{bg}{WHITE_FG} CLAUDE 3.5 SONNET {RESET}

{fg}# file editor
$ bash executor
@ requires approval{RESET}
""",
        "brackets": lambda bg, fg: f"""
{bg} [ CLAUDE 3.5 SONNET ] {RESET}

{fg}[>]{RESET} run commands
{fg}[=]{RESET} file operations
{fg}[!]{RESET} elevated access
""",
        "ascii_art": lambda bg, fg: f"""
{bg} | CLAUDE SONNET    | {RESET}

{fg}>>>{RESET} execute code
{fg}[=]{RESET} modify files
{fg}(!){RESET} request approval
""",
    }

    LAYOUTS = {
        k: v
        for k, v in LAYOUTS.items()
        if k
        in ["basic_background", "minimal", "technical", "technical_2", "technical_3"]
    }

    # Print each layout with different color combinations
    import random

    layout_items = list(LAYOUTS.items())
    color_items = list(COLORS.items())
    random.shuffle(layout_items)
    random.shuffle(color_items)

    for color_name, (BG, FG) in color_items:
        for layout_name, layout in layout_items:
            print(f"Style: {layout_name} with {color_name}\n\n\n")
            print("$: interpreter")
            print(layout(BG, FG))
            print("> make a react project")
            print("\n" * 10)


def welcome_message(args):
    WHITE_FG = "\033[97m"
    BLUE_BG = "\033[48;5;27m"  # Dark blue background (not navy)
    BLUE_FG = "\033[38;5;27m"  # Matching dark blue foreground
    BLUE_BG = "\033[48;5;21m"  # Dark blue background (not navy)
    BLUE_FG = "\033[38;5;21m"  # Matching dark blue foreground
    RESET = "\033[0m"

    tips = [
        'Use """ for multi-line input',
        "Try the wtf command to fix the last error",
        "Press Ctrl+C to cancel",
        "Messages starting with $ run in the shell",
    ]

    print(
        f"""
{BLUE_BG}{WHITE_FG} CLAUDE 3.5 SONNET {RESET}

# edits files
$ executes commands
@ actions require approval
"""
    )


# Tip: {random.choice(tips)}

# def welcome_message(args):
#     print(f"""
# \033[7m GPT-5 \033[0m

# # edits files
# $ executes commands
# @ actions require approval
# """)


def welcome_message(args):
    print(
        f"""
Open Interpreter {__version__}
Copyright (C) 2024 Open Interpreter Team
Licensed under GNU AGPL v3.0
Maintained by automated systems

A natural language interface for your computer.

Usage: i [prompt]
   or: interpreter [options]

Documentation: docs.openinterpreter.com
Run 'interpreter --help' for full options

"""
    )


def welcome_message():
    print(
        f"""
Open Interpreter {__version__}
Licensed under GNU AGPL v3.0

A natural language interface for your computer.

Usage: interpreter [prompt] [-m model] [-t temp] [-k key] [options]
Execute natural language commands on your computer

    -m, --model <model>    Specify the language model to use
    -t, --temp <float>     Set temperature (0-1) for model responses
    -k, --key <key>        Set API key for the model provider
    -p, --profile <file>   Load settings from profile file
    --auto-run            Run commands without confirmation
    --no-tools            Disable tool/function calling
    --debug               Enable debug logging
    --serve               Start in server mode

example: interpreter "create a python script"
example: interpreter -m gpt-4 "analyze data.csv" 
example: interpreter --auto-run "install nodejs"
example: interpreter --profile work.json
"""
    )


def welcome_message():
    print(
        f"""
Open Interpreter {__version__}
Licensed under GNU AGPL v3.0

A modern command-line assistant.

Usage: interpreter [prompt] [-m model] [-t temp] [-k key] [options]
Execute natural language commands on your computer

    -m, --model <model>    Specify the language model to use
    -t, --temp <float>     Set temperature (0-1) for model responses
    -k, --key <key>        Set API key for the model provider
    -p, --profile <file>   Load settings from profile file
    --auto-run            Run commands without confirmation
    --no-tools            Disable tool/function calling
    --debug               Enable debug logging
    --serve               Start in server mode

example: interpreter "create a python script"
example: interpreter -m gpt-4 "analyze data.csv" 
example: interpreter --auto-run "install nodejs"
example: interpreter --profile work.json
"""
    )


def welcome_message():
    print(
        f"""
Open Interpreter {__version__}
Copyright (C) 2024 Open Interpreter Team
Licensed under GNU AGPL v3.0

A modern command-line assistant.

Usage: i [prompt]
   or: interpreter [options]

Documentation: docs.openinterpreter.com
Run 'interpreter --help' for all options
"""
    )
