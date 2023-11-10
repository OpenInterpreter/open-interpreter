import base64
import os
import random
import string
import tempfile
import webbrowser

from html2image import Html2Image

from ..base_code_interpreter import BaseCodeInterpreter


class HTML(BaseCodeInterpreter):
    file_extension = "html"
    proper_name = "HTML"

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        # Open the HTML file with the default web browser
        webbrowser.open("file://" + os.path.realpath(f.name))

        yield {
            "output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."
        }

        if self.config["vision"]:
            yield {"output": "\n\nSending image to GPT-4V..."}

            # Warn LLM about placeholders.
            if "placeholder" in code.lower() or "will go here" in code.lower():
                yield {
                    "output": "\n\nWARNING TO LLM: Placeholder detected. Do NOT use placeholders in HTML code, write the users entire request at once."
                }

            # Convert the HTML into an image using html2image
            hti = Html2Image()

            # Generate a random filename for the temporary image
            temp_filename = "".join(random.choices(string.digits, k=10)) + ".png"
            hti.screenshot(html_str=code, save_as=temp_filename)

            # Convert the image to base64
            with open(temp_filename, "rb") as image_file:
                screenshot_base64 = base64.b64encode(image_file.read()).decode()

            # Delete the temporary image file
            os.remove(temp_filename)

            yield {"image": screenshot_base64}
