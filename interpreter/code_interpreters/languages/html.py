import webbrowser
import tempfile
import os
from ..base_code_interpreter import BaseCodeInterpreter

class HTML(BaseCodeInterpreter):
    file_extension = "html"
    proper_name = "HTML"

<<<<<<< HEAD
    def __init__(self, **kwargs):
        super().__init__(**kwargs) # include kwargs though they dont do anything in this case.
                                   # This is just so we dont need more logic in the create interpreter function
=======
    def __init__(self):
        super().__init__()
>>>>>>> upstream/main

    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        # Open the HTML file with the default web browser
        webbrowser.open('file://' + os.path.realpath(f.name))

        yield {"output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."}