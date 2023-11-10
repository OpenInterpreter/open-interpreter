import base64
import os
import tempfile
import webbrowser

from ..base_code_interpreter import BaseCodeInterpreter


class HTML(BaseCodeInterpreter):
    file_extension = "html"
    proper_name = "HTML"

    def __init__(self):
        super().__init__()

    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        # Open the HTML file with the default web browser
        webbrowser.open("file://" + os.path.realpath(f.name))

        yield {
            "output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser.\n\nSending image to GPT-4V..."
        }

        # Warn this thing about placeholders.
        if "placeholder" in code.lower() or "will go here" in code.lower():
            yield {
                "output": "\n\nWARNING TO LLM: Placeholder detected. Do NOT use placeholders in HTML code, write the users entire request at once."
            }

        # Convert the HTML into an image using hcti API
        import requests

        data = {"html": code, "css": "", "google_fonts": ""}
        image = requests.post(
            url="https://hcti.io/v1/image",
            data=data,
            auth=(
                "f6f5b19f-171b-4dd4-a58f-f3ccfd334ffc",
                "529139e4-af2a-4bee-8baf-828823c93a32",
            ),
        )
        screenshot_url = image.json()["url"]

        # Download the image and convert it to base64
        response = requests.get(screenshot_url)
        screenshot_base64 = base64.b64encode(response.content).decode()

        yield {"image": screenshot_base64}
