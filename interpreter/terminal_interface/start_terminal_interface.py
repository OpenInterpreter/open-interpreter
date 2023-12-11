import argparse
import os
import platform
import re
import subprocess
import sys

import pkg_resources

from .conversation_navigator import conversation_navigator
from .utils.check_for_update import check_for_update
from .utils.display_markdown_message import display_markdown_message
from .utils.get_config import get_config_path
from .validate_llm_settings import validate_llm_settings

arguments = [
    {
        "name": "system_message",
        "nickname": "s",
        "help_text": "prompt / custom instructions for the language model",
        "type": str,
    },
    {
        "name": "local",
        "nickname": "l",
        "help_text": "experimentally run the language model locally (via LM Studio)",
        "type": bool,
    },
    {
        "name": "auto_run",
        "nickname": "y",
        "help_text": "automatically run generated code",
        "type": bool,
    },
    {
        "name": "debug_mode",
        "nickname": "d",
        "help_text": "run in debug mode",
        "type": bool,
    },
    {
        "name": "disable_procedures",
        "nickname": "dp",
        "help_text": "disables procedures (RAG of some common OI use-cases). disable to shrink system message. auto-disabled for non-OpenAI models",
        "type": bool,
    },
    {
        "name": "model",
        "nickname": "m",
        "help_text": "language model to use",
        "type": str,
    },
    {
        "name": "temperature",
        "nickname": "t",
        "help_text": "optional temperature setting for the language model",
        "type": float,
    },
    {
        "name": "context_window",
        "nickname": "c",
        "help_text": "optional context window size for the language model",
        "type": int,
    },
    {
        "name": "max_tokens",
        "nickname": "x",
        "help_text": "optional maximum number of tokens for the language model",
        "type": int,
    },
    {
        "name": "max_output",
        "nickname": "xo",
        "help_text": "optional maximum number of characters for code outputs",
        "type": int,
    },
    {
        "name": "max_budget",
        "nickname": "b",
        "help_text": "optionally set the max budget (in USD) for your llm calls",
        "type": float,
    },
    {
        "name": "api_base",
        "nickname": "ab",
        "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
        "type": str,
    },
    {
        "name": "api_key",
        "nickname": "ak",
        "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
        "type": str,
    },
    {
        "name": "safe_mode",
        "nickname": "safe",
        "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
        "type": str,
        "choices": ["off", "ask", "auto"],
        "default": "off",
    },
    {
        "name": "config_file",
        "nickname": "cf",
        "help_text": "optionally set a custom config file to use",
        "type": str,
    },
    {
        "name": "vision",
        "nickname": "v",
        "help_text": "experimentally use vision for supported languages (HTML)",
        "type": bool,
    },
    {
        "name": "os",
        "nickname": "o",
        "help_text": "experimentally let Open Interpreter control your mouse and keyboard",
        "type": bool,
    },
]


