import json
import os
import random
import re
import sys

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_all_styles

from ..misc.spinner import SimpleSpinner


class ContentRenderer:
    def __init__(self, style):
        if os.name == "nt":
            import colorama
            colorama.init()
        self.buffer = ""
        self.started = False
        self.style = style

    def feed(self, json_obj):
        pass

    def flush(self):
        pass


class CodeRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        self.line_number = 1
        self.code_lang = None
        self.buffer = ""
        self.rendered_content = ""
        self.spinner = SimpleSpinner("")
        self.is_spinning = False
        try:
            self.terminal_width = os.get_terminal_size().columns
        except:
            self.terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
        self.safety_padding = 4  # Extra padding to prevent edge cases
        self.json_obj = None

        # Set prefix width based on INTERPRETER_LINE_NUMBERS
        self.show_line_numbers = (
            os.environ.get("INTERPRETER_LINE_NUMBERS", "true").lower() == "true"
        )
        self.prefix_width = (
            6 if self.show_line_numbers else 0
        )  # "123 │ " = 6 characters

        # Print appropriate separator
        if self.show_line_numbers:
            SchemaRenderer.print_separator("┼")
        else:
            SchemaRenderer.print_separator("┴")
            print()

    def feed(self, json_obj):
        self.json_obj = json_obj

        if json_obj.get("name") == "bash":
            content = json_obj.get("command", "")
            self.code_lang = "bash"
        elif json_obj.get("name") == "str_replace_editor":
            content = json_obj.get("file_text", "")

        if self.code_lang is None:
            # Derive it from path extension
            extension = (
                json_obj.get("path", "").split(".")[-1]
                if "." in json_obj.get("path", "")
                else ""
            )
            self.code_lang = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "html": "html",
                "css": "css",
                "json": "json",
                "md": "markdown",
                "sh": "bash",
                "txt": "text",
            }.get(extension, "text")

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
        line = line.encode("utf-8", errors="replace").decode("utf-8")
        try:
            lexer = get_lexer_by_name(self.code_lang)
        except:
            lexer = TextLexer()

        formatter = Terminal256Formatter(style=self.style)
        available_width = self.terminal_width - self.prefix_width - self.safety_padding

        # Remove ANSI escape sequences for width calculation
        line_no_ansi = re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", line)

        # Split long lines before highlighting, accounting for actual visible width
        if len(line_no_ansi) > available_width:
            chunks = []
            pos = 0
            chunk_start = 0
            ansi_offset = 0

            while pos < len(line_no_ansi):
                if pos - chunk_start >= available_width:
                    # Find actual position in original string including ANSI codes
                    real_pos = pos + ansi_offset
                    chunks.append(line[chunk_start:real_pos])
                    chunk_start = real_pos
                pos += 1

                # Count ANSI sequences to maintain offset
                while pos + ansi_offset < len(line):
                    if line[pos + ansi_offset] == "\033":
                        match = re.match(
                            r"\033\[[0-9;]*[a-zA-Z]", line[pos + ansi_offset :]
                        )
                        if match:
                            ansi_offset += len(match.group(0))
                        else:
                            break
                    else:
                        break

            if chunk_start < len(line):
                chunks.append(line[chunk_start:])
        else:
            chunks = [line]

        if self.show_line_numbers:
            # Highlight and print first chunk with line number
            line_prefix = f"{SchemaRenderer.GRAY_COLOR}{str(self.line_number).rjust(3)} │ {SchemaRenderer.RESET_COLOR}"
            highlighted = highlight(chunks[0] + "\n", lexer, formatter).rstrip()

            if self.line_number == 0 and highlighted.strip() == "":
                return

            sys.stdout.write(f"{line_prefix}{highlighted}\n")

            # Print remaining chunks with padding and pipe
            continuation_prefix = (
                f"{SchemaRenderer.GRAY_COLOR}    │ {SchemaRenderer.RESET_COLOR}"
            )
            for chunk in chunks[1:]:
                highlighted = highlight(chunk + "\n", lexer, formatter).rstrip()
                sys.stdout.write(f"{continuation_prefix}{highlighted}\n")
        else:
            # Print chunks without line numbers
            for chunk in chunks:
                highlighted = highlight(chunk + "\n", lexer, formatter).rstrip()
                sys.stdout.write(f"{highlighted}\n")

        sys.stdout.flush()
        self.line_number += 1

    def flush(self):
        if self.is_spinning:
            self.spinner.stop()
            self.is_spinning = False
        if self.buffer:
            self._render_line(self.buffer)
            self.buffer = ""

    def close(self):
        self.flush()
        if self.show_line_numbers:
            SchemaRenderer.print_separator("┴", newline=False)
        else:
            print()
            SchemaRenderer.print_separator("─", newline=False)


class PathRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        self.cwd = os.getcwd() + "/"
        self.buffer = ""
        self.json_obj = None
        self.last_printed_pos = 0
        self.diverged = False

    def feed(self, json_obj):
        self.json_obj = json_obj

        if json_obj.get("name") == "computer":
            if "coordinate" in json_obj:
                content = json_obj.get("coordinate", "")
            elif "text" in json_obj:
                content = json_obj.get("text", "")
        else:
            content = json_obj.get("path", "")

        content = str(content)

        # Process each new character
        while self.last_printed_pos < len(content):
            curr_char = content[self.last_printed_pos]

            # If we haven't diverged yet, check if we're still matching cwd
            if not self.diverged:
                if (
                    self.last_printed_pos < len(self.cwd)
                    and curr_char != self.cwd[self.last_printed_pos]
                ):
                    # We just diverged - print everything from start
                    self.diverged = True
                    sys.stdout.write(content[: self.last_printed_pos + 1])
                elif self.last_printed_pos >= len(self.cwd):
                    # We're past cwd - print just this character
                    sys.stdout.write(curr_char)
            else:
                # Already diverged - print each new character
                sys.stdout.write(curr_char)

            sys.stdout.flush()
            self.last_printed_pos += 1

    def close(self):
        self.flush()
        if self.json_obj and (
            self.json_obj.get("command") == "view"
            or self.json_obj.get("name") == "computer"
        ):
            SchemaRenderer.print_separator("┴", newline=True)


class CommandRenderer(ContentRenderer):
    ICONS = {
        "create": "✦",
        "view": "⚆",
        "str_replace": "↻",
        "insert": "➤",
        "undo_edit": "↫",
        "bash": "▶",
        "key": "⌨",
        "type": "⌨",
        "mouse_move": "⇢",
        "left_click": "⊙",
        "left_click_drag": "⇥",
        "right_click": "⊚",
        "middle_click": "⊗",
        "double_click": "⊛",
        "screenshot": "⚆",
        "cursor_position": "⊹",
        "Open Interpreter": "●",
    }

    def __init__(self, style):
        super().__init__(style)
        SchemaRenderer.print_separator("┬")
        self.buffer = ""
        self.rendered_commands = set()  # Track complete commands we've rendered
        self.json_obj = None

    def feed(self, json_obj):
        self.json_obj = json_obj
        if json_obj.get("name") == "bash":
            content = json_obj.get("name", "")
        elif json_obj.get("name") == "str_replace_editor":
            content = json_obj.get("command", "")
        elif json_obj.get("name") == "computer":
            content = json_obj.get("action", "")

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

    def close(self):
        if self.json_obj and self.json_obj.get("name") == "computer":
            if set(self.json_obj.keys()) == {"name", "action"}:
                SchemaRenderer.print_separator("┴", newline=True)


class InsertRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        self.insert_line = None
        self.context_lines = 3
        self.file_content = []
        self.showed_context = False
        self.GREEN_COLOR = "\033[38;5;255m"
        self.RESET_COLOR = "\033[0m"
        self.context_style = "bw"
        self.showed_after_context = False
        self.line_number = 1
        self.rendered_content = ""
        self.is_spinning = False
        self.spinner = SimpleSpinner("")
        self.code_lang = "python"
        self.buffer = ""
        try:
            self.terminal_width = os.get_terminal_size().columns
        except:
            self.terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
        self.prefix_width = 5  # "123 │ " = 6 characters
        self.safety_padding = 2  # Extra padding to prevent edge cases
        self.show_context = True
        self.leading_space = ""

    def _load_file_content(self, path):
        """Load file content and return as list of lines"""
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.readlines()
        return []

    def _find_insert_line(self, path, specified_line=None, old_str=None):
        """Find the insertion line either from specified line or by finding old_str"""
        if specified_line is not None:
            return specified_line

        if old_str is not None:
            file_text = "".join(self.file_content)
            try:
                # Find line number by counting newlines before match
                prefix = file_text[: file_text.index(old_str)]
                line_number = prefix.count("\n") + 1
                self.leading_space = prefix[: prefix.find(old_str.lstrip())]
                return line_number
            except ValueError:
                return None  # Return None to indicate failure

        return 1  # Default to first line if neither specified

    def feed(self, json_obj):
        path = json_obj.get("path", "")
        content = json_obj.get("new_str", "")

        # Initialize context if needed
        if not self.showed_context:
            # Load file content if not already loaded
            if not self.file_content:
                self.file_content = self._load_file_content(path)

            # Find insert line position
            self.insert_line = self._find_insert_line(
                path,
                specified_line=json_obj.get("insert_line"),
                old_str=json_obj.get("old_str"),
            )

            # If insert_line is None, stop rendering
            if self.insert_line is None:
                return

            # Print separator unless we're doing a string replacement
            if "old_str" not in json_obj:
                SchemaRenderer.print_separator("┼")

            # Set initial line number and show context
            self.line_number = self.insert_line

            if (
                self.show_context and "old_str" not in json_obj
            ):  # OldStr would have already shown context
                start_line = max(0, self.insert_line - self.context_lines - 1)
                end_line = min(len(self.file_content), self.insert_line - 1)
                for line in self.file_content[start_line:end_line]:
                    self._render_line(line.rstrip(), is_context=True)

            self.showed_context = True

        # Process the new content
        if len(content) <= len(self.rendered_content):
            return

        # Get only the new content
        new_content = content[len(self.rendered_content) :]
        self.buffer += new_content
        self.rendered_content = content

        # Process complete lines
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            # Render complete lines
            for line in lines[:-1]:
                if self.is_spinning:
                    self.spinner.stop()
                    self.is_spinning = False
                self._render_line(line, is_context=False)
                if lines[-1].strip():
                    self.spinner.start()
                    self.is_spinning = True
            self.buffer = lines[-1]

    def _render_line(self, line, is_context=False):
        try:
            lexer = get_lexer_by_name(self.code_lang)
        except:
            lexer = TextLexer()

        available_width = self.terminal_width - self.prefix_width - self.safety_padding

        # Split long lines before highlighting/formatting
        if len(line) > available_width:
            chunks = [
                line[i : i + available_width]
                for i in range(0, len(line), available_width)
            ]
        else:
            chunks = [line]

        # Prepare first line prefix
        if is_context:
            line_number_color = SchemaRenderer.GRAY_COLOR
        else:
            line_number_color = self.GREEN_COLOR
        line_prefix = f"{line_number_color}{str(self.line_number).rjust(3)} │ {SchemaRenderer.RESET_COLOR}"

        # Format and print first chunk
        if is_context:
            highlighted = (
                f"{SchemaRenderer.GRAY_COLOR}{chunks[0]}{SchemaRenderer.RESET_COLOR}"
            )
        else:
            formatter = Terminal256Formatter(style=self.style)
            highlighted = highlight(chunks[0] + "\n", lexer, formatter).rstrip()
        sys.stdout.write(f"{line_prefix}{highlighted}\n")

        # Print remaining chunks with padding and pipe
        continuation_prefix = f"{line_number_color}    │ {SchemaRenderer.RESET_COLOR}"
        for chunk in chunks[1:]:
            if is_context:
                highlighted = (
                    f"{SchemaRenderer.GRAY_COLOR}{chunk}{SchemaRenderer.RESET_COLOR}"
                )
            else:
                highlighted = highlight(chunk + "\n", lexer, formatter).rstrip()
            sys.stdout.write(f"{continuation_prefix}{highlighted}\n")

        sys.stdout.flush()
        self.line_number += 1

    def flush(self):
        if self.is_spinning:
            self.spinner.stop()
            self.is_spinning = False
        if self.buffer:
            self._render_line(self.buffer)
            self.buffer = ""

        # Show ending context if we haven't already
        if (
            self.show_context
            and not self.showed_after_context
            and self.insert_line is not None
        ):
            self.showed_after_context = True
            start_line = self.insert_line - 1
            end_line = min(len(self.file_content), start_line + self.context_lines)
            for line in self.file_content[start_line:end_line]:
                self._render_line(line.rstrip(), is_context=True)

    def close(self):
        self.flush()
        SchemaRenderer.print_separator("┴", newline=False)


