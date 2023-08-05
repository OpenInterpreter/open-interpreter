import subprocess
import threading
import time
import ast
import astor

# Mapping of languages to their start and print commands
language_map = {
  "python": {
    "start_cmd": "python -i -q -u",
    "print_cmd": 'print("{}")'
  },
  "bash": {
    "start_cmd": "bash --noediting",
    "print_cmd": 'echo "{}"'
  },
  "javascript": {
    "start_cmd": "node -i",
    "print_cmd": 'console.log("{}")'
  }
}


class CodeInterpreter:
  """
  Code Interpreters display and run code in different languages.
  
  They can create code blocks on the terminal, then be executed to produce an output which will be displayed in real-time.
  """

  def __init__(self, language):
    self.language = language
    self.proc = None
    self.active_line = None

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

  def run(self):

    self.code = self.active_block.code

    if not self.proc:
      self.start_process()

    # Reset output
    self.output = ""

    # Use the print_cmd for the selected language
    self.print_cmd = language_map[self.language]["print_cmd"]
    code = self.code

    # If it's Python, insert print commands to say what line is running and fix indentation
    if self.language == "python":
      print("CODE:\n", code)
      code = self.add_active_line_prints(code)
      print("ACODE:\n", code)
      code = normalize(code)
      print("NCODE:\n", code)
      code = fix_code_indentation(code)
      print("FCODE:\n", code)

    # Add end command
    code += "\n\n" + self.print_cmd.format('END') + "\n"

    print("Running code:")
    print(code)
    print("---")

    # Reset self.done so we can .wait() for it
    self.done = threading.Event()
    self.done.clear()

    # Write code to stdin of the process
    self.proc.stdin.write(code)
    self.proc.stdin.flush()

    # Wait until execution completes
    self.done.wait()

    # Wait for the display to catch up? (I'm not sure why this works)
    time.sleep(0.01)

    # Return code output
    return self.output

  def add_active_line_prints(self, code):
    """
    This function takes a code snippet and adds print statements before each line,
    indicating the active line number during execution. The print statements respect
    the indentation of the original code, using the indentation of the next non-blank line.
    """
    
    # Split the original code into lines
    code_lines = code.strip().split('\n')

    # Initialize an empty list to hold the modified lines of code
    modified_code_lines = []

    # Iterate over each line in the original code
    for i, line in enumerate(code_lines):
        # Initialize a variable to hold the leading whitespace of the next non-empty line
        leading_whitespace = ""

        # Iterate over the remaining lines to find the leading whitespace of the next non-empty line
        for next_line in code_lines[i:]:
            if next_line.strip():
                leading_whitespace = next_line[:len(next_line) - len(next_line.lstrip())]
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
      line = line.strip()

      # Check if it's a message we added (like ACTIVE_LINE)
      # Or if we should save it to self.output
      if line.startswith("ACTIVE_LINE:"):
        self.active_line = int(line.split(":")[1])
      elif line == "END":
        self.done.set()
        self.active_line = None
      else:
        self.output += "\n" + line
        self.output = self.output.strip()

      # Strip then truncate the output if necessary
      self.output = truncate_output(self.output)

      # Update the active block
      self.active_block.active_line = self.active_line
      self.active_block.output = self.output
      self.active_block.refresh()

def normalize(code):
    # Parse the code into an AST
    parsed_ast = ast.parse(code)

    # Convert the AST back to source code
    return astor.to_source(parsed_ast)

def fix_code_indentation(code):
    lines = code.split("\n")
    fixed_lines = []
    was_indented = False
    for line in lines:
        current_indent = len(line) - len(line.lstrip())
        if current_indent == 0 and was_indented:
            fixed_lines.append('') # Add an empty line after an indented block
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