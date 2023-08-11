import subprocess
import threading
import traceback
import platform
import time
import ast
import astor
import sys
import os
import re

# Mapping of languages to their start and print commands
language_map = {
  "python": {
    # Python is run from this interpreter with sys.executable
    # in interactive, quiet, and unbuffered mode
    "start_cmd": sys.executable + " -i -q -u",
    "print_cmd": 'print("{}")'
  },
  "shell": {
    # On Windows, the shell start command is `cmd.exe`
    # On Unix, it should be the SHELL environment variable (defaults to 'bash' if not set)
    "start_cmd": 'cmd.exe' if platform.system() == 'Windows' else os.environ.get('SHELL', 'bash'),
    "print_cmd": 'echo "{}"'
  },
  "javascript": {
    "start_cmd": "node -i",
    "print_cmd": 'console.log("{}")'
  },
  "applescript": {
    # Starts from shell, whatever the user's preference (defaults to '/bin/zsh')
    # (We'll prepend "osascript -e" every time, not once at the start, so we want an empty shell)
    "start_cmd": os.environ.get('SHELL', '/bin/zsh'),
    "print_cmd": 'log "{}"'
  }
}

# Get forbidden_commands (disabled)
"""
with open("interpreter/forbidden_commands.json", "r") as f:
  forbidden_commands = json.load(f)
"""


class CodeInterpreter:
  """
  Code Interpreters display and run code in different languages.
  
  They can control code blocks on the terminal, then be executed to produce an output which will be displayed in real-time.
  """

  def __init__(self, language, debug_mode):
    self.language = language
    self.proc = None
    self.active_line = None
    self.debug_mode = debug_mode

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

  def update_active_block(self):
      """
      This will also truncate the output,
      which we need to do every time we update the active block.
      """
      # Strip then truncate the output if necessary
      self.output = truncate_output(self.output)
  
      # Display it
      self.active_block.active_line = self.active_line
      self.active_block.output = self.output
      self.active_block.refresh()

  def run(self):
    """
    Executes code.
    """

    # Get code to execute
    self.code = self.active_block.code

    # Check for forbidden commands (disabled)
    """
    for line in self.code.split("\n"):
      if line in forbidden_commands:
        message = f"This code contains a forbidden command: {line}"
        message += "\n\nPlease contact the Open Interpreter team if this is an error."
        self.active_block.output = message
        return message
    """

    # Start the subprocess if it hasn't been started
    if not self.proc:
      try:
        self.start_process()
      except:
        # Sometimes start_process will fail!
        # Like if they don't have `node` installed or something.
        
        traceback_string = traceback.format_exc()
        self.output = traceback_string
        self.update_active_block()
  
        # Before you return, wait for the display to catch up?
        # (I'm not sure why this works)
        time.sleep(0.1)
  
        return self.output

    # Reset output
    self.output = ""

    # Use the print_cmd for the selected language
    self.print_cmd = language_map[self.language]["print_cmd"]
    code = self.code

    # Add print commands that tell us what the active line is
    code = self.add_active_line_prints(code)

    # If it's Python, we also need to prepare it for `python -i`
    if self.language == "python":

      # Normalize code by parsing then unparsing it
      try:
        code = prepare_for_python_interactive(code)
      except:
        # If this failed, it means the code didn't compile
        # This traceback will be our output.
        
        traceback_string = traceback.format_exc()
        self.output = traceback_string
        self.update_active_block()

        # Before you return, wait for the display to catch up?
        # (I'm not sure why this works)
        time.sleep(0.1)

        return self.output
        
      code = fix_code_indentation(code)

    # Remove any whitespace lines, as this will break indented blocks
    code_lines = code.split("\n")
    code_lines = [c for c in code_lines if c.strip() != ""]
    code = "\n".join(code_lines)

    # Add end command (we'll be listening for this so we know when it ends)
    code += "\n\n" + self.print_cmd.format('END_OF_EXECUTION')

    # Applescript-specific processing
    if self.language == "applescript":
      # Escape double quotes
      code = code.replace('"', r'\"')
      # Wrap in double quotes
      code = '"' + code + '"'
      # Prepend start command
      code = "osascript -e " + code

    # Debug
    if self.debug_mode:
      print("Running code:")
      print(code)
      print("---")

    # Reset self.done so we can .wait() for it
    self.done = threading.Event()
    self.done.clear()

    # Write code to stdin of the process
    try:
      self.proc.stdin.write(code + "\n")
      self.proc.stdin.flush()
    except BrokenPipeError:
      # It can just.. break sometimes? Let's fix this better in the future
      # For now, just try again
      self.start_process()
      self.run()
      return

    # Wait until execution completes
    self.done.wait()

    # Before you return, wait for the display to catch up?
    # (I'm not sure why this works)
    time.sleep(0.1)

    # Return code output
    return self.output

  def add_active_line_prints(self, code):
    """
    This function takes a code snippet and adds print statements before each line,
    indicating the active line number during execution. The print statements respect
    the indentation of the original code, using the indentation of the next non-blank line.

    Note: This doesn't work on shell if:
    1) Any line starts with whitespace and
    2) Sometimes, doesn't even work for regular loops with newlines between lines
    We return in those cases.
    3) It really struggles with multiline stuff, so I've disabled that (but we really should fix and restore).
    """

    if self.language == "python":
      return add_active_line_prints_to_python(code)

    # Split the original code into lines
    code_lines = code.strip().split('\n')

    # If it's shell, check for breaking cases
    if self.language == "shell":
      if len(code_lines) > 1:
        return code
      if "for" in code or "do" in code or "done" in code:
        return code
      for line in code_lines:
        if line.startswith(" "):
          return code

    # Initialize an empty list to hold the modified lines of code
    modified_code_lines = []

    # Iterate over each line in the original code
    for i, line in enumerate(code_lines):
      # Initialize a variable to hold the leading whitespace of the next non-empty line
      leading_whitespace = ""

      # Iterate over the remaining lines to find the leading whitespace of the next non-empty line
      for next_line in code_lines[i:]:
        if next_line.strip():
          leading_whitespace = next_line[:len(next_line) -
                                         len(next_line.lstrip())]
          break

      # Format the print command with the current line number, using the found leading whitespace
      print_line = self.print_cmd.format(f"ACTIVE_LINE:{i+1}")
      print_line = leading_whitespace + print_line

      # Add the print command and the original line to the modified lines
      modified_code_lines.append(print_line)
      modified_code_lines.append(line)

    # Join the modified lines with newlines and return the result
    code = "\n".join(modified_code_lines)
    return code

  def save_and_display_stream(self, stream):
    # Handle each line of output
    for line in iter(stream.readline, ''):

      if self.debug_mode:
        print("Recieved output line:")
        print(line)
        print("---")
      
      line = line.strip()

      # Node's interactive REPL outputs a billion things
      # So we clean it up:
      if self.language == "javascript":
        if "Welcome to Node.js" in line:
          continue
        if line in ["undefined", 'Type ".help" for more information.']:
          continue
        # Remove trailing ">"s
        line = re.sub(r'^\s*(>\s*)+', '', line)

      # Check if it's a message we added (like ACTIVE_LINE)
      # Or if we should save it to self.output
      if line.startswith("ACTIVE_LINE:"):
        self.active_line = int(line.split(":")[1])
      elif "END_OF_EXECUTION" in line:
        self.done.set()
        self.active_line = None
      elif "KeyboardInterrupt" in line:
        raise KeyboardInterrupt
      else:
        self.output += "\n" + line
        self.output = self.output.strip()

      self.update_active_block()

