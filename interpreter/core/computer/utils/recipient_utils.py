def format_to_recipient(text, recipient):
    return f"@@@RECIPIENT:{recipient}@@@CONTENT:{text}@@@END"


def parse_for_recipient(content):
    if content.startswith("@@@RECIPIENT:") and "@@@END" in content:
        parts = content.split("@@@")
        recipient = parts[1].split(":")[1]
        new_content = parts[2].split(":")[1]
        return recipient, new_content
    return None, content
