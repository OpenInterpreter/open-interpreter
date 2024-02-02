"""
This is all messed up.... Uses the old streaming structure.
"""


from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .utils.display_markdown_message import display_markdown_message


def render_past_conversation(messages):
    # This is a clone of the terminal interface.
    # So we should probably find a way to deduplicate...

    active_block = None
    render_cursor = False
    ran_code_block = False

    for chunk in messages:
        # Only addition to the terminal interface:
        if chunk["role"] == "user":
            if active_block:
                active_block.end()
                active_block = None
            print(">", chunk["content"])
            continue

        # Message
        if chunk["type"] == "message":
            if active_block is None:
                active_block = MessageBlock()
            if active_block.type != "message":
                active_block.end()
                active_block = MessageBlock()
            active_block.message += chunk["content"]

        # Code
        if chunk["type"] == "code":
            if active_block is None:
                active_block = CodeBlock()
            if active_block.type != "code" or ran_code_block:
                # If the last block wasn't a code block,
                # or it was, but we already ran it:
                active_block.end()
                active_block = CodeBlock()
            ran_code_block = False
            render_cursor = True

            if "format" in chunk:
                active_block.language = chunk["format"]
            if "content" in chunk:
                active_block.code += chunk["content"]
            if "active_line" in chunk:
                active_block.active_line = chunk["active_line"]

        # Console
        if chunk["type"] == "console":
            ran_code_block = True
            render_cursor = False
            active_block.output += "\n" + chunk["content"]
            active_block.output = active_block.output.strip()  # <- Aesthetic choice

        if active_block:
            active_block.refresh(cursor=render_cursor)

    # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
    if active_block:
        active_block.end()
        active_block = None
