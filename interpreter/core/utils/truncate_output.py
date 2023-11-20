def truncate_output(data, max_output_chars=2000):
    needs_truncation = False

    message = f"Output truncated. Showing the last {max_output_chars} characters.\n\n"

    # Remove previous truncation message if it exists
    if data.startswith(message):
        data = data[len(message) :]
        needs_truncation = True

    # If data exceeds max length, truncate it and add message
    if len(data) > max_output_chars or needs_truncation:
        data = message + data[-max_output_chars:]

    return data
