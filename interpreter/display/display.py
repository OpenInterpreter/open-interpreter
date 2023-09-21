def chat_with_display(interpreter, message):

    active_block = None
    console = Console()

    for chunk in interpreter.chat(display=False, message):
        if "message" in chunk:
            if active_block.type != "content":
                active_block.end()
                active_block = message_block()

        if "code" in chunk:
            if active_block.type != "code":
                active_block.end()
                active_block = code_block()
                active_block.language = chunk["language"]

        if "active_line" in chunk:
            active_block.active_line = chunk["active_line"]
        
        if "code_output" in chunk:
            active_block.output += "\n" + chunk["code_output"]

        active_block.refresh()