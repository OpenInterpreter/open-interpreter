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

# Mapping of languages to their start and print commands
language_map = {
    "python": {"start_cmd": "python -i -q -u", "print_cmd": 'print("{}")'},
    "bash": {"start_cmd": "bash --noediting", "print_cmd": 'echo "{}"'},
    "javascript": {"start_cmd": "node -i", "print_cmd": 'console.log("{}")'}
}


class CodeInterpreter:
  """
  Code Interpreters display and run code in different languages.
  
  They can create code blocks on the terminal, then be executed to produce an output which will be displayed in real-time.
  """

  def __init__(self):
    # Define these for IDE auto-completion
    self.language = ""
    self.output = ""
    self.code = ""
    
    self.proc = None
    self.active_line = None

  def create_block(self):
    # Start a new live display
    self.live = Live(auto_refresh=False, console=Console())
    self.live.start()
    self.output = ""
    self.code = ""

  """def export_messages(self):
    return [
      {
        "role": "function_call"
        "function_call": {
          "name": "run_code",
          "args": {
            "language": self.language,
            "code": self.code,
          }
        }
      },
      {"role": "function", "content": self.output}
    ]"""

  def end_block(self):
    # Destroys live display
    self.live.stop()

  def start_process(self):
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

  def exec(self):
    if not self.proc:
      self.start_process()

    # Reset output_lines and active_line
    self.output = ""
    self.active_line = None

    # Split the code into lines and add print statements to track the active line
    code_lines = self.code.strip().split('\n')
    self.active_line = 0

    # Display just the code
    self.update_display()

    # Use the print_cmd for the selected language
    print_cmd = language_map[self.language]["print_cmd"]

    # Initialize an empty list to hold the modified lines of code
    modified_code_lines = []

    # Iterate over each line in the original code
    for i, line in enumerate(code_lines):
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
    self.done = threading.Event()
    self.done.clear()

    # Write code to stdin of the process
    self.proc.stdin.write(code + "\n" + print_cmd.format('END') + "\n")
    self.proc.stdin.flush()

    # Wait until execution completes
    self.done.wait()

    # Wait for the display to catch up? (I'm not sure why this works)
    time.sleep(0.01)

    # Return code output
    return self.output

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
        self.output += "\n" + line
        self.output = self.output.strip()

      # Strip then truncate the output if necessary
      self.output = truncate_output(self.output)

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
    code_lines = self.code.strip().split('\n')
    for i, line in enumerate(code_lines, start=1):
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
    if self.output == "" or self.output == "None":
      output_panel = ""
    else:
      output_panel = Panel(self.output,
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


def truncate_output(data):

  # In the future, this will come from a config file
  max_output_chars = 2000

  message = f'Output truncated. Showing the last {max_output_chars} characters.\n\n'

  # Remove previous truncation message if it exists
  if data.startswith(message):
    data = data[len(message):]

  # If data exceeds max length, truncate it and add message
  if len(data) > max_output_chars:
    data = message + data[-max_output_chars:]
  return data


"""
def run_code(language: str, code: str, code_interpreters: dict) -> Union[str, None]:
    # Check if the provided language is supported
    if language not in language_map:
        raise ValueError(f"Unsupported language: {language}")

    # Get or create a code interpreter for the language
    if language not in code_interpreters:
        code_interpreters[language] = CodeInterpreter()
        code_interpreters[language].language = language

    # Create the block
    block = code_interpreters[language]
    output = block.exec(code)

    return output
"""
