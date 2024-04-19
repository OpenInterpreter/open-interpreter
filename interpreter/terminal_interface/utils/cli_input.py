def cli_input(prompt: str = "") -> str:
    start_marker = "```"
    end_marker = "```"
    message = input(prompt)

    # Multi-line input mode
    if start_marker in message:
        lines = [message]
        while True:
            line = input()
            lines.append(line)
            if end_marker in line:
                break
        return "\n".join(lines)

    # Single-line input mode
    return message