def fix_code_indentation(code):
  lines = code.split("\n")
  fixed_lines = []
  was_indented = False
  for line in lines:
    current_indent = len(line) - len(line.lstrip())
    if current_indent == 0 and was_indented:
      fixed_lines.append('')  # Add an empty line after an indented block
    fixed_lines.append(line)
    was_indented = current_indent > 0

  return "\n".join(fixed_lines)


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

# Perhaps we should split the "add active line prints" processing to a new file?
# Add active prints to python:

class AddLinePrints(ast.NodeTransformer):
    """
    Transformer to insert print statements indicating the line number
    before every executable line in the AST.
    """

    def insert_print_statement(self, line_number):
        """Inserts a print statement for a given line number."""
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Constant(value=f"ACTIVE_LINE:{line_number}")],
                keywords=[]
            )
        )

    def process_body(self, body):
        """Processes a block of statements, adding print calls."""
        new_body = []
        for sub_node in body:
            if hasattr(sub_node, 'lineno'):
                new_body.append(self.insert_print_statement(sub_node.lineno))
            new_body.append(sub_node)
        return new_body

    def visit(self, node):
        """Overridden visit to transform nodes."""
        new_node = super().visit(node)
        
        # If node has a body, process it
        if hasattr(new_node, 'body'):
            new_node.body = self.process_body(new_node.body)
        
        # If node has an orelse block (like in for, while, if), process it
        if hasattr(new_node, 'orelse') and new_node.orelse:
            new_node.orelse = self.process_body(new_node.orelse)
        
        # Special case for Try nodes as they have multiple blocks
        if isinstance(new_node, ast.Try):
            for handler in new_node.handlers:
                handler.body = self.process_body(handler.body)
            if new_node.finalbody:
                new_node.finalbody = self.process_body(new_node.finalbody)
        
        return new_node

def add_active_line_prints_to_python(code):
    """
    Add print statements indicating line numbers to a python string.
    """
    tree = ast.parse(code)
    transformer = AddLinePrints()
    new_tree = transformer.visit(tree)
    return ast.unparse(new_tree)

def prepare_for_python_interactive(code):
    """
    Adjusts code formatting for the python -i flag. It adds newlines based 
    on whitespace to make code work in interactive mode.
    """

    def get_indentation(line):
        """Returns the number of leading spaces in a line, treating 4 spaces as one level of indentation."""
        return len(line) - len(line.lstrip())

    lines = code.split('\n')
    adjusted_code = []

    previous_indentation = 0

    for line in lines:
        current_indentation = get_indentation(line)

        if current_indentation < previous_indentation:
            if not (line.strip().startswith("except:") or line.strip().startswith("else:") or line.strip().startswith("elif:") or line.strip().startswith("finally:")):
              adjusted_code.append('')  # end of block

        adjusted_code.append(line)
        previous_indentation = current_indentation

    return '\n'.join(adjusted_code)