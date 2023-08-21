import subprocess
import webbrowser
import tempfile
import threading
import traceback
import platform
import time
import ast
import astor
import sys
import os
import re


def run_html(html_content):
    # Create a temporary HTML file with the content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
        f.write(html_content.encode())
        
    # Open the HTML file with the default web browser
    webbrowser.open('file://' + os.path.realpath(f.name))

    return f"Saved to {os.path.realpath(f.name)} and opened with the user's default web browser."


# Mapping of languages to their start, run, and print commands
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
  },
  "html": {
    "open_subrocess": False,
    "run_function": run_html,
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
                                 text=True,
                                 bufsize=0)

    # Start watching ^ its `stdout` and `stderr` streams
    threading.Thread(target=self.save_and_display_stream,
                     args=(self.proc.stdout, False), # Passes False to is_error_stream
                     daemon=True).start()
    threading.Thread(target=self.save_and_display_stream,
                     args=(self.proc.stderr, True), # Passes True to is_error_stream
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

    # Should we keep a subprocess open? True by default
    open_subrocess = language_map[self.language].get("open_subrocess", True)

    # Start the subprocess if it hasn't been started
    if not self.proc and open_subrocess:
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
    self.print_cmd = language_map[self.language].get("print_cmd")
    code = self.code

    # Add print commands that tell us what the active line is
    if self.print_cmd:
      try:
        code = self.add_active_line_prints(code)
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

    if self.language == "python":
      # This lets us stop execution when error happens (which is not default -i behavior)
      # And solves a bunch of indentation problems-- if everything's indented, -i treats it as one block
      code = wrap_in_try_except(code)

    # Remove any whitespace lines, as this will break indented blocks
    # (are we sure about this? test this)
    code_lines = code.split("\n")
    code_lines = [c for c in code_lines if c.strip() != ""]
    code = "\n".join(code_lines)

    # Add end command (we'll be listening for this so we know when it ends)
    if self.print_cmd and self.language != "applescript": # Applescript is special. Needs it to be a shell command because 'return' (very common) will actually return, halt script
      code += "\n\n" + self.print_cmd.format('END_OF_EXECUTION')

    # Applescript-specific processing
    if self.language == "applescript":
      # Escape double quotes
      code = code.replace('"', r'\"')
      # Wrap in double quotes
      code = '"' + code + '"'
      # Prepend start command
      code = "osascript -e " + code
      # Append end command
      code += '\necho "END_OF_EXECUTION"'
      
    # Debug
    if self.debug_mode:
      print("Running code:")
      print(code)
      print("---")

    # HTML-specific processing (and running)
    if self.language == "html":
      output = language_map["html"]["run_function"](code)
      return output

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

  def save_and_display_stream(self, stream, is_error_stream):
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

      # Python's interactive REPL outputs a million things
      # So we clean it up:
      if self.language == "python":
        if re.match(r'^(\s*>>>\s*|\s*\.\.\.\s*)', line):
          continue

      # Check if it's a message we added (like ACTIVE_LINE)
      # Or if we should save it to self.output
      if line.startswith("ACTIVE_LINE:"):
        self.active_line = int(line.split(":")[1])
      elif "END_OF_EXECUTION" in line:
        self.done.set()
        self.active_line = None
      elif is_error_stream and "KeyboardInterrupt" in line:
        raise KeyboardInterrupt
      else:
        self.output += "\n" + line
        self.output = self.output.strip()

      self.update_active_block()

def truncate_output(data):
  needs_truncation = False

  # In the future, this will come from a config file
  max_output_chars = 2000

  message = f'Output truncated. Showing the last {max_output_chars} characters.\n\n'

  # Remove previous truncation message if it exists
  if data.startswith(message):
    data = data[len(message):]
    needs_truncation = True

  # If data exceeds max length, truncate it and add message
  if len(data) > max_output_chars or needs_truncation:
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

        # In case it's not iterable:
        if not isinstance(body, list):
            body = [body]
    
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

def wrap_in_try_except(code):
    # Add import traceback
    code = "import traceback\n" + code

    # Parse the input code into an AST
    parsed_code = ast.parse(code)

    # Wrap the entire code's AST in a single try-except block
    try_except = ast.Try(
        body=parsed_code.body,
        handlers=[
            ast.ExceptHandler(
                type=ast.Name(id="Exception", ctx=ast.Load()),
                name=None,
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(value=ast.Name(id="traceback", ctx=ast.Load()), attr="print_exc", ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        )
                    ),
                ]
            )
        ],
        orelse=[],
        finalbody=[]
    )

    # Assign the try-except block as the new body
    parsed_code.body = [try_except]

    # Convert the modified AST back to source code
    return ast.unparse(parsed_code)
