import subprocess
import threading
import time
from rich.live import Live
from rich.panel import Panel
from rich.box import MINIMAL
from rich.syntax import Syntax
from rich.table import Table
from rich.console import Group
from rich.console import Console
from typing import Union

# Mapping of languages to their start and print commands
language_map = {
    "python": {"start_cmd": "python -i -q -u", "print_cmd": 'print("{}")'},
    "bash": {"start_cmd": "bash --noediting", "print_cmd": 'echo "{}"'},
    "javascript": {"start_cmd": "node -i", "print_cmd": 'console.log("{}")'}
}

class CodeInterpreter:

  def __init__(self, language):
    # Initialize stuff we'll need
    self.language = language
    self.done = threading.Event()

    # Get the start_cmd for the selected language
    start_cmd = language_map[self.language]["start_cmd"]

    # Use the appropriate start_cmd to execute the code
    self.proc = subprocess.Popen(start_cmd.split(),
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True)

    # Start watching ^ its `stdout` and `stderr` streams
    threading.Thread(target=self.save_and_display_stream,
                      args=(self.proc.stdout, ),
                      daemon=True).start()
    threading.Thread(target=self.save_and_display_stream,
                      args=(self.proc.stderr, ),
                      daemon=True).start()

  def save_and_display_stream(self, stream):
    # Handle each line of output
    for line in iter(stream.readline, ''):
      line = line.strip()

      # Check if it's a message we added (like ACTIVE_LINE)
      # Or if we should save it to self.output
      if line.startswith("ACTIVE_LINE:"):
        self.active_line = int(line.split(":")[1])
      elif line == "END":
        self.done.set()
        self.active_line = -1
      else:
        self.output.append(line)

      # Update the display, which renders code + self.output
      self.update_display()

  def update_display(self):
    # Create a table for the code
    code_table = Table(show_header=False,
                       show_footer=False,
                       box=None,
                       padding=0,
                       expand=True)
    code_table.add_column()

    # Add each line of code to the table
    for i, line in enumerate(self.code_lines, start=1):
      if i == self.active_line:
        # This is the active line, print it with a white background
        syntax = Syntax(line, self.language, line_numbers=False, theme="bw")
        code_table.add_row(syntax, style="black on white")
      else:
        # This is not the active line, print it normally
        syntax = Syntax(line,
                        self.language,
                        line_numbers=False,
                        theme="monokai")
        code_table.add_row(syntax)

    # Create a panel for the code
    code_panel = Panel(code_table, box=MINIMAL, style="on #272722")

    # Create a panel for the output (if there is any)
    if self.output == [] or self.output == ["None"]:
      output_panel = ""
    else:
      output_panel = Panel("\n".join(self.output),
                           box=MINIMAL,
                           style="#FFFFFF on #3b3b37")

    # Create a group with the code table and output panel
    group = Group(
      code_panel,
      output_panel,
    )

    # Update the live display
    self.live.update(group)
    self.live.refresh()

  def exec(self, code):

    # Reset output and active_line
    self.output = []
    self.active_line = None
    
    # Create and start a new live display
    with Live(auto_refresh=False, console=Console()) as self.live:

      # Split the code into lines and add print statements to track the active line
      self.code_lines = code.strip().split('\n')
      self.active_line = 0

      # Display just the code
      self.update_display()

      # Use the print_cmd for the selected language
      print_cmd = language_map[self.language]["print_cmd"]

      # Initialize an empty list to hold the modified lines of code
      modified_code_lines = []

      # Iterate over each line in the original code
      for i, line in enumerate(self.code_lines):
        # Get the leading whitespace of the current line
        leading_whitespace = line[:len(line) - len(line.lstrip())]

        # Format the print command with the current line number
        print_line = print_cmd.format(f"ACTIVE_LINE:{i+1}")

        # Prepend the leading whitespace to the print command
        print_line = leading_whitespace + print_line

        # Add the print command and the original line to the modified lines
        modified_code_lines.append(print_line)
        modified_code_lines.append(line)

      # Join the modified lines with newlines
      code = "\n".join(modified_code_lines)

      # Reset self.done so we can .wait() for it
      self.done.clear()

      # Write code to stdin of the process
      self.proc.stdin.write(code + "\n" + print_cmd.format('END') + "\n")
      self.proc.stdin.flush()

      # Wait until execution completes
      self.done.wait()

      # Wait for the display to catch up? (I'm not sure why this works)
      time.sleep(0.01)

    # Return code output
    return "\n".join(self.output[2:])

def run_code(language: str, code: str, code_interpreters: dict) -> Union[str, None]:
    # Check if the provided language is supported
    if language not in language_map:
        raise ValueError(f"Unsupported language: {language}")

    # Get or create a code interpreter for the language
    if language not in code_interpreters:
        code_interpreters[language] = CodeInterpreter(language)

    block = code_interpreters[language]
    output = block.exec(code)

    return output