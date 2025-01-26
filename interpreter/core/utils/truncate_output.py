def truncate_output(data, max_output_chars=2800, add_scrollbars=False):
    # if "@@@DO_NOT_TRUNCATE@@@" in data:
    #     return data

    needs_truncation = False

    # Calculate how much to show from start and end
    chars_per_end = max_output_chars // 2

    message = (f"Output truncated ({len(data):,} characters total). "
               f"Showing {chars_per_end:,} characters from start/end. "
               "To handle large outputs, store result in python var first "
               "`result = command()` then `computer.ai.summarize(result)` for "
               "a summary, search with `result.find('text')`, "
               "repeat shell commands with wc/grep/sed, etc. or break it down "
               "into smaller steps.\n\n")

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
        first_part = data[:chars_per_end]
        last_part = data[-chars_per_end:]
        data = message + first_part + "\n[...]\n" + last_part

    return data
