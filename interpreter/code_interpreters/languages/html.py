import webbrowser
import tempfile
import os
from typing import Optional

from ..base_code_interpreter import BaseCodeInterpreter

class HTML(BaseCodeInterpreter):
    file_extension = "html"
    proper_name = "HTML"

    def __init__(self, sandbox: bool, e2b_api_key: Optional[str]):
        super().__init__(sandbox=sandbox, e2b_api_key=e2b_api_key)

    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        # Open the HTML file with the default web browser
        webbrowser.open('file://' + os.path.realpath(f.name))

        yield {"output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."}