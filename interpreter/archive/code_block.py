from rich.live import Live
from rich.panel import Panel
from rich.box import MINIMAL
from rich.syntax import Syntax
from rich.table import Table
from rich.console import Group
from rich.console import Console


class CodeBlock:
  """
  Code Blocks display code and outputs in different languages.
  """

  def __init__(self):
    # Define these for IDE auto-completion
    self.language = ""
    self.output = ""
    self.code = ""
    self.active_line = None

    self.live = Live(auto_refresh=False, console=Console(), vertical_overflow="visible")
    self.live.start()

  def update_from_message(self, message):
    if "function_call" in message and "parsed_arguments" in message[
        "function_call"]:

      parsed_arguments = message["function_call"]["parsed_arguments"]

      if parsed_arguments != None:
        self.language = parsed_arguments.get("language")
        self.code = parsed_arguments.get("code")

        if self.code and self.language:
          self.refresh()

  def end(self):
    self.refresh(cursor=False)
    # Destroys live display
    self.live.stop()

  def refresh(self, cursor=True):
    # Get code, return if there is none
    code = self.code
    if not code:
      return
    
    # Create a table for the code
    code_table = Table(show_header=False,
                       show_footer=False,
                       box=None,
                       padding=0,
                       expand=True)
    code_table.add_column()

    # Add cursor    
    if cursor:
      code += "█"

    # Add each line of code to the table
    code_lines = code.strip().split('\n')
    for i, line in enumerate(code_lines, start=1):
      if i == self.active_line:
        # This is the active line, print it with a white background
        syntax = Syntax(line, self.language, theme="bw", line_numbers=False, word_wrap=True)
        code_table.add_row(syntax, style="black on white")
      else:
        # This is not the active line, print it normally
        syntax = Syntax(line, self.language, theme="monokai", line_numbers=False, word_wrap=True)
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
