import os
import sys
from enum import Enum, auto
from typing import Dict, Optional, Set

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_by_name


class MarkdownElement(Enum):
    BOLD = "**"
    ITALIC = "*"
    CODE = "`"
    CODE_BLOCK = "```"
    LINK = "["
    HEADER = "#"


class MarkdownStreamer:
    def __init__(self):
        # ANSI escape codes
        self.BOLD = "\033[1m"
        self.CODE = "\033[7m"  # Regular inline code stays inverted
        self.CODE_BLOCK = (
            "\033[48;5;234m"  # Very subtle dark gray background for code blocks
        )
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
                        # First newline after ``` - this line contains the language
                        self.code_lang = self.current_code_line
                        self.collecting_lang = False
                        terminal_width = os.get_terminal_size().columns
                        # Print empty line with background
                        sys.stdout.write(
                            f"\n\n{self.CODE_BLOCK}"
                            + " " * terminal_width
                            + f"{self.RESET}\n"
                        )
                        self.current_code_line = ""
                    else:
                        try:
                            lexer = get_lexer_by_name(self.code_lang.strip().lower())
                        except:
                            lexer = TextLexer()
                        formatter = Terminal256Formatter(style="monokai")

                        terminal_width = os.get_terminal_size().columns
                        padding = 2  # Left/right padding
                        content_width = terminal_width - (padding * 2)

                        # Split the original line into words before highlighting
                        words = self.current_code_line.split(" ")
                        current_line = ""

                        for word in words:
                            test_line = (
                                current_line + (" " if current_line else "") + word
                            )
                            if len(test_line) > content_width:
                                # Print current line with background and padding
                                formatted = highlight(
                                    current_line, lexer, formatter
                                ).rstrip()
                                sys.stdout.write(
                                    f"{self.CODE_BLOCK}  {formatted}"
                                    + " " * (terminal_width - len(current_line) - 2)
                                    + f"{self.RESET}\n"
                                )
                                current_line = word
                            else:
                                current_line = test_line if current_line else word

                        # Write any remaining content
                        if current_line:
                            formatted = highlight(
                                current_line, lexer, formatter
                            ).rstrip()
                            sys.stdout.write(
                                f"{self.CODE_BLOCK}  {formatted}"
                                + " " * (terminal_width - len(current_line) - 2)
                                + f"{self.RESET}\n"
                            )

                        self.current_code_line = ""
                elif char == "`" and self.current_code_line.endswith("``"):
                    if self.current_code_line[:-2]:
                        try:
                            lexer = get_lexer_by_name(self.code_lang.strip().lower())
                        except:
                            lexer = TextLexer()
                        formatter = Terminal256Formatter(style="monokai")
                        formatted = highlight(
                            self.current_code_line[:-2], lexer, formatter
                        ).rstrip()
                        terminal_width = os.get_terminal_size().columns
                        sys.stdout.write(
                            f"{self.CODE_BLOCK}  {formatted}"
                            + " "
                            * (terminal_width - len(self.current_code_line[:-2]) - 2)
                            + f"{self.RESET}\n"
                        )

                    terminal_width = os.get_terminal_size().columns
                    # Print empty line with background
                    sys.stdout.write(
                        f"{self.CODE_BLOCK}" + " " * terminal_width + f"{self.RESET}\n"
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


import requests

# Download a large markdown file to test different styles
url = "https://raw.githubusercontent.com/matiassingers/awesome-readme/master/readme.md"
url = (
    "https://raw.githubusercontent.com/OpenInterpreter/open-interpreter/main/README.md"
)

response = requests.get(url)
markdown_text = response.text

markdown_text = markdown_text.split("After install")[1]

# Initialize it once
md = MarkdownStreamer()

# Or feed from a string:
import random

i = 0
import time

while i < len(markdown_text):
    # Random chunk size between 1 and 20
    chunk_size = random.randint(1, 20)
    time.sleep(random.uniform(0.01, 0.3))
    # Get chunk, ensuring we don't go past the end
    chunk = markdown_text[i : min(i + chunk_size, len(markdown_text))]
    # Feed each character in the chunk
    for char in chunk:
        md.feed(char)
    i += chunk_size

# for chunk in markdown_text:
#     md.feed(chunk)

# You can reset it if needed (clears all state)
md.reset()
