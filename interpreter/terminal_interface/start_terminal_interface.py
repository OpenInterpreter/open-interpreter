import argparse
import os
import platform
import re
import subprocess
import sys
import time

import pkg_resources

from .conversation_navigator import conversation_navigator
from .utils.check_for_update import check_for_update
from .utils.display_markdown_message import display_markdown_message
from .utils.get_config import get_config_path
from .validate_llm_settings import validate_llm_settings


def start_terminal_interface(interpreter):
    """
    Meant to be used from the command line. Parses arguments, starts OI's terminal interface.
    """

    arguments = [
        # Profiles coming soon— after we seperate core from TUI
        # {
        #     "name": "profile",
        #     "nickname": "p",
        #     "help_text": "profile (from your config file) to use. sets multiple settings at once",
        #     "type": str,
        #     "default": "default",
        # },
        {
            "name": "custom_instructions",
            "nickname": "ci",
            "help_text": "custom instructions for the language model, will be appended to the system_message",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "custom_instructions"},
        },
        {
            "name": "system_message",
            "nickname": "s",
            "help_text": "(we don't recommend changing this) base prompt for the language model",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "system_message"},
        },
        {
            "name": "auto_run",
            "nickname": "y",
            "help_text": "automatically run generated code",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "auto_run"},
        },
        {
            "name": "debug_mode",
            "nickname": "d",
            "help_text": "run in debug mode",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "debug_mode"},
        },
        {
            "name": "model",
            "nickname": "m",
            "help_text": "language model to use",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "model"},
        },
        {
            "name": "temperature",
            "nickname": "t",
            "help_text": "optional temperature setting for the language model",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "temperature"},
        },
        {
            "name": "llm_supports_vision",
            "nickname": "lsv",
            "help_text": "inform OI that your model supports vision, and can recieve vision inputs",
            "type": bool,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_vision"},
        },
        {
            "name": "llm_supports_functions",
            "nickname": "lsf",
            "help_text": "inform OI that your model supports OpenAI-style functions, and can make function calls",
            "type": bool,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_functions"},
        },
        {
            "name": "context_window",
            "nickname": "c",
            "help_text": "optional context window size for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "context_window"},
        },
        {
            "name": "max_tokens",
            "nickname": "x",
            "help_text": "optional maximum number of tokens for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "max_tokens"},
        },
        {
            "name": "max_budget",
            "nickname": "b",
            "help_text": "optionally set the max budget (in USD) for your llm calls",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "max_budget"},
        },
        {
            "name": "api_base",
            "nickname": "ab",
            "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_base"},
        },
        {
            "name": "api_key",
            "nickname": "ak",
            "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_key"},
        },
        {
            "name": "max_output",
            "nickname": "xo",
            "help_text": "optional maximum number of characters for code outputs",
            "type": int,
            "attribute": {"object": interpreter, "attr_name": "max_output"},
        },
        {
            "name": "force_task_completion",
            "nickname": "fc",
            "help_text": "runs OI in a loop, requiring it to admit to completing/failing task",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "force_task_completion"},
        },
        {
            "name": "speak_messages",
            "nickname": "sm",
            "help_text": "(Mac only) use the applescript `say` command to read messages aloud",
            "type": bool,
            "action": "store_true",
            "attribute": {"object": interpreter, "attr_name": "speak_messages"},
        },
        {
            "name": "safe_mode",
            "nickname": "safe",
            "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
            "type": str,
            "choices": ["off", "ask", "auto"],
            "default": "off",
            "attribute": {"object": interpreter, "attr_name": "safe_mode"},
        },
        {
            "name": "config_file",
            "nickname": "cf",
            "help_text": "optionally set a custom config file to use",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "config_file"},
        },
        # Profiles
        {
            "name": "fast",
            "nickname": "f",
            "help_text": "run `interpreter --model gpt-3.5-turbo`",
            "type": bool,
        },
        {
            "name": "local",
            "nickname": "l",
            "help_text": "experimentally run the LLM locally via LM Studio (this just sets api_base, model, system_message, and offline = True)",
            "type": bool,
        },
        {
            "name": "vision",
            "nickname": "v",
            "help_text": "experimentally use vision for supported languages (HTML, Python)",
            "type": bool,
        },
        {
            "name": "os",
            "nickname": "o",
            "help_text": "experimentally let Open Interpreter control your mouse and keyboard",
            "type": bool,
        },
        # Special commands
        {
            "name": "config",
            "help_text": "open config.yaml file in text editor",
            "type": bool,
        },
        {
            "name": "conversations",
            "help_text": "list conversations to resume",
            "type": bool,
        },
        {
            "name": "version",
            "help_text": "get Open Interpreter's version number",
            "type": bool,
        },
    ]

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        action = arg.get("action", "store_true")
        nickname = arg.get("nickname")

        if arg["type"] == bool:
            if nickname:
                parser.add_argument(
                    f"-{nickname}",
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=None,
                )
            else:
                parser.add_argument(
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=None,
                )
        else:
            choices = arg.get("choices")
            default = arg.get("default")

            if nickname:
                parser.add_argument(
                    f"-{nickname}",
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    type=arg["type"],
                    choices=choices,
                    default=default,
                )
            else:
                parser.add_argument(
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    type=arg["type"],
                    choices=choices,
                    default=default,
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

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and (
        interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto"
    ):
        setattr(interpreter, "auto_run", False)

    if args.version:
        version = pkg_resources.get_distribution("open-interpreter").version
        update_name = "New Computer"  # Change this with each major update
        print(f"Open Interpreter {version} {update_name}")
        return

    if args.fast:
        if args.local or args.vision or args.os:
            print(
                "Fast mode (`gpt-3.5`) is not supported with --vision, --os, or --local (`gpt-3.5` is not a vision or a local model)."
            )
            time.sleep(1.5)
        else:
            interpreter.llm.model = "gpt-3.5-turbo"

    if args.vision:
        interpreter.llm.supports_vision = True
        interpreter.llm.model = "gpt-4-vision-preview"
        interpreter.system_message += "\nThe user will show you an image of the code you write. You can view images directly.\n\nFor HTML: This will be run STATELESSLY. You may NEVER write '<!-- previous code here... --!>' or `<!-- header will go here -->` or anything like that. It is CRITICAL TO NEVER WRITE PLACEHOLDERS. Placeholders will BREAK it. You must write the FULL HTML CODE EVERY TIME. Therefore you cannot write HTML piecemeal—write all the HTML, CSS, and possibly Javascript **in one step, in one code block**. The user will help you review it visually.\nIf the user submits a filepath, you will also see the image. The filepath and user image will both be in the user's message.\n\nIf you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you."
        interpreter.llm.supports_functions = False
        interpreter.llm.context_window = 110000
        interpreter.llm.max_tokens = 4096
        interpreter.force_task_completion = True

        if (
            not args.local
        ):  # We'll display this in a moment— after local's message prints
            display_markdown_message("> `Vision` enabled (experimental)\n")

    if args.os:
        interpreter.os = True
        interpreter.offline = True  # Disables open procedures, which is best for pure code mode / normal mode
        interpreter.llm.supports_vision = True
        interpreter.shrink_images = True
        interpreter.llm.model = "gpt-4-vision-preview"
        interpreter.llm.supports_functions = False
        interpreter.llm.context_window = 110000
        interpreter.llm.max_tokens = 4096
        interpreter.auto_run = True
        interpreter.force_task_completion = True

        # This line made it use files too much
        interpreter.system_message = interpreter.system_message.replace(
            "If you want to send data between programming languages, save the data to a txt or json.\n",
            "",
        )
        ambiguous_requests_message = "If there's not enough context, if the user's request is ambiguous, they're likely referring to something on their screen. Take a screenshot! Don't ask questions."
        interpreter.system_message = interpreter.system_message.replace(
            "When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.",
            ambiguous_requests_message,
        )
        if ambiguous_requests_message not in interpreter.system_message:
            interpreter.system_message += "n" + ambiguous_requests_message

        interpreter.system_message += (
            "\n\n"
            + """

Execute code using `computer` (already imported) to control the user's computer:

```python
computer.screenshot() # Automatically runs plt.show() to show you what's on the screen, returns a `pil_image` `in case you need it (rarely). **You almost always want to do this first! You don't know what's on the user's screen.**
x, y = computer.display.size()

computer.keyboard.hotkey(" ", "command") # Opens spotlight (very useful)
computer.keyboard.write("hello")
# .down() .up() and .press() also work (uses pyautogui)

computer.mouse.move("text onscreen") # This moves the mouse to the UI element with that text. Use this **frequently** — and get creative! To mouse over a video thumbnail, you could pass the *timestamp* (which is usually written on the thumbnail) into this.
computer.mouse.move(icon="magnifying glass") # Moves mouse to the icon with that description
computer.mouse.move(x=500, y=500) # Use this very rarely. It's only 1% as accurate as move("Text")!
computer.mouse.click() # Don't forget this! Include in the same code block

# Dragging
computer.mouse.move("So I was")
computer.mouse.down()
computer.mouse.move("and that's it!")
computer.mouse.up()

computer.clipboard.view() # Prints contents of clipboard for you to review.
computer.os.get_selected_text() # If editing text, the user often wants this.
```

If you want to scroll, **ensure the correct window is active**, then consider using the arrow keys.

For rare and complex mouse actions, consider using computer vision libraries on `pil_image` to produce a list of coordinates for the mouse to move/drag to.

If the user highlighted text in an editor, then asked you to modify it, they probably want you to `keyboard.write` it over their version of the text.

Tasks are 100% computer-based. DO NOT simply write long messages to the user to complete tasks. You MUST put your text back into the program they're using to deliver your text! For example, overwriting some text they've highlighted with `keyboard.write`.

Use keyboard navigation when reasonably possible, but not if it involves pressing a button multiple times. The mouse is less reliable. Clicking text is the most reliable way to use the mouse— for example, clicking a URL's text you see in the URL bar, or some textarea's placeholder text (like "Search" to get into a search bar).

Applescript might be best for some tasks.
        
If you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you.

**Include `computer.screenshot()` after a 2 second delay at the end of _every_ code block to verify your progress on the task.**

Try multiple methods before saying the task is impossible. **You can do it!**

You are an expert computer navigator, brilliant and technical. **At each step, describe the user's screen with a lot of detail, including 1. the active app, 2. what text areas appear to be active, 3. what text is selected, if any, 4. what options you could take next.** Think carefully, and break the task down into short code blocks. DO NOT TRY TO WRITE CODE THAT DOES THE ENTIRE TASK ALL AT ONCE. Take multiple steps. Verify at each step whether or not you're on track.

# Verifying web based tasks (required)
In order to verify if a web-based task is complete, use a hotkey that will go to the URL bar, then select all, then copy the contents of the URL bar. Then use clipboard to review the contents of the URL bar, which may be different from the visual appearance.

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

        # FOR TESTING ONLY
        # Install Open Interpreter from GitHub
        # for chunk in interpreter.computer.run(
        #     "shell",
        #     "pip install git+https://github.com/KillianLucas/open-interpreter.git",
        # ):
        #     if chunk.get("format") != "active_line":
        #         print(chunk.get("content"))

        # Give it access to the computer via Python
        for _ in interpreter.computer.run(
            "python",
            "import time\nimport interpreter\ncomputer = interpreter.computer",  # We ask it to use time, so
        ):
            pass

        display_markdown_message(
            "**Warning:** In this mode, Open Interpreter will not require approval before performing actions. Be ready to close your terminal."
        )
        print("")  # < - Aesthetic choice

    if args.local:
        # Default local (LM studio) attributes

        if not (args.os or args.vision):
            interpreter.system_message = "You are Open Interpreter, a world-class programmer that can execute code on the user's machine."

        interpreter.offline = True
        interpreter.llm.model = "openai/x"  # "openai/" tells LiteLLM it's an OpenAI compatible server, the "x" part doesn't matter
        interpreter.llm.api_base = "http://localhost:1234/v1"
        interpreter.llm.max_tokens = 1000
        interpreter.llm.context_window = 3000
        interpreter.llm.api_key = "x"

        if not (args.os or args.vision):
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
        else:
            if args.vision:
                display_markdown_message(
                    f"> `Local Vision` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background **and using a vision-compatible model**.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
                )
                time.sleep(1)
                display_markdown_message("---\n")
            elif args.os:
                time.sleep(1)
                display_markdown_message("*Setting up local OS control...*\n")
                time.sleep(2.5)
                display_markdown_message("---")
                display_markdown_message(
                    f"> `Local Vision` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background **and using a vision-compatible model**.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
                )
            else:
                time.sleep(1)
                display_markdown_message(
                    f"> `Local Mode` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
                )

    # Check for update
    try:
        if not args.offline:
            # This message should actually be pushed into the utility
            if check_for_update():
                display_markdown_message(
                    "> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---"
                )
    except:
        # Doesn't matter
        pass

    # Set attributes on interpreter
    for attr_name, attr_value in vars(args).items():
        if attr_value != None:
            # If the user has provided a config file, load it and extend interpreter's configuration
            if attr_name == "config_file":
                user_config = get_config_path(attr_value)
                interpreter.config_file = user_config
                interpreter.extend_config(config_path=user_config)
            else:
                argument_dictionary = [a for a in arguments if a["name"] == attr_name]
                if len(argument_dictionary) > 0:
                    argument_dictionary = argument_dictionary[0]
                    if "attribute" in argument_dictionary:
                        attr_dict = argument_dictionary["attribute"]
                        setattr(attr_dict["object"], attr_dict["attr_name"], attr_value)

                        if args.debug_mode:
                            print(
                                f"Setting attribute {attr_name} on {attr_dict['object'].__class__.__name__.lower()} to '{attr_value}'..."
                            )

    if interpreter.llm.model == "gpt-4-1106-preview":
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 128000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = True

    if interpreter.llm.model == "gpt-3.5-turbo-1106":
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 16000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = True

    validate_llm_settings(interpreter)

    # If we've set a custom api base, we want it to be sent in an openai compatible way.
    # So we need to tell LiteLLM to do this by changing the model name:
    if interpreter.llm.api_base:
        if not interpreter.llm.model.lower().startswith("openai/"):
            interpreter.llm.model = "openai/" + interpreter.llm.model

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    interpreter.chat()
