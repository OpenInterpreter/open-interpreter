import requests

from ..ui.markdown import MarkdownRenderer
from .stream_text import stream_text


def desktop_prompt():
    renderer = MarkdownRenderer()
    for chunk in stream_text(
        "To get early access to the **Open Interpreter Desktop App**, please provide the following information:\n\n"
    ):
        renderer.feed(chunk)
    first_name = input("What's your first name? ").strip()
    email = input("What's your email? ").strip()

    url = "https://neyguovvcjxfzhqpkicj.supabase.co/functions/v1/addEmailToWaitlist"
    data = {"first_name": first_name, "email": email}

    try:
        response = requests.post(url, json=data)
    except requests.RequestException as e:
        pass

    for chunk in stream_text("\nWe'll email you shortly. ✓\n---\n"):
        renderer.feed(chunk)

    renderer.close()
