from ...utils.html_to_png_base64 import html_to_png_base64
from ..base_language import BaseLanguage


class HTML(BaseLanguage):
    file_extension = "html"
    name = "HTML"

    def __init__(self):
        super().__init__()

    def run(self, code):
        # Assistant should know what's going on
        yield {
            "type": "console",
            "format": "output",
            "content": "HTML being displayed on the user's machine...",
            "recipient": "assistant",
        }

        # User sees interactive HTML
        yield {"type": "code", "format": "html", "content": code, "recipient": "user"}

        # Assistant sees image
        base64 = html_to_png_base64(code)
        yield {
            "type": "image",
            "format": "base64.png",
            "content": base64,
            "recipient": "assistant",
        }