class OldStrRenderer(ContentRenderer):
    def __init__(self, style):
        super().__init__(style)
        SchemaRenderer.print_separator("┼")
        self.RED_COLOR = "\033[39m\033[38;5;204m"  # Monokai red
        self.RESET_COLOR = "\033[0m"
        self.rendered_content = ""
        self.line_number = 1
        self.code_lang = "python"
        try:
            self.terminal_width = os.get_terminal_size().columns
        except:
            self.terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
        self.prefix_width = 6
        self.safety_padding = 4
        self.buffer = ""  # Add buffer for line-by-line processing
        self.found_line_number = None
        self.path = None
        self.leading_space = ""

    def _find_line_number(self, content, path):
        """Find the line number of content in file and print context"""
        try:
            with open(path, "r") as f:
                file_content = f.read()
                occurrences = file_content.count(content)
                if occurrences == 1:
                    # Find line number by counting newlines
                    line_idx = file_content.find(content)
                    self.found_line_number = file_content[:line_idx].count("\n") + 1

                    # Print context lines before
                    context_lines = 3
                    lines_before = file_content[:line_idx].split("\n")[-context_lines:]
                    start_line = self.found_line_number - len(lines_before)
                    for i, line in enumerate(lines_before):
                        line_num = start_line + i
                        prefix = f"{SchemaRenderer.GRAY_COLOR}{str(line_num).rjust(3)} │ {SchemaRenderer.RESET_COLOR}"
                        sys.stdout.write(
                            f"{prefix}{SchemaRenderer.GRAY_COLOR}{line}{SchemaRenderer.RESET_COLOR}\n"
                        )
                    self.line_number = self.found_line_number
                    self.leading_space = file_content[:line_idx][
                        : line_idx.find(content.lstrip())
                    ]
        except:
            self.found_line_number = 1

    def feed(self, json_obj):
        content = json_obj.get("old_str", "")
        self.path = json_obj.get("path", "")

        if len(content) <= len(self.rendered_content):
            return

        # Get only the new content
        new_content = content[len(self.rendered_content) :]
        self.buffer += new_content
        self.rendered_content = content

        # If this is our first content, find the line number
        if self.found_line_number is None:
            self._find_line_number(content, self.path)

        # Process complete lines
        if "\n" in self.buffer and self.found_line_number is not None:
            lines = self.buffer.split("\n")
            # Process all complete lines
            for line in lines[:-1]:
                self._render_line(line)
            # Keep the incomplete line in the buffer
            self.buffer = lines[-1]

    def _render_line(self, line):
        try:
            lexer = get_lexer_by_name(self.code_lang)
        except:
            lexer = TextLexer()

        available_width = self.terminal_width - self.prefix_width - self.safety_padding

        # Split long lines before highlighting
        if len(line) > available_width:
            chunks = [
                line[i : i + available_width]
                for i in range(0, len(line), available_width)
            ]
        else:
            chunks = [line]

        # Render first chunk with line number
        line_prefix = f"{SchemaRenderer.GRAY_COLOR}{str(self.line_number).rjust(3)} │ {SchemaRenderer.RESET_COLOR}"
        sys.stdout.write(
            f"{line_prefix}{self.RED_COLOR}\033[9m{chunks[0]}\033[29m{self.RESET_COLOR}\n"
        )

        # Render remaining chunks with continuation prefix
        continuation_prefix = (
            f"{SchemaRenderer.GRAY_COLOR}    │ {SchemaRenderer.RESET_COLOR}"
        )
        for chunk in chunks[1:]:
            sys.stdout.write(
                f"{continuation_prefix}{self.RED_COLOR}\033[9m{chunk}\033[29m{self.RESET_COLOR}\n"
            )

        sys.stdout.flush()
        self.line_number += 1

    def flush(self):
        if self.buffer and self.found_line_number is not None:
            self._render_line(self.buffer)
            self.buffer = ""

    def close(self):
        # Try to find line number one last time if we haven't found it yet
        if self.found_line_number is None and self.rendered_content and self.path:
            self._find_line_number(self.rendered_content, self.path)

        self.flush()
        if self.found_line_number is None:
            print("No line number found")


