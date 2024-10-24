import sys
from enum import Enum, auto
from typing import Set


class Style(Enum):
    NORMAL = auto()
    BOLD = auto()
    ITALIC = auto()
    CODE = auto()
    HEADER = auto()
    CODE_BLOCK = auto()


class MarkdownStreamer:
    def __init__(self):
        # ANSI escape codes
        self.BOLD = "\033[1m"
        self.CODE = "\033[7m"  # Inverted
        self.CODE_BLOCK = "\033[48;5;236m"  # Very subtle dark gray background
        self.RESET = "\033[0m"

        # State tracking
        self.active_styles: Set[Style] = set()
        self.potential_marker = ""
        self.line_start = True
        self.header_level = 0
        self.in_list = False
        self.rule_marker_count = 0

        # Code block state
        self.code_fence_count = 0
        self.in_code_block = False
        self.list_marker_count = 0

    def write_char(self, char: str):
        """Write a single character with current styling."""
        if Style.CODE in self.active_styles:
            sys.stdout.write(f"{self.CODE}{char}{self.RESET}")
        elif Style.CODE_BLOCK in self.active_styles:
            sys.stdout.write(f"{self.CODE_BLOCK}{char}{self.RESET}")
        elif Style.BOLD in self.active_styles or Style.HEADER in self.active_styles:
            sys.stdout.write(f"{self.BOLD}{char}{self.RESET}")
        else:
            sys.stdout.write(char)
        sys.stdout.flush()

    def handle_marker(self, char: str) -> bool:
        """Handle markdown markers."""
        self.potential_marker += char

        # Code block
        if char == "`" and not Style.CODE in self.active_styles:
            self.code_fence_count += 1
            if self.code_fence_count == 3:
                self.code_fence_count = 0
                if not self.in_code_block:
                    self.in_code_block = True
                    self.active_styles.add(Style.CODE_BLOCK)
                    sys.stdout.write("\n")
                else:
                    self.in_code_block = False
                    self.active_styles.remove(Style.CODE_BLOCK)
                    sys.stdout.write("\n")
                return True
        else:
            self.code_fence_count = 0

        # Inline code
        if char == "`" and len(self.potential_marker) == 1:
            if Style.CODE in self.active_styles:
                self.active_styles.remove(Style.CODE)
            else:
                self.active_styles.add(Style.CODE)
            self.potential_marker = ""
            return True

        # Bold marker
        if self.potential_marker == "**":
            if Style.BOLD in self.active_styles:
                self.active_styles.remove(Style.BOLD)
            else:
                self.active_styles.add(Style.BOLD)
            self.potential_marker = ""
            return True

        # Italic marker
        elif self.potential_marker == "*" and char != "*":
            if Style.ITALIC in self.active_styles:
                self.active_styles.remove(Style.ITALIC)
            else:
                self.active_styles.add(Style.ITALIC)
            self.write_char(char)
            self.potential_marker = ""
            return True

        # Not a complete marker
        if len(self.potential_marker) > 2:
            self.write_char(self.potential_marker[0])
            self.potential_marker = self.potential_marker[1:]

        return False

    def handle_horizontal_rule(self, char: str) -> bool:
        """Handle horizontal rule markers."""
        if self.line_start and char == "-":
            self.rule_marker_count += 1
            if self.rule_marker_count == 3:
                sys.stdout.write("\n")
                sys.stdout.write("─" * 50)
                sys.stdout.write("\n")
                self.rule_marker_count = 0
                self.line_start = True
                return True
            return True
        else:
            if self.rule_marker_count > 0:
                for _ in range(self.rule_marker_count):
                    self.write_char("-")
                self.rule_marker_count = 0
        return False

    def handle_line_start(self, char: str) -> bool:
        """Handle special characters at start of lines."""
        if not self.line_start:
            return False

        if char == "#":
            self.header_level += 1
            return True
        elif self.header_level > 0:
            if char == " ":
                self.active_styles.add(Style.HEADER)
                return True
            self.header_level = 0

        elif char == "-" and not any(
            s in self.active_styles for s in [Style.BOLD, Style.ITALIC]
        ):
            self.list_marker_count = 1
            return True
        elif self.list_marker_count == 1 and char == " ":
            sys.stdout.write("  • ")  # Write bullet point
            sys.stdout.flush()
            self.list_marker_count = 0
            self.line_start = False
            return True

        self.line_start = False
        return False

    def feed(self, char: str):
        """Feed a single character into the streamer."""
        # Handle newlines
        if char == "\n":
            self.write_char(char)
            self.line_start = True
            if not self.in_code_block:
                self.active_styles.clear()
            self.potential_marker = ""
            self.list_marker_count = 0  # Reset list state
            return

        # Handle horizontal rules
        if not self.in_code_block and self.handle_horizontal_rule(char):
            return

        # Handle line start features
        if not self.in_code_block and self.handle_line_start(char):
            return

        # Handle markdown markers
        if char in ["*", "`"]:
            if not self.handle_marker(char):
                self.write_char(char)
        else:
            if self.potential_marker:
                self.write_char(self.potential_marker)
            self.potential_marker = ""
            self.write_char(char)

    def reset(self):
        """Reset streamer state."""
        self.active_styles.clear()
        self.potential_marker = ""
        self.line_start = True
        self.header_level = 0
        self.list_marker_count = 0
        self.in_code_block = False
        self.code_fence_count = 0
        self.rule_marker_count = 0
        sys.stdout.write(self.RESET)
        sys.stdout.flush()


import requests

# Download a large markdown file to test different styles
url = "https://raw.githubusercontent.com/matiassingers/awesome-readme/master/readme.md"
url = (
    "https://raw.githubusercontent.com/OpenInterpreter/open-interpreter/main/README.md"
)

response = requests.get(url)
markdown_text = response.text

markdown_text = (
    """```python
print("Hello, world!")
```\n"""
    + markdown_text
)


# Initialize it once
md = MarkdownStreamer()

# Then feed it characters one at a time. You can do this:
md.feed("H")
md.feed("e")
md.feed("l")
md.feed("l")
md.feed("o")

# Or feed from a string:
for char in markdown_text:
    md.feed(char)

# You can reset it if needed (clears all state)
md.reset()
