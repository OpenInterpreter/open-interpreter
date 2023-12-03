"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it.
"""

try:
    import readline
except ImportError:
    pass

import time

from ..core.utils.scan_code import scan_code
from ..core.utils.system_debug_info import system_info
from ..core.utils.truncate_output import truncate_output
from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .magic_commands import handle_magic_command
from .utils.check_for_package import check_for_package
from .utils.display_markdown_message import display_markdown_message
from .utils.display_output import display_output
from .utils.find_image_path import find_image_path

# Add examples to the readline history
examples = [
    "How many files are on my desktop?",
    "What time is it in Seattle?",
    "Make me a simple Pomodoro app.",
    "Open Chrome and go to YouTube.",
]
# random.shuffle(examples)
for example in examples:
    readline.add_history(example)


def terminal_interface(interpreter, message):
    # Auto run and local don't display messages.
    # Probably worth abstracting this to something like "verbose_cli" at some point.
    if not interpreter.auto_run and not interpreter.local:
        interpreter_intro_message = [
            "**Open Interpreter** will require approval before running code."
        ]

        if interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto":
            if not check_for_package("semgrep"):
                interpreter_intro_message.append(
                    f"**Safe Mode**: {interpreter.safe_mode}\n\n>Note: **Safe Mode** requires `semgrep` (`pip install semgrep`)"
                )
        else:
            interpreter_intro_message.append("Use `interpreter -y` to bypass this.")

        interpreter_intro_message.append("Press `CTRL-C` to exit.")

        display_markdown_message("\n\n".join(interpreter_intro_message) + "\n")

    if message:
        interactive = False
    else:
        interactive = True

    while True:
        try:
            if interactive:
                message = input("> ").strip()

                try:
                    # This lets users hit the up arrow key for past messages
                    readline.add_history(message)
                except:
                    # If the user doesn't have readline (may be the case on windows), that's fine
                    pass

        except KeyboardInterrupt:
            # Exit gracefully
            # Disconnect from the computer interface
            interpreter.computer.terminate()
            break

        if message.startswith("%") and interactive:
            handle_magic_command(interpreter, message)
            continue

        # Many users do this
        if message.strip() == "interpreter --local":
            print("Please exit this conversation, then run `interpreter --local`.")
            continue
        if message.strip() == "pip install --upgrade open-interpreter":
            print(
                "Please exit this conversation, then run `pip install --upgrade open-interpreter`."
            )
            continue

        if interpreter.vision:
            # Is the input a path to an image? Like they just dragged it into the terminal?
            image_path = find_image_path(message)

            ## If we found an image, add it to the message
            if image_path:
                # Add the text interpreter's messsage history
                interpreter.messages.append(
                    {
                        "role": "user",
                        "type": "message",
                        "content": message,
                    }
                )

                # Pass in the image to interpreter in a moment
                message = {
                    "role": "user",
                    "type": "image",
                    "format": "path",
                    "content": image_path,
                }

        try:
            extra_computer_outputs = []

            for chunk in interpreter.chat(message, display=False, stream=True):
                yield chunk

                # Is this for thine eyes?
                if "recipient" in chunk and chunk["recipient"] != "user":
                    continue

                if interpreter.debug_mode:
                    print("Chunk in `terminal_interface`:", chunk)

                if "stop" in chunk and active_block:
                    active_block.refresh(cursor=False)

                    if chunk["type"] in [
                        "message",
                        "console",
                    ]:  # We don't stop on code's end — code + console output are actually one block.
                        active_block.end()
                        active_block = None

                # Assistant message blocks
                if chunk["type"] == "message":
                    if "start" in chunk:
                        active_block = MessageBlock()
                        render_cursor = True

                    if "content" in chunk:
                        active_block.message += chunk["content"]

                # Assistant code blocks
                elif chunk["role"] == "assistant" and chunk["type"] == "code":
                    if "start" in chunk:
                        active_block = CodeBlock()
                        active_block.language = chunk["format"]
                        render_cursor = True

                    if "content" in chunk:
                        active_block.code += chunk["content"]

                # Execution notice
                if chunk["type"] == "confirmation":
                    if not interpreter.auto_run:
                        # OI is about to execute code. The user wants to approve this

                        # End the active code block so you can run input() below it
                        if active_block:
                            active_block.refresh(cursor=False)
                            active_block.end()
                            active_block = None

                        code_to_run = chunk["content"]
                        language = code_to_run["format"]
                        code = code_to_run["content"]

                        should_scan_code = False

                        if not interpreter.safe_mode == "off":
                            if interpreter.safe_mode == "auto":
                                should_scan_code = True
                            elif interpreter.safe_mode == "ask":
                                response = input(
                                    "  Would you like to scan this code? (y/n)\n\n  "
                                )
                                print("")  # <- Aesthetic choice

                                if response.strip().lower() == "y":
                                    should_scan_code = True

                        if should_scan_code:
                            scan_code(code, language, interpreter)

                        response = input(
                            "  Would you like to run this code? (y/n)\n\n  "
                        )
                        print("")  # <- Aesthetic choice

                        if response.strip().lower() == "y":
                            # Create a new, identical block where the code will actually be run
                            # Conveniently, the chunk includes everything we need to do this:
                            active_block = CodeBlock()
                            active_block.margin_top = False  # <- Aesthetic choice
                            active_block.language = language
                            active_block.code = code
                        else:
                            # User declined to run code.
                            interpreter.messages.append(
                                {
                                    "role": "user",
                                    "type": "message",
                                    "content": "I have declined to run this code.",
                                }
                            )
                            break

                # Computer can display visual types to user,
                # Which sometimes creates more computer output (e.g. HTML errors, eventually)
                if (
                    chunk["role"] == "computer"
                    and "content" in chunk
                    and (
                        chunk["type"] == "image"
                        or ("format" in chunk and chunk["format"] == "html")
                        or ("format" in chunk and chunk["format"] == "javascript")
                    )
                ):
                    computer_output = display_output(chunk)
                    extra_computer_outputs.append(computer_output)

                # Console
                if chunk["type"] == "console" and "format" in chunk:
                    render_cursor = False
                    if chunk["format"] == "output":
                        active_block.output += "\n" + chunk["content"]
                        active_block.output = (
                            active_block.output.strip()
                        )  # ^ Aesthetic choice

                        # Truncate output
                        active_block.output = truncate_output(
                            active_block.output, interpreter.max_output
                        )
                    if chunk["format"] == "active_line":
                        active_block.active_line = chunk["content"]

                if chunk["type"] == "console" and "stop" in chunk:
                    # If we just finished executing, and extra_computer_outputs isn't empty, flush it:
                    if extra_computer_outputs != []:
                        interpreter.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": "\n".join(extra_computer_outputs),
                            }
                        )
                        extra_computer_outputs = []

                if active_block:
                    active_block.refresh(cursor=render_cursor)

            # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
            if active_block:
                active_block.end()
                active_block = None
                time.sleep(0.1)

            # Flush extra_computer_outputs
            if extra_computer_outputs != []:
                interpreter.messages.append(
                    {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": "\n".join(extra_computer_outputs),
                    }
                )
                extra_computer_outputs = []

            if not interactive:
                # Don't loop
                break

        except KeyboardInterrupt:
            # Exit gracefully
            if active_block:
                active_block.end()
                active_block = None

            if interactive:
                # (this cancels LLM, returns to the interactive "> " input)
                continue
            else:
                break
        except:
            system_info(interpreter)
            raise
