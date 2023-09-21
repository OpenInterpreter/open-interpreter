from .code_block import CodeBlock
from .message_block import MessageBlock

def display(interpreter, message):
    active_block = None

    for chunk in interpreter.chat(message, display=False, stream=True):
        if "message" in chunk:
            if active_block is None:
                active_block = MessageBlock()
            if active_block.type != "message":
                active_block.end()
                active_block = MessageBlock()
            active_block.message += chunk["message"]

        if "code" in chunk:
            if active_block is None:
                active_block = CodeBlock()
            if active_block.type != "code":
                active_block.end()
                active_block = CodeBlock()
                active_block.language = chunk["language"]
            active_block.code += chunk["code"]

        if "active_line" in chunk:
            active_block.active_line = chunk["active_line"]
        
        if "output" in chunk:
            # This only happens if the last block was a CodeBlock.
            active_block.output += "\n" + chunk["output"]

        active_block.refresh()

        yield chunk

    active_block.end()