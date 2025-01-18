import os
import sys
import time
from enum import Enum, auto
from typing import Dict, Optional, Set

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_by_name

from ..misc.spinner import SimpleSpinner


class MarkdownElement(Enum):
    BOLD = "**"
    ITALIC = "*"
    CODE = "`"
    CODE_BLOCK = "```"
    LINK = "["
    HEADER = "#"


class MarkdownRenderer:
    def __init__(self):
        if os.name == "nt":
            import colorama
            colorama.init()
        # ANSI escape codes
        self.BOLD = "\033[1m"
        self.CODE = "\033[7m"  # Regular inline code stays inverted
        self.CODE_BLOCK = "\033[48;5;238m"  # Medium gray background for code blocks
        self.CODE_BLOCK_LINE = (
            ""  # Removed the separator line since we'll use background
        )
        self.LINK = "\033[4;34m"
        self.RESET = "\033[0m"
        self.OSC = "\033]8;;"
        self.ST = "\033\\"

        # State tracking
        self.buffer = ""
        self.current_element: Optional[MarkdownElement] = None
        self.line_start = True
        self.header_level = 0
        self.backtick_count = 0
        self.code_lang = ""
        self.collecting_lang = False

        # Add new state variables for code block handling
        self.in_code_block = False
        self.current_code_line = ""
        self.line_number = 1

        # Add spinner (no text, just the spinner)
        self.spinner = SimpleSpinner("")

    def write_styled(self, text: str, element: Optional[MarkdownElement] = None):
        """Write text with appropriate styling."""
        if element == MarkdownElement.BOLD:
            sys.stdout.write(f"{self.BOLD}{text}{self.RESET}")
        elif element == MarkdownElement.CODE:
            sys.stdout.write(f"{self.CODE}{text}{self.RESET}")
        elif element == MarkdownElement.CODE_BLOCK:
            # Handle single line of code block
            try:
                lexer = get_lexer_by_name(self.code_lang.strip().lower())
            except:
                lexer = TextLexer()
            formatter = Terminal256Formatter(style="monokai")
            formatted = highlight(text + "\n", lexer, formatter)
            sys.stdout.write(formatted)
            sys.stdout.flush()
        elif element == MarkdownElement.LINK:
            # Extract URL from buffer
            url_start = self.buffer.index("](") + 2
            url = self.buffer[url_start:-1]
            sys.stdout.write(
                f"{self.OSC}{url}{self.ST}{self.LINK}{text}{self.RESET}{self.OSC}{self.ST}"
            )
        elif element == MarkdownElement.HEADER:
            sys.stdout.write(f"{self.BOLD}{text}{self.RESET}")
        else:
            sys.stdout.write(text)
        sys.stdout.flush()

    def is_element_complete(self) -> bool:
        """Check if current markdown element is complete."""
        if not self.current_element:
            return False

        if self.current_element == MarkdownElement.LINK:
            return ")" in self.buffer and "](" in self.buffer
        elif self.current_element == MarkdownElement.CODE_BLOCK:
            # Look for matching triple backticks
            if self.buffer.startswith("```"):
                # Find the next triple backticks after the start
                rest_of_buffer = self.buffer[3:]
                return "```" in rest_of_buffer
        elif self.current_element == MarkdownElement.CODE:
            # For inline code, look for single backtick
            if self.buffer.startswith("`"):
                # Make sure we don't match with part of a triple backtick
                if not self.buffer.startswith("```"):
                    return "`" in self.buffer[1:]
        elif self.current_element == MarkdownElement.BOLD:
            if len(self.buffer) >= 2 and self.buffer.startswith("*"):
                if self.buffer[1] == "*":  # It's a bold marker
                    return len(self.buffer) >= 4 and self.buffer.endswith("**")
                else:  # It's just a single asterisk
                    self.write_styled(self.buffer)
                    return True
        elif self.current_element == MarkdownElement.HEADER:
            return "\n" in self.buffer
        return False

    def handle_complete_element(self):
        """Process and write a complete markdown element."""
        if not self.current_element:
            return

        if self.current_element == MarkdownElement.LINK:
            # Extract link text
            text = self.buffer[1 : self.buffer.index("]")]
            self.write_styled(text, MarkdownElement.LINK)
        elif self.current_element == MarkdownElement.CODE_BLOCK:
            content = self.buffer[3:]  # Skip opening ```
            end_index = content.index("```")

            first_newline = content.find("\n")
            if first_newline != -1 and first_newline < end_index:
                self.code_lang = content[:first_newline]
                text = content[first_newline + 1 : end_index]
            else:
                self.code_lang = ""
                text = content[:end_index]

            self.write_styled(text, MarkdownElement.CODE_BLOCK)
            self.code_lang = ""  # Reset language
        elif self.current_element == MarkdownElement.CODE:
            # Remove single backticks
            text = self.buffer[1:-1]
            self.write_styled(text, MarkdownElement.CODE)
        elif self.current_element == MarkdownElement.BOLD:
            # Remove ** markers
            text = self.buffer[2:-2]
            self.write_styled(text, MarkdownElement.BOLD)
        elif self.current_element == MarkdownElement.HEADER:
            # Remove # markers and newline
            text = self.buffer[self.header_level :].strip()
            self.write_styled(text, MarkdownElement.HEADER)
            self.write_styled("\n")

        self.current_element = None
        self.buffer = ""
        self.header_level = 0

    def feed(self, text: str):
        """Process incoming text stream."""

        for char in text:
            # Handle code block line-by-line streaming
            if self.in_code_block:
                if char == "\n":
                    if self.collecting_lang:
                        self.spinner.start()
                        self.spinner.stop()  # Stop before any output
                        # First newline after ``` - this line contains the language
                        self.code_lang = self.current_code_line
                        self.collecting_lang = False
                        try:
                            terminal_width = os.get_terminal_size().columns
                        except:
                            terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
                        sys.stdout.write(
                            "\033[38;5;240m\n────┬" + "─" * (terminal_width - 5) + "\n"
                        )  # Top line
                        sys.stdout.write(
                            "\033[38;5;240m    │ " + self.code_lang + "\n"
                        )  # Language line
                        sys.stdout.write(
                            "\033[38;5;240m────┼"
                            + "─" * (terminal_width - 5)
                            + "\033[0m\n"
                        )  # Connected line
                        self.line_number = 1
                        self.current_code_line = ""
                    else:
                        self.spinner.stop()  # Stop before any output
                        try:
                            lexer = get_lexer_by_name(self.code_lang.strip().lower())
                        except:
                            lexer = TextLexer()
                        formatter = Terminal256Formatter(
                            style=os.getenv("INTERPRETER_CODE_STYLE", "monokai")
                        )

                        try:
                            terminal_width = os.get_terminal_size().columns
                        except:
                            terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
                        line_prefix = (
                            f"\033[38;5;240m{str(self.line_number).rjust(3)} │ "
                        )
                        content_width = (
                            terminal_width - len(line_prefix) + len("\033[38;5;240m")
                        )  # Adjust for ANSI code

                        if (
                            not self.current_code_line.strip()
                        ):  # Empty or whitespace-only line
                            sys.stdout.write(f"{line_prefix}\n")
                        else:
                            # Split the original line into words before highlighting
                            words = self.current_code_line.split(" ")
                            current_line = ""
                            first_line = True

                            for word in words:
                                test_line = (
                                    current_line + (" " if current_line else "") + word
                                )
                                if len(test_line) > content_width:
                                    # Highlight and write current line
                                    if first_line:
                                        formatted = highlight(
                                            current_line, lexer, formatter
                                        ).rstrip()
                                        sys.stdout.write(f"{line_prefix}{formatted}\n")
                                        first_line = False
                                    else:
                                        formatted = highlight(
                                            current_line, lexer, formatter
                                        ).rstrip()
                                        sys.stdout.write(
                                            f"\033[38;5;240m    │ {formatted}\n"
                                        )
                                    current_line = word
                                else:
                                    current_line = test_line if current_line else word

                            # Write any remaining content
                            if current_line:
                                formatted = highlight(
                                    current_line, lexer, formatter
                                ).rstrip()
                                if first_line:
                                    sys.stdout.write(f"{line_prefix}{formatted}\n")
                                else:
                                    sys.stdout.write(
                                        f"\033[38;5;240m    │ {formatted}\n"
                                    )

                        self.line_number += 1
                        self.current_code_line = ""
                        self.spinner.start()  # Start after output
                elif char == "`" and self.current_code_line.endswith("``"):
                    self.spinner.stop()  # Stop before final output
                    if self.current_code_line[:-2]:
                        try:
                            lexer = get_lexer_by_name(self.code_lang.strip().lower())
                        except:
                            lexer = TextLexer()
                        formatter = Terminal256Formatter(style="monokai")
                        formatted = highlight(
                            self.current_code_line[:-2], lexer, formatter
                        ).rstrip()
                        sys.stdout.write(
                            f"{str(self.line_number).rjust(4)} │ {formatted}\n"
                        )
                    try:
                        terminal_width = os.get_terminal_size().columns
                    except:
                        terminal_width = int(os.environ.get("TERMINAL_WIDTH", "50"))
                    sys.stdout.write(
                        "\033[38;5;240m────┴" + "─" * (terminal_width - 5) + "\033[0m\n"
                    )
                    sys.stdout.flush()
                    self.in_code_block = False
                    self.collecting_lang = False
                    self.current_code_line = ""
                    self.current_element = None
                    self.buffer = ""
                else:
                    self.current_code_line += char
                continue

            # If we're currently processing a markdown element
            if self.current_element:
                self.buffer += char
                if self.is_element_complete():
                    self.handle_complete_element()
                continue

            # Special handling for backticks
            if char == "`":
                self.backtick_count += 1

                if self.backtick_count == 3:
                    self.current_element = MarkdownElement.CODE_BLOCK
                    self.buffer = "```"
                    self.backtick_count = 0
                    self.in_code_block = True
                    self.collecting_lang = True
                    self.line_number = 1
                continue

            # If we were counting backticks but got a different character
            if self.backtick_count > 0:
                if self.backtick_count == 1:
                    self.current_element = MarkdownElement.CODE
                    self.buffer = (
                        "`" + char
                    )  # Include both the backtick and current char
                else:
                    # Write out accumulated backticks as regular text
                    self.write_styled("`" * self.backtick_count)
                    self.write_styled(char)
                self.backtick_count = 0
                continue

            # Check for start of new markdown elements
            if self.line_start and char == "#":
                self.current_element = MarkdownElement.HEADER
                self.header_level += 1
                self.buffer = char
            elif char == "[":
                self.current_element = MarkdownElement.LINK
                self.buffer = char
            elif char == "*":
                self.buffer = char
                self.current_element = MarkdownElement.BOLD
            else:
                # Regular text
                self.write_styled(char)

            # Track line starts for headers
            self.line_start = char == "\n"

    def close(self):
        pass

    def reset(self):
        """Reset all state variables to their initial values."""
        self.buffer = ""
        self.current_element = None
        self.line_start = True
        self.header_level = 0
        self.backtick_count = 0
        self.code_lang = ""
        self.collecting_lang = False
        self.in_code_block = False
        self.current_code_line = ""
