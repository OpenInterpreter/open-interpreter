import json
import os
import random
import sys

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_all_styles
from yaspin import yaspin
from yaspin.spinners import Spinners


class ContentRenderer:
    def __init__(self, style):
        self.buffer = ""
        self.started = False
        self.style = style

    def feed(self, content):
        pass

    def flush(self):
        pass


class CodeRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        self.line_number = 1
        self.code_lang = "python"
        self.buffer = ""
        self.rendered_content = ""
        self.spinner = yaspin(Spinners.simpleDots, text="  ")
        self.is_spinning = False

    def feed(self, content):
        # Start spinner if we have content to process
        if not self.is_spinning and content.strip():
            self.spinner.start()
            self.is_spinning = True

        # Only process the new part of the content
        if len(content) <= len(self.rendered_content):
            return

        # Get only the new content
        new_content = content[len(self.rendered_content) :]
        self.buffer += new_content
        self.rendered_content = content  # Update what we've seen

        # Process complete lines
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                if self.is_spinning:
                    self.spinner.stop()
                    self.is_spinning = False
                self._render_line(line)
                if lines[-1].strip():  # If there's more content coming
                    self.spinner.start()
                    self.is_spinning = True
            self.buffer = lines[-1]  # Keep the incomplete line

    def _render_line(self, line):
        try:
            lexer = get_lexer_by_name(self.code_lang)
        except:
            lexer = TextLexer()

        formatter = Terminal256Formatter(style=self.style)

        # Highlight the line
        highlighted = highlight(line + "\n", lexer, formatter).rstrip()
        line_prefix = f"{SchemaRenderer.GRAY_COLOR}{str(self.line_number).rjust(3)} │ {SchemaRenderer.RESET_COLOR}"

        sys.stdout.write(f"{line_prefix}{highlighted}\n")
        sys.stdout.flush()
        self.line_number += 1

    def flush(self):
        if self.is_spinning:
            self.spinner.stop()
            self.is_spinning = False
        if self.buffer:
            self._render_line(self.buffer)
            self.buffer = ""


class PathRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        self.rendered_content = ""  # Track what we've already rendered

    def feed(self, content):
        # Only render new content
        new_content = content[len(self.rendered_content) :]
        if new_content:
            sys.stdout.write(f"{new_content}")
            sys.stdout.flush()
            self.rendered_content += new_content


class CommandRenderer(ContentRenderer):
    ICONS = {
        "create": "✦",
        "view": "⚆",
        "str_replace": "↻",
        "insert": "⊹",
        "undo_edit": "↫",
    }

    def __init__(self, style):
        super().__init__(style)
        self.buffer = ""
        self.rendered_commands = set()  # Track complete commands we've rendered

    def feed(self, content):
        # If we've already rendered this complete command, skip
        if content in self.rendered_commands:
            return

        # Buffer the content
        self.buffer = content

        # If this is a complete command (matches one of our icons), render it
        if content.strip() in self.ICONS:
            icon = self.ICONS.get(content.strip(), "•")
            ICON_COLOR = "\033[37m"  # White color
            sys.stdout.write(
                f"{SchemaRenderer.GRAY_COLOR}  {ICON_COLOR}{icon}\033[0m{SchemaRenderer.GRAY_COLOR} │ {content}{SchemaRenderer.RESET_COLOR} "
            )
            sys.stdout.flush()
            self.rendered_commands.add(content)
            self.buffer = ""

    def flush(self):
        pass  # No need to flush since we render when we get a complete command


