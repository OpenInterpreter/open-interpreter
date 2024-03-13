import re

from ...utils.html_to_png_base64 import html_to_png_base64
from ..base_language import BaseLanguage

template = """<!DOCTYPE html>
<html>
<head>
    <title>React App</title>
</head>
<body>
    <div id="root"></div>

    <!-- React and ReactDOM from CDN -->
    <script crossorigin src="https://unpkg.com/react@17/umd/react.development.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@17/umd/react-dom.development.js"></script>

    <!-- Babel for JSX parsing -->
    <script crossorigin src="https://unpkg.com/@babel/standalone@7.12.1/babel.min.js"></script>

    <!-- React code here -->
    <script type="text/babel">
        {insert_react_code}
    </script>
</body>
</html>"""


def is_incompatible(code):
    lines = code.split("\n")

    # Check for require statements at the start of any of the first few lines
    # Check for ES6 import/export statements
    for line in lines[:5]:
        if re.match(r"\s*require\(", line):
            return True
        if re.match(r"\s*import\s", line) or re.match(r"\s*export\s", line):
            return True

    return False


class React(BaseLanguage):
    name = "React"
    file_extension = "html"

    # system_message = "When you execute code with `react`, your react code will be run in a script tag after being inserted into the HTML template, following the installation of React, ReactDOM, and Babel for JSX parsing. **We will handle this! Don't make an HTML file to run React, just execute `react`.**"

    def run(self, code):
        if is_incompatible(code):
            yield {
                "type": "console",
                "format": "output",
                "content": f"Error: React format not supported. {self.system_message} Therefore some things like `require` and 'import' aren't supported.",
                "recipient": "assistant",
            }
            return

        code = template.replace("{insert_react_code}", code)

        yield {
            "type": "console",
            "format": "output",
            "content": "React is being displayed on the user's machine...",
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
