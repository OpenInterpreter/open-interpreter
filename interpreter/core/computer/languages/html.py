from ...utils.html_to_base64 import html_to_base64
from ..base_language import BaseLanguage


class HTML(BaseLanguage):
    file_extension = "html"
    name = "HTML"

    def __init__(self):
        super().__init__()

    def run(self, code):
        # User sees interactive HTML
        yield {"type": "code", "format": "html", "content": code, "recipient": "user"}

        # Assistant sees image
        base64 = html_to_base64(code)
        yield {
            "type": "image",
            "format": "base64",
            "content": base64,
            "recipient": "assistant",
        }
