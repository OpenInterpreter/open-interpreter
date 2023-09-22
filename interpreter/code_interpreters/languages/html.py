"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import webbrowser
import tempfile
import os
from ..base_code_interpreter import BaseCodeInterpreter

class HTML(BaseCodeInterpreter):
    def __init__(self):
        super().__init__()

    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        # Open the HTML file with the default web browser
        webbrowser.open('file://' + os.path.realpath(f.name))

        yield {"output": f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."}