class SchemaRenderer:
    GRAY_COLOR = "\033[38;5;240m"
    RESET_COLOR = "\033[0m"

    @staticmethod
    def print_separator(char="─", newline=True, line=True):
        terminal_width = os.get_terminal_size().columns
        if newline:
            sys.stdout.write("\n")
        if line:
            sys.stdout.write(
                f"{SchemaRenderer.GRAY_COLOR}────{char}"
                + "─" * (terminal_width - 5)
                + f"{SchemaRenderer.RESET_COLOR}\n"
            )
        else:
            sys.stdout.write(
                f"{SchemaRenderer.GRAY_COLOR}    {char}{SchemaRenderer.RESET_COLOR}\n"
            )

    schemas = {
        "command": {
            "renderer": CommandRenderer,
            "before": lambda: SchemaRenderer.print_separator("┬"),
        },
        "path": {
            "renderer": PathRenderer,
            "before": lambda: None,
        },
        "content": {
            "renderer": CodeRenderer,
            "before": lambda: SchemaRenderer.print_separator("┼"),
        },
    }


class CodeStreamView:
    def __init__(self):
        self.current_renderers = {}
        self.partial_json = ""
        self.code_style = random.choice(list(get_all_styles()))
        self.code_style = "monokai"  # bw
        # print("Style:", self.code_style)
        self.current_schema = None
        self.current_json = None  # Store the current parsed JSON state

    def _parse_json(self, json_chunk):
        # Add new chunk to existing buffer
        self.partial_json += json_chunk

        # Try to parse the complete buffer first
        try:
            result = json.loads(self.partial_json)
            self.current_json = result  # Store the current state
            # Only clear buffer if we successfully parsed the entire thing
            if result.get("end", False):
                self.partial_json = ""
            return result
        except:
            pass

        # Rest of the method remains the same for handling incomplete JSON
        new_s = ""
        stack = []
        is_inside_string = False
        escaped = False

        # Process each character in the string one at a time.
        for char in self.partial_json:
            if is_inside_string:
                if char == '"' and not escaped:
                    is_inside_string = False
                elif char == "\n" and not escaped:
                    char = (
                        "\\n"  # Replace the newline character with the escape sequence.
                    )
                elif char == "\\":
                    escaped = not escaped
                else:
                    escaped = False
            else:
                if char == '"':
                    is_inside_string = True
                    escaped = False
                elif char == "{":
                    stack.append("}")
                elif char == "[":
                    stack.append("]")
                elif char == "}" or char == "]":
                    if stack and stack[-1] == char:
                        stack.pop()
                    else:
                        # Mismatched closing character; the input is malformed.
                        return None

            # Append the processed character to the new string.
            new_s += char

        # If we're still inside a string at the end of processing, we need to close the string.
        if is_inside_string:
            new_s += '"'

        # Close any remaining open structures in the reverse order that they were opened.
        for closing_char in reversed(stack):
            new_s += closing_char

        # Attempt to parse the modified string as JSON.
        try:
            result = json.loads(new_s)
            self.current_json = result  # Store the current state
            # Only clear buffer if we successfully parsed a complete message
            if result.get("end", False):
                self.partial_json = ""
            return result
        except:
            # Don't print the failure message since it's expected for incomplete JSON
            return None

    def feed(self, chunk):
        json_obj = self._parse_json(chunk)
        if not json_obj:
            return

        # Process the JSON object
        for schema_type, schema in SchemaRenderer.schemas.items():
            if schema_type in json_obj:
                # If this is a new schema type, initialize it
                if schema_type not in self.current_renderers:
                    if schema["before"]:
                        schema["before"]()
                    self.current_renderers[schema_type] = schema["renderer"](
                        self.code_style
                    )

                # Feed the content to the renderer
                self.current_renderers[schema_type].feed(json_obj[schema_type])

                # If this is the end of the content, flush and cleanup
                if json_obj.get("end", False):
                    self.current_renderers[schema_type].flush()
                    if schema["after"]:
                        schema["after"]()
                    del self.current_renderers[schema_type]

    def close(self):
        # Flush any remaining content
        for renderer in self.current_renderers.values():
            renderer.flush()
        self.current_renderers.clear()

        # Print horizontal separator with newline based on command type
        if self.current_json.get("command") == "view":
            SchemaRenderer.print_separator("┴", newline=True)
        else:
            SchemaRenderer.print_separator("┴", newline=False)
