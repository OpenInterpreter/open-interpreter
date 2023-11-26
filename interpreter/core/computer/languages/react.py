"""
Test this more— I don't think it understands the environment it's in. It tends to write "require" for example. Also make sure errors go back into it (console.log type stuff)
"""

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


class HTML(BaseLanguage):
    file_extension = "html"
    proper_name = "React"

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self, code):
        # Everything happens in the terminal interface re: how you render HTML.
        # In the future though, we should let the TUI do this but then also capture stuff like console.log errors here.

        code = template.replace("{insert_react_code}", code)

        yield {"html": code}
