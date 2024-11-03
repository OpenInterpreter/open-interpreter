import os
import sys

from pygments import highlight
from pygments.formatters import Terminal256Formatter
from pygments.lexers import TextLexer, get_lexer_by_name


class BashStreamer:
    def __init__(self):
        self.CODE_BLOCK = "\033[48;5;235m"  # Very subtle dark gray background
        self.RESET = "\033[0m"

        self.current_code_line = ""
        self.code_lang = ""
        self.in_code_block = False
        self.style = os.environ.get("INTERPRETER_CODE_STYLE", "monokai")

    def set_language(self, language: str):
        """Set the language for syntax highlighting"""
        self.code_lang = language
        self.in_code_block = True

        # Print initial empty line with background
        terminal_width = os.get_terminal_size().columns
        sys.stdout.write(
            f"\n{self.CODE_BLOCK}" + " " * terminal_width + f"{self.RESET}\n"
        )
        sys.stdout.flush()

    def feed(self, text: str):
        """Process incoming text stream"""
        if not self.in_code_block:
            return

        for char in text:
            if char == "\n":
                # Handle empty lines
                if not self.current_code_line.strip():
                    sys.stdout.write(
                        f"{self.CODE_BLOCK}" + " " * terminal_width + f"{self.RESET}\n"
                    )
                    self.current_code_line = ""
                    continue

                try:
                    lexer = get_lexer_by_name(self.code_lang.strip().lower())
                except:
                    lexer = TextLexer()

                style = self.style
                formatter = Terminal256Formatter(style=style)

                terminal_width = os.get_terminal_size().columns
                padding = 2  # Left/right padding
                content_width = terminal_width - (padding * 2)

                # Get the leading whitespace
                leading_space = len(self.current_code_line) - len(
                    self.current_code_line.lstrip()
                )
                code_content = self.current_code_line[leading_space:]

                # Split the actual content into words
                words = code_content.split(" ")
                current_line = (
                    " " * leading_space
                )  # Start with the original indentation

                for word in words:
                    test_line = (
                        current_line + (" " if current_line.strip() else "") + word
                    )
                    if len(test_line) > content_width:
                        # Print current line with background and padding
                        formatted = highlight(current_line, lexer, formatter).rstrip()
                        sys.stdout.write(
                            self.CODE_BLOCK
                            + f"  {formatted}"
                            + " " * (terminal_width - len(current_line) - 2)
                            + f"{self.RESET}\n"
                        )
                        current_line = (
                            " " * leading_space + word
                        )  # Reset with original indentation
                    else:
                        current_line = test_line

                # Write any remaining content
                if current_line:
                    formatted = highlight(current_line, lexer, formatter).rstrip()
                    sys.stdout.write(
                        self.CODE_BLOCK
                        + f"  {formatted}"
                        + " " * (terminal_width - len(current_line) - 2)
                        + f"{self.RESET}\n"
                    )

                self.current_code_line = ""
            else:
                self.current_code_line += char

    def end(self):
        """End the code block and print final formatting"""
        if self.current_code_line:  # Handle any remaining text
            try:
                lexer = get_lexer_by_name(self.code_lang.strip().lower())
            except:
                lexer = TextLexer()
            formatter = Terminal256Formatter(style=self.style)
            formatted = highlight(self.current_code_line, lexer, formatter).rstrip()
            terminal_width = os.get_terminal_size().columns
            sys.stdout.write(
                self.CODE_BLOCK
                + f"  {formatted}"
                + " " * (terminal_width - len(self.current_code_line) - 2)
                + f"{self.RESET}\n"
            )

        terminal_width = os.get_terminal_size().columns
        sys.stdout.write(
            self.CODE_BLOCK + f"" + " " * terminal_width + f"{self.RESET}\n"
        )

        self.in_code_block = False
        self.current_code_line = ""
        self.code_lang = ""

    def reset(self):
        """Reset all state variables"""
        self.current_code_line = ""
        self.code_lang = ""
        self.in_code_block = False


streamer = BashStreamer()
streamer.set_language("bash")
streamer.feed(
    """#!/bin/bash

# A script to monitor system resources and log them
LOG_FILE="/var/log/system_monitor.log"
INTERVAL=5

# Create log file if it doesn't exist
touch $LOG_FILE

echo "Starting system monitoring..." 

while true; do
    # Get timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Collect system stats
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
    mem_usage=$(free -m | awk '/Mem:/ {print $3}')
    disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    
    # Log the stats
    echo "$timestamp - CPU: $cpu_usage% MEM: ${mem_usage}MB DISK: $disk_usage" >> $LOG_FILE
    
    # Print to console
    echo "CPU Usage: $cpu_usage%"
    echo "Memory Usage: ${mem_usage}MB"
    echo "Disk Usage: $disk_usage"
    echo "------------------------"
    
    sleep $INTERVAL
done\n"""
)
streamer.end()
print("")
