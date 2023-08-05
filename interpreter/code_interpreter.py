import subprocess
import threading
import time

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

  def __init__(self, language):
    self.language = language
    self.proc = None

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

    # Split the code into lines and add print statements to track the active line
    code_lines = self.code.strip().split('\n')
    self.active_line = 0

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

    # Add end command
    code += "\n\n" + print_cmd.format('END') + "\n"
    
    print("Running:\n---\n", code, "\n---")

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