from .code_block import CodeBlock
from .message_block import MessageBlock

def terminal_gui(interpreter, message):
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
            
        try:
            for chunk in interpreter.chat(message, display=False, stream=True):
                if interpreter.debug_mode:
                    print("chunk in interactive_display:", chunk)
                
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
                    if active_block.type != "code":
                        active_block.end()
                        active_block = CodeBlock()
                
                if "language" in chunk:
                    active_block.language = chunk["language"]
                if "code" in chunk:
                    active_block.code += chunk["code"]
                if "active_line" in chunk:
                    active_block.active_line = chunk["active_line"]

                # Output
                if "output" in chunk:
                    active_block.output += "\n" + chunk["output"]

                if active_block:
                    active_block.refresh()

                yield chunk

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