def start_terminal_interface(interpreter):
    """
    Meant to be used from the command line. Parses arguments, starts OI's terminal interface.
    """

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        if arg["type"] == bool:
            parser.add_argument(
                f'-{arg["nickname"]}',
                f'--{arg["name"]}',
                dest=arg["name"],
                help=arg["help_text"],
                action="store_true",
                default=None,
            )
        else:
            choices = arg["choices"] if "choices" in arg else None
            default = arg["default"] if "default" in arg else None

            parser.add_argument(
                f'-{arg["nickname"]}',
                f'--{arg["name"]}',
                dest=arg["name"],
                help=arg["help_text"],
                type=arg["type"],
                choices=choices,
                default=default,
            )

    # Add special arguments
    parser.add_argument(
        "--config",
        dest="config",
        action="store_true",
        help="open config.yaml file in text editor",
    )
    parser.add_argument(
        "--conversations",
        dest="conversations",
        action="store_true",
        help="list conversations to resume",
    )
    parser.add_argument(
        "-f",
        "--fast",
        dest="fast",
        action="store_true",
        help="run `interpreter --model gpt-3.5-turbo`",
    )
    parser.add_argument(
        "--version",
        dest="version",
        action="store_true",
        help="get Open Interpreter's version number",
    )

    args = parser.parse_args()

    # This should be pushed into an open_config.py util
    # If --config is used, open the config.yaml file in the Open Interpreter folder of the user's config dir
    if args.config:
        if args.config_file:
            config_file = get_config_path(args.config_file)
        else:
            config_file = get_config_path()

        print(f"Opening `{config_file}`...")

        # Use the default system editor to open the file
        if platform.system() == "Windows":
            os.startfile(
                config_file
            )  # This will open the file with the default application, e.g., Notepad
        else:
            try:
                # Try using xdg-open on non-Windows platforms
                subprocess.call(["xdg-open", config_file])
            except FileNotFoundError:
                # Fallback to using 'open' on macOS if 'xdg-open' is not available
                subprocess.call(["open", config_file])
        return

    if args.local:
        # Default local (LM studio) attributes
        interpreter.system_message = "You are an AI."
        interpreter.model = (
            "openai/" + interpreter.model
        )  # This tells LiteLLM it's an OpenAI compatible server
        interpreter.api_base = "http://localhost:1234/v1"
        interpreter.max_tokens = 1000
        interpreter.context_window = 3000
        interpreter.api_key = "0"

        display_markdown_message(
            """
> Open Interpreter's local mode is powered by **`LM Studio`**.


You will need to run **LM Studio** in the background.

1. Download **LM Studio** from [https://lmstudio.ai/](https://lmstudio.ai/) then start it.
2. Select a language model then click **Download**.
3. Click the **<->** button on the left (below the chat button).
4. Select your model at the top, then click **Start Server**.


Once the server is running, you can begin your conversation below.

> **Warning:** This feature is highly experimental.
> Don't expect `gpt-3.5` / `gpt-4` level quality, speed, or reliability yet!

"""
        )

    # Set attributes on interpreter
    for attr_name, attr_value in vars(args).items():
        # Ignore things that aren't possible attributes on interpreter
        if attr_value is not None and hasattr(interpreter, attr_name):
            # If the user has provided a config file, load it and extend interpreter's configuration
            if attr_name == "config_file":
                user_config = get_config_path(attr_value)
                interpreter.config_file = user_config
                interpreter.extend_config(config_path=user_config)
            else:
                setattr(interpreter, attr_name, attr_value)

    # Check for update
    try:
        if not interpreter.local:
            # This should actually be pushed into the utility
            if check_for_update():
                display_markdown_message(
                    "> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---"
                )
    except:
        # Doesn't matter
        pass

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and (
        interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto"
    ):
        setattr(interpreter, "auto_run", False)

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    if args.version:
        version = pkg_resources.get_distribution("open-interpreter").version
        update_name = "New Computer"  # Change this with each major update
        print(f"Open Interpreter {version} {update_name}")
        return

    if args.fast:
        interpreter.model = "gpt-3.5-turbo"

    if args.vision:
        interpreter.vision = True
        interpreter.model = "gpt-4-vision-preview"
        interpreter.system_message += "\nThe user will show you an image of the code you write. You can view images directly.\n\nFor HTML: This will be run STATELESSLY. You may NEVER write '<!-- previous code here... --!>' or `<!-- header will go here -->` or anything like that. It is CRITICAL TO NEVER WRITE PLACEHOLDERS. Placeholders will BREAK it. You must write the FULL HTML CODE EVERY TIME. Therefore you cannot write HTML piecemeal—write all the HTML, CSS, and possibly Javascript **in one step, in one code block**. The user will help you review it visually.\nIf the user submits a filepath, you will also see the image. The filepath and user image will both be in the user's message.\n\nIf you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you."
        interpreter.function_calling_llm = False
        interpreter.context_window = 110000
        interpreter.max_tokens = 4096
        interpreter.force_task_completion = True

        display_markdown_message("> `Vision` enabled **(experimental)**\n")

    if args.os:
        interpreter.os = True
        interpreter.disable_procedures = True
        interpreter.vision = True
        interpreter.model = "gpt-4-vision-preview"
        interpreter.function_calling_llm = False
        interpreter.context_window = 110000
        interpreter.max_tokens = 4096
        interpreter.auto_run = True
        interpreter.force_task_completion = True
        # This line made it use files too much
        interpreter.system_message = interpreter.system_message.replace(
            "If you want to send data between programming languages, save the data to a txt or json.\n",
            "",
        )
        interpreter.system_message = interpreter.system_message.replace(
            "When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.",
            "The user is likely referring to something on their screen.",
        )
        interpreter.system_message += (
            "\n\n"
            + """

Execute code using `computer` (already imported) to control the user's computer:

```python
computer.screenshot() # Automatically runs plt.show() to show you what's on the screen, returns a `pil_image` `in case you need it (rarely). **You almost always want to do this first! You don't know what's on the user's screen.**
computer.screenshot(quadrant=1) # Get a detailed view of the upper left quadrant (you'll rarely need this, use it to examine/retry failed attempts)

computer.keyboard.hotkey("space", "command") # Opens spotlight (very useful)
computer.keyboard.write("hello")
# .down() .up() and .press() also work (uses pyautogui)

computer.mouse.move("Text Onscreen") # This moves the mouse to the UI element with that text. Use this **frequently** — and get creative! To mouse over a video thumbnail, you could pass the *timestamp* (which is usually written on the thumbnail) into this.
computer.mouse.move(x=500, y=500) # Use this very rarely. It's only 1% as accurate as click("Text")!
computer.mouse.click() # Don't forget this! Include in the same code block

# Dragging
computer.mouse.move("So I was")
computer.mouse.down()
computer.mouse.move("and that's it!")
computer.mouse.up()
```

For rare and complex mouse actions, consider using computer vision libraries on `pil_image` to produce a list of coordinates for the mouse to move/drag to.

If the user highlighted text in an editor, then asked you to modify it, they probably want you to `keyboard.write` it over their version of the text.

Tasks are 100% computer-based. DO NOT simply write long messages to the user to complete tasks. You MUST put your text back into the program they're using to deliver your text! For example, overwriting some text they've highlighted with `keyboard.write`.

Use keyboard navigation when reasonably possible, but not if it involves pressing a button multiple times. The mouse is less reliable. Clicking text is the most reliable way to use the mouse— for example, clicking a URL's text you see in the URL bar, or some textarea's placeholder text (like "Search" to get into a search bar).

Applescript might be best for some tasks.
        
If you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you.

**Include `computer.screenshot()` after a 2 second delay at the end of _every_ code block to verify your progress on the task.**

Try multiple methods before saying the task is impossible. **You can do it!**

You are an expert computer navigator, brilliant and technical. **At each step, describe the user's screen with a lot of detail, including 1. the active app, 2. what text areas appear to be active, 3. what text is selected, if any, 4. what options you could take next.** Think carefully.

        """.strip()
        )

        # Download required packages
        try:
            import cv2
            import IPython
            import matplotlib
            import pyautogui
            import pytesseract
        except ImportError:
            display_markdown_message(
                "> **Missing Packages**\n\nSeveral packages are required for OS Control (`matplotlib`, `pytesseract`, `pyautogui`, `opencv-python`, `ipython`).\n\nInstall them?\n"
            )
            user_input = input("(y/n) > ")
            if user_input.lower() != "y":
                print("Exiting...")
                return
            packages = [
                "matplotlib",
                "pytesseract",
                "pyautogui",
                "opencv-python",
                "ipython",
            ]
            command = "\n".join([f"pip install {package}" for package in packages])
            for chunk in interpreter.computer.run("shell", command):
                if chunk.get("format") != "active_line":
                    print(chunk.get("content"))

        display_markdown_message(
            "> `OS Control` enabled (experimental)\n\nOpen Interpreter will be able to see your screen, move your mouse, and use your keyboard."
        )
        print("")  # < - Aesthetic choice

        # Give it access to the computer via Python
        for _ in interpreter.computer.run(
            "python",
            "import interpreter\ncomputer = interpreter.computer",
        ):
            pass

        display_markdown_message(
            "**Warning:** In this mode, Open Interpreter will not require approval before performing actions. Be ready to close your terminal."
        )
        print("")  # < - Aesthetic choice

    if not interpreter.local and interpreter.model == "gpt-4-1106-preview":
        if interpreter.context_window is None:
            interpreter.context_window = 128000
        if interpreter.max_tokens is None:
            interpreter.max_tokens = 4096
        if interpreter.function_calling_llm is None:
            interpreter.function_calling_llm = True

    if not interpreter.local and interpreter.model == "gpt-3.5-turbo-1106":
        if interpreter.context_window is None:
            interpreter.context_window = 16000
        if interpreter.max_tokens is None:
            interpreter.max_tokens = 4096
        if interpreter.function_calling_llm is None:
            interpreter.function_calling_llm = True

    validate_llm_settings(interpreter)

    interpreter.chat()
