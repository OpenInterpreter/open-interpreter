import argparse
import os
import platform
import re
import subprocess
import sys
import time

import pkg_resources

from .conversation_navigator import conversation_navigator
from .utils.apply_config import apply_config
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
            "name": "verbose",
            "nickname": "v",
            "help_text": "print detailed logs",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "verbose"},
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
            "name": "api_version",
            "nickname": "av",
            "help_text": "optionally set the API version for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_version"},
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
            "name": "disable_telemetry",
            "nickname": "dt",
            "help_text": "disables sending of basic anonymous usage stats",
            "type": bool,
            "default": True,
            "action": "store_false",
            "attribute": {"object": interpreter, "attr_name": "anonymous_telemetry"},
        },
        {
            "name": "speak_messages",
            "nickname": "sm",
            "help_text": "(Mac only) use the applescript `say` command to read messages aloud",
            "type": bool,
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
            "nickname": "vi",
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
            "name": "reset_config",
            "help_text": "reset config.yaml to default",
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

    # Check for deprecated flags before parsing arguments
    if "--debug_mode" in sys.argv or "-d" in sys.argv:
        print("\n`--debug_mode` / `-d` has been renamed to `--verbose` / `-v`.\n")
        time.sleep(1.5)
        if "--debug_mode" in sys.argv:
            sys.argv.remove("--debug_mode")
        if "-d" in sys.argv:
            sys.argv.remove("-d")
        sys.argv.append("--verbose")

    parser = argparse.ArgumentParser(description="Open Interpreter")

    # Add arguments
    for arg in arguments:
        action = arg.get("action", "store_true")
        nickname = arg.get("nickname")
        default = arg.get("default")

        if arg["type"] == bool:
            if nickname:
                parser.add_argument(
                    f"-{nickname}",
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=default,
                )
            else:
                parser.add_argument(
                    f'--{arg["name"]}',
                    dest=arg["name"],
                    help=arg["help_text"],
                    action=action,
                    default=default,
                )
        else:
            choices = arg.get("choices")

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

    # This should be pushed into a utility:
    if args.reset_config:
        if args.config_file:
            config_file = get_config_path(args.config_file)
        else:
            config_file = get_config_path()
        if os.path.exists(config_file):
            os.remove(config_file)
            config_file = get_config_path()
            print("`config.yaml` has been reset.")
        else:
            print("`config.yaml` does not exist.")
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

        if not args.model:
            # This will cause it to override the config, which is what we want
            args.model = "gpt-4-vision-preview"

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
        interpreter.llm.supports_vision = True
        # interpreter.shrink_images = True # Faster but less accurate

        if not args.model:
            args.model = "gpt-4-vision-preview"

        interpreter.llm.supports_functions = False
        interpreter.llm.context_window = 110000
        interpreter.llm.max_tokens = 4096
        interpreter.auto_run = True
        interpreter.force_task_completion = True

        interpreter.system_message = """
        
You are Open Interpreter, a world-class programmer that can complete any goal by executing code.

When you write code, it will be executed **on the user's machine**. The user has given you **full and complete permission** to execute any code necessary to complete the task.

When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.

In general, try to make plans with as few steps as possible. As for actually executing code to carry out that plan, **don't try to do everything in one code block.** You should try something, print information about it, then continue from there in tiny, informed steps. You will never get it on the first try, and attempting it in one go will often lead to errors you cant see.

Manually summarize text.

Do not try to write code that attempts the entire task at once, and verify at each step whether or not you're on track.

# Computer

You may use the `computer` Python module to complete tasks:

```python
computer.display.view() # Shows you what's on the screen, returns a `pil_image` `in case you need it (rarely). **You almost always want to do this first!**

computer.keyboard.hotkey(" ", "command") # Opens spotlight (very useful)
computer.keyboard.write("hello")

computer.mouse.click("text onscreen") # This clicks on the UI element with that text. Use this **frequently** and get creative! To click a video, you could pass the *timestamp* (which is usually written on the thumbnail) into this.
computer.mouse.move("open recent >") # This moves the mouse over the UI element with that text. Many dropdowns will disappear if you click them. You have to hover over items to reveal more.
computer.mouse.click(x=500, y=500) # Use this very, very rarely. It's highly inaccurate
computer.mouse.click(icon="gear icon") # Moves mouse to the icon with that description. Use this very often

computer.mouse.scroll(-10) # Scrolls down. If you don't find some text on screen that you expected to be there, you probably want to do this
x, y = computer.display.center() # Get your bearings

computer.clipboard.view() # Returns contents of clipboard
computer.os.get_selected_text() # Use frequently. If editing text, the user often wants this
```

For rare and complex mouse actions, consider using computer vision libraries on the `computer.display.view()` `pil_image` to produce a list of coordinates for the mouse to move/drag to.

If the user highlighted text in an editor, then asked you to modify it, they probably want you to `keyboard.write` over their version of the text.

Tasks are 100% computer-based. DO NOT simply write long messages to the user to complete tasks. You MUST put your text back into the program they're using to deliver your text!

Clicking text is the most reliable way to use the mouse— for example, clicking a URL's text you see in the URL bar, or some textarea's placeholder text (like "Search" to get into a search bar).

Applescript might be best for some tasks.

If you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you.

It is very important to make sure you are focused on the right application and window. Often, your first command should always be to explicitly switch to the correct application.

When searching the web, use query parameters. For example, https://www.amazon.com/s?k=monitor

Try multiple methods before saying the task is impossible. **You can do it!**

# Critical Routine Procedure for Multi-Step Tasks

Include `computer.display.view()` after a 2 second delay at the end of _every_ code block to verify your progress, then answer these questions in extreme detail:

1. Generally, what is happening on-screen?
2. What is the active app?
3. What hotkeys does this app support that might get be closer to my goal?
4. What text areas are active, if any?
5. What text is selected?
6. What options could you take next to get closer to your goal?
        
        """.strip()

        # Check if required packages are installed

        # THERE IS AN INCONSISTENCY HERE.
        # We should be testing if they import WITHIN OI's computer, not here.

        packages = ["cv2", "plyer", "pyautogui", "pyperclip", "pywinctl"]
        missing_packages = []
        for package in packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            display_markdown_message(
                f"> **Missing Package(s): {', '.join(['`' + p + '`' for p in missing_packages])}**\n\nThese packages are required for OS Control.\n\nInstall them?\n"
            )
            user_input = input("(y/n) > ")
            if user_input.lower() != "y":
                print("Exiting...")
                return

            for pip_name in ["pip", "pip3"]:
                command = f"{pip_name} install 'open-interpreter[os]'"

                for chunk in interpreter.computer.run("shell", command):
                    if chunk.get("format") != "active_line":
                        print(chunk.get("content"))

                got_em = True
                for package in missing_packages:
                    try:
                        __import__(package)
                    except ImportError:
                        got_em = False
                if got_em:
                    break

            missing_packages = []
            for package in packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)

            if missing_packages != []:
                print(
                    "\n\nWarning: The following packages could not be installed:",
                    ", ".join(missing_packages),
                )
                print("\nPlease try to install them manually.\n\n")
                time.sleep(2)
                print("Attempting to start OS control anyway...\n\n")

        display_markdown_message("> `OS Control` enabled")

        # Should we explore other options for ^ these kinds of tags?
        # Like:

        # from rich import box
        # from rich.console import Console
        # from rich.panel import Panel
        # console = Console()
        # print(">\n\n")
        # console.print(Panel("[bold italic white on black]OS CONTROL[/bold italic white on black] Enabled", box=box.SQUARE, expand=False), style="white on black")
        # print(">\n\n")
        # console.print(Panel("[bold italic white on black]OS CONTROL[/bold italic white on black] Enabled", box=box.HEAVY, expand=False), style="white on black")
        # print(">\n\n")
        # console.print(Panel("[bold italic white on black]OS CONTROL[/bold italic white on black] Enabled", box=box.DOUBLE, expand=False), style="white on black")
        # print(">\n\n")
        # console.print(Panel("[bold italic white on black]OS CONTROL[/bold italic white on black] Enabled", box=box.SQUARE, expand=False), style="white on black")

        if not args.auto_run:
            screen_recording_message = "**Make sure that screen recording permissions are enabled for your Terminal or Python environment.**"
            display_markdown_message(screen_recording_message)
            print("")

        # # FOR TESTING ONLY
        # # Install Open Interpreter from GitHub
        # for chunk in interpreter.computer.run(
        #     "shell",
        #     "pip install git+https://github.com/KillianLucas/open-interpreter.git",
        # ):
        #     if chunk.get("format") != "active_line":
        #         print(chunk.get("content"))

        # Give it access to the computer via Python
        for _ in interpreter.computer.run(
            "python",
            "import time\nfrom interpreter import interpreter\ncomputer = interpreter.computer",  # We ask it to use time, so
        ):
            if args.verbose:
                print(_.get("content"))
            pass

        if not args.auto_run:
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

    # Apply config
    if args.config_file:
        user_config = get_config_path(args.config_file)
        interpreter = apply_config(interpreter, config_path=user_config)
    else:
        # Apply default config file
        interpreter = apply_config(interpreter)

    # Set attributes on interpreter
    for argument_name, argument_value in vars(args).items():
        if argument_value != None:
            argument_dictionary = [a for a in arguments if a["name"] == argument_name]
            if len(argument_dictionary) > 0:
                argument_dictionary = argument_dictionary[0]
                if "attribute" in argument_dictionary:
                    attr_dict = argument_dictionary["attribute"]
                    setattr(attr_dict["object"], attr_dict["attr_name"], argument_value)

                    if args.verbose:
                        print(
                            f"Setting attribute {attr_dict['attr_name']} on {attr_dict['object'].__class__.__name__.lower()} to '{argument_value}'..."
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

    # If we've set a custom api base, we want it to be sent in an openai compatible way.
    # So we need to tell LiteLLM to do this by changing the model name:
    if interpreter.llm.api_base:
        if not interpreter.llm.model.lower().startswith(
            "openai/"
        ) and not interpreter.llm.model.lower().startswith("azure/"):
            interpreter.llm.model = "openai/" + interpreter.llm.model

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    validate_llm_settings(interpreter)

    interpreter.in_terminal_interface = True

    interpreter.chat()
