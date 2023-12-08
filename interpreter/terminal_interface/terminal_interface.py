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

    just_pressed_ctrl_c = False

    while True:
        try:
            if interactive:
                # I think this could be refactored for more clarity.
                if not just_pressed_ctrl_c and (
                    interpreter.os
                    and interpreter.messages != []
                    and "content" in interpreter.messages[-1]
                    and "The task is done."
                    not in interpreter.messages[-1]["content"].lower()
                ):
                    message = "proceed. if the entire task is done, say exactly 'The task is done.', otherwise keep going."
                else:
                    ### This is the primary input for Open Interpreter.
                    message = input("> ").strip()

                    just_pressed_ctrl_c = (
                        False  # Just used for os mode, to escape the loop above^
                    )

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
            for chunk in interpreter.chat(message, display=False, stream=True):
                yield chunk

                # Is this for thine eyes?
                if "recipient" in chunk and chunk["recipient"] != "user":
                    continue

                if interpreter.debug_mode:
                    print("Chunk in `terminal_interface`:", chunk)

                if "end" in chunk and active_block:
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
                        if interpreter.os:
                            # OS mode uses voice — otherwise you can't tell what it's doing!
                            active_block.voice = True
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
                    if interpreter.os:
                        # We don't display things to the user in OS control mode, since we use vision to communicate the screen to the LLM so much.
                        continue
                    # Display and give extra output back to the LLM
                    extra_computer_output = display_output(chunk)
                    if (
                        interpreter.messages[-1].get("format") != "output"
                        or interpreter.messages[-1]["role"] != "computer"
                        or interpreter.messages[-1]["type"] != "console"
                    ):
                        # If the last message isn't a console output, make a new block
                        interpreter.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": extra_computer_output,
                            }
                        )
                    else:
                        # If the last message is a console output, simply append the extra output to it
                        interpreter.messages[-1]["content"] += (
                            "\n" + extra_computer_output
                        )
                        interpreter.messages[-1]["content"] = interpreter.messages[-1][
                            "content"
                        ].strip()

                # Console
                if chunk["type"] == "console":
                    render_cursor = False
                    if "format" in chunk and chunk["format"] == "output":
                        active_block.output += "\n" + chunk["content"]
                        active_block.output = (
                            active_block.output.strip()
                        )  # ^ Aesthetic choice

                        # Truncate output
                        active_block.output = truncate_output(
                            active_block.output, interpreter.max_output
                        )
                    if "format" in chunk and chunk["format"] == "active_line":
                        active_block.active_line = chunk["content"]

                    if "start" in chunk:
                        # We need to make a code block if we pushed out an HTML block first, which would have closed our code block.
                        if not isinstance(active_block, CodeBlock):
                            if active_block:
                                active_block.end()
                            active_block = CodeBlock()

                if active_block:
                    active_block.refresh(cursor=render_cursor)

            # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
            if "active_block" in locals():
                if active_block:
                    active_block.end()
                    active_block = None
                    time.sleep(0.1)

            if not interactive:
                # Don't loop
                break

        except KeyboardInterrupt:
            just_pressed_ctrl_c = True

            # Exit gracefully
            if "active_block" in locals():
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
