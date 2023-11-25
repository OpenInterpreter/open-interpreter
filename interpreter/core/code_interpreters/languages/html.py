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
        ## This has been offloaded to the terminal interface
        # Create a temporary HTML file with the content
        # with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
        #     f.write(code.encode())

        # # Open the HTML file with the default web browser
        # webbrowser.open("file://" + os.path.realpath(f.name))

        # yield {
        #     "output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."
        # }

        if self.config["vision"]:
            pass

            # disabled because placeholder is a normal html element lol. how to fix this?
            # Warn LLM about placeholders.
            # if "placeholder" in code.lower() or "will go here" in code.lower():
            #     yield {
            #         "output": "\n\nWARNING TO LLM: Placeholder detected. Do NOT use placeholders in HTML code, write the users entire request at once."
            #     }

            # Lmao this is so thin. But html should be accepted output, it's actually terminal interface that will figure out how to render it

        yield {"html": code}
