from .code_block import CodeBlock
from .message_block import MessageBlock

def interactive_display(interpreter, message):
    active_block = None

    if message:
        interactive = False
    else:
        interactive = True

    while True:
        if interactive:
            message = input("> ").strip()
        
        for chunk in interpreter.chat(message, display=False, stream=True):

            if interpreter.debug_mode:
                print("chunk in interactive_display:", chunk)
            
            if "message" in chunk:
                if active_block is None:
                    active_block = MessageBlock()
                if active_block.type != "message":
                    active_block.end()
                    active_block = MessageBlock()
                active_block.message += chunk["message"]

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
            
            if "output" in chunk:
                # This only happens if the last block was a CodeBlock.
                active_block.output += "\n" + chunk["output"]

            if active_block:
                active_block.refresh()

            yield chunk

        active_block.end()
        active_block = None

        if not interactive:
            # Don't loop
            break
