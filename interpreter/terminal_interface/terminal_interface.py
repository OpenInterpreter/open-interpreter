"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it.
"""

try:
    import readline
except ImportError:
    pass

import platform
import re
import subprocess
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

    pause_force_task_completion_loop = False
    force_task_completion_message = """Proceed. If you want to write code, start your message with "```"! If the entire task I asked for is done, say exactly 'The task is done.' If it's impossible, say 'The task is impossible.' (If I haven't provided a task, say exactly 'Let me know what you'd like to do next.') Otherwise keep going."""
    force_task_completion_responses = [
        "the task is done.",
        "the task is impossible.",
        "let me know what you'd like to do next.",
    ]
    voice_subprocess = None

    while True:
        try:
            if interactive:
                # FORCE TASK COMPLETION
                ### I think `force_task_completion` should be moved to the core.
                # `force_task_completion` makes it utter specific phrases if it doesn't want to be told to "Proceed."
                if (
                    not pause_force_task_completion_loop
                    and interpreter.force_task_completion
                    and interpreter.messages
                    and not any(
                        task_status
                        in interpreter.messages[-1].get("content", "").lower()
                        for task_status in force_task_completion_responses
                    )
                ):
                    # Remove past force_task_completion messages
                    interpreter.messages = [
                        message
                        for message in interpreter.messages
                        if message.get("content", "") != force_task_completion_message
                    ]
                    # Combine adjacent assistant messages, so hopefully it learns to just keep going!
                    combined_messages = []
                    for message in interpreter.messages:
                        if (
                            combined_messages
                            and message["role"] == "assistant"
                            and combined_messages[-1]["role"] == "assistant"
                            and message["type"] == "message"
                            and combined_messages[-1]["type"] == "message"
                        ):
                            combined_messages[-1]["content"] += (
                                "\n" + message["content"]
                            )
                        else:
                            combined_messages.append(message)
                    interpreter.messages = combined_messages
                    # Send model the force_task_completion_message:
                    message = force_task_completion_message
                else:
                    ### This is the primary input for Open Interpreter.
                    message = input("> ").strip()

                    pause_force_task_completion_loop = False  # Just used for `interpreter.force_task_completion`, to escape the loop above^

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

        if isinstance(message, str):
            # This is for the terminal interface being used as a CLI — messages are strings.
            # This won't fire if they're in the python package, display=True, and they passed in an array of messages (for example).

            if message.startswith("%") and interactive:
                handle_magic_command(interpreter, message)
                pause_force_task_completion_loop = True
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

                # Comply with PyAutoGUI fail-safe for OS mode
                # so people can turn it off by moving their mouse to a corner
                if interpreter.os:
                    if (
                        chunk.get("format") == "output"
                        and "FailSafeException" in chunk["content"]
                    ):
                        pause_force_task_completion_loop = True
                        break

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
                        render_cursor = True

                    if "content" in chunk:
                        active_block.message += chunk["content"]

                    if "end" in chunk and interpreter.os:
                        last_message = interpreter.messages[-1]["content"]
                        if (
                            platform.system() == "Darwin"
                            and last_message not in force_task_completion_responses
                        ):
                            # Remove markdown lists and the line above markdown lists
                            lines = last_message.split("\n")
                            i = 0
                            while i < len(lines):
                                # Match markdown lists starting with hyphen, asterisk or number
                                if re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                                    del lines[i]
                                    if i > 0:
                                        del lines[i - 1]
                                        i -= 1
                                else:
                                    i += 1
                            message = "\n".join(lines)
                            # Replace newlines with spaces, escape double quotes and backslashes
                            sanitized_message = (
                                message.replace("\\", "\\\\")
                                .replace("\n", " ")
                                .replace('"', '\\"')
                            )
                            if voice_subprocess:
                                voice_subprocess.terminate()
                            voice_subprocess = subprocess.Popen(
                                [
                                    "osascript",
                                    "-e",
                                    f'say "{sanitized_message}" using "Fred"',
                                ]
                            )

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
