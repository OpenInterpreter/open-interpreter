def truncate_output(data, max_output_chars=2800, add_scrollbars=False):
    # if "@@@DO_NOT_TRUNCATE@@@" in data:
    #     return data

    needs_truncation = False

    message = f"Output truncated. Showing the last {max_output_chars} characters. You should try again and use computer.ai.summarize(output) over the output, or break it down into smaller steps.\n\n"

    # This won't work because truncated code is stored in interpreter.messages :/
    # If the full code was stored, we could do this:
    if add_scrollbars:
        message = (
            message.strip()
            + f" Run `get_last_output()[0:{max_output_chars}]` to see the first page.\n\n"
        )
    # Then we have code in `terminal.py` which makes that function work. It should be a computer tool though to just access messages IMO. Or like, self.messages.

    # Remove previous truncation message if it exists
    if data.startswith(message):
        data = data[len(message) :]
        needs_truncation = True

    # If data exceeds max length, truncate it and add message
    if len(data) > max_output_chars or needs_truncation:
        data = message + data[-max_output_chars:]

    return data
