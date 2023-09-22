"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it
"""

from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .magic_commands import handle_magic_command
from ..utils.display_markdown_message import display_markdown_message

def terminal_interface(interpreter, message):
    if not interpreter.auto_run:
        display_markdown_message("""
        **Open Interpreter** will require approval before running code. Use `interpreter -y` to bypass this.

        Press `CTRL-C` to exit.
        """)
    
    active_block = None

    if message:
        interactive = False
    else:
        interactive = True

    while True:
        try:
            if interactive:
                message = input("> ").strip()
        except KeyboardInterrupt:
            # Exit gracefully
            break

        if message.startswith("%") and interactive:
            handle_magic_command(interpreter, message)
            continue

        # Track if we've ran a code block.
        # We'll use this to determine if we should render a new code block,
        # In the event we get code -> output -> code again
        ran_code_block = False
        render_cursor = False
            
        try:
            for chunk in interpreter.chat(message, display=False, stream=True):
                if interpreter.debug_mode:
                    print("Chunk in `terminal_interface`:", chunk)
                
                # Message
                if "message" in chunk:
                    if active_block is None:
                        active_block = MessageBlock()
                    if active_block.type != "message":
                        active_block.end()
                        active_block = MessageBlock()
                    active_block.message += chunk["message"]

                # Code
                if "code" in chunk or "language" in chunk:
                    if active_block is None:
                        active_block = CodeBlock()
                    if active_block.type != "code" or ran_code_block:
                        # If the last block wasn't a code block,
                        # or it was, but we already ran it:
                        active_block.end()
                        active_block = CodeBlock()
                    ran_code_block = False
                    render_cursor = True
                
                if "language" in chunk:
                    active_block.language = chunk["language"]
                if "code" in chunk:
                    active_block.code += chunk["code"]
                if "active_line" in chunk:
                    active_block.active_line = chunk["active_line"]

                # Output
                if "output" in chunk:
                    ran_code_block = True
                    render_cursor = False
                    active_block.output += "\n" + chunk["output"]
                    active_block.output = active_block.output.strip() # <- Aesthetic choice

                if active_block:
                    active_block.refresh(cursor=render_cursor)

                yield chunk

            # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
            if active_block:
                active_block.end()
                active_block = None

            if not interactive:
                # Don't loop
                break

        except KeyboardInterrupt:
            # Exit gracefully (this cancels LLM, returns to the interactive "> " input)
            active_block.end()
            active_block = None
            continue