class SchemaRenderer:
    GRAY_COLOR = "\033[38;5;240m"
    RESET_COLOR = "\033[0m"

    @staticmethod
    def print_separator(char="─", newline=True, line=True):
        try:
            terminal_width = os.get_terminal_size().columns
        except:
            terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
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

    edit_schemas = {
        "command": {"renderer": CommandRenderer},
        "path": {"renderer": PathRenderer},
        "file_text": {"renderer": CodeRenderer},
        "old_str": {"renderer": OldStrRenderer},
        "new_str": {"renderer": InsertRenderer},
    }

    bash_schemas = {
        "name": {"renderer": CommandRenderer},
        "command": {"renderer": CodeRenderer},
    }

    computer_schemas = {
        "action": {"renderer": CommandRenderer},
        "text": {"renderer": PathRenderer},
        "coordinate": {"renderer": PathRenderer},
    }


class ToolRenderer:
    def __init__(self, name=None):
        self.current_renderers = {}
        self.partial_json = ""
        self.code_style = random.choice(list(get_all_styles()))
        self.code_style = "monokai"  # bw
        # print("Style:", self.code_style)
        self.current_schema = None
        self.current_json = None  # Store the current parsed JSON state
        self.name = name

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

        json_obj["name"] = self.name  # Pass name into renderers

        # Process the JSON object
        schemas = []
        if self.name == "str_replace_editor":
            schemas = SchemaRenderer.edit_schemas.items()
        elif self.name == "bash":
            schemas = SchemaRenderer.bash_schemas.items()
        elif self.name == "computer":
            schemas = SchemaRenderer.computer_schemas.items()

        for schema_type, schema in schemas:
            if schema_type in json_obj:
                # If this is a new schema type, initialize it
                if schema_type not in self.current_renderers:
                    # Close any existing renderers
                    self.close()
                    # Initialize the new renderer
                    self.current_renderers[schema_type] = schema["renderer"](
                        self.code_style
                    )

                # Feed the entire JSON object to the renderer
                self.current_renderers[schema_type].feed(json_obj)

    def close(self):
        # Close any remaining content
        for renderer in self.current_renderers.values():
            if hasattr(renderer, "close"):
                renderer.close()
