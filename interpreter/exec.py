"""
exec_and_capture_output is a function that runs code in a stateful Jupyter notebook and captures its outputs (exceptions, print statements-- anything that would display in the terminal). It renders those outputs to the user's terminal as they're generated.
"""

import ast
import astor
from IPython.core.interactiveshell import InteractiveShell
from IPython.core.ultratb import AutoFormattedTB
from contextlib import redirect_stdout, redirect_stderr
import sys
import re
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.box import MINIMAL

# Set up the error format
itb = AutoFormattedTB(mode = 'Plain', color_scheme='Neutral', tb_offset = 1)

def check_for_syntax_errors(code):
    # Needs to happen before we execute.
    lines = code.split('\n')
    filtered_lines = [line for line in lines if not re.match(r'^[!%]', line.strip())]
    cleaned_code = '\n'.join(filtered_lines)
    compile(cleaned_code, '<string>', 'exec')

def truncate_output(data, max_output_chars):
    message = f'Output truncated. Showing the last {max_output_chars} characters. Adjust via `interpreter.max_output_chars`.\n\n'

    # Remove previous truncation message if it exists
    if data.startswith(message):
        data = data[len(message):]

    # If data exceeds max length, truncate it and add message
    if len(data) > max_output_chars:
        data = message + data[-max_output_chars:]
    return data

class RichOutStream:

    def __init__(self, live, max_output_chars):
        self.live = live
        self.data = ""
        self.max_output_chars = max_output_chars

    def write(self, data):
        self.data += data

        # Clean ANSI color codes
        self.data = re.sub(r'\x1b\[[0-9;]*m', '', self.data)
      
        # Clean ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.data = ansi_escape.sub('', self.data)

        # Truncate and prepend a message if truncated
        self.data = truncate_output(self.data, max_output_chars=self.max_output_chars)

        # None outputs should be empty, they happen with things like plt.show()
        if self.data.strip() == "None" or self.data.strip() == "":
            self.data = ""
            self.live.update("")
        else:
            panel = Panel(self.data.strip(), box=MINIMAL, style="#FFFFFF on #3b3b37")
            self.live.update(panel)

    def flush(self):
        pass

    # Some things (like youtube-dl) will check if this is "isatty()"
    # then fail if it isn't present, so. If this is True it breaks the CLI, so we set it to False (I don't know what it means).
    def isatty(self):
        return False

def exec_and_capture_output(code, max_output_chars, forbidden_commands):
    # Store the original stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # Create new instance of InteractiveShell
    shell = InteractiveShell.instance()

    # Disable automatic stdout/stderr flushing
    #shell.ast_node_interactivity = "last_expr_or_assign"
    # No wait, this should be none so we can handle printing the last node on our own. Why did we have it set to last_expr_or_assign?
    shell.ast_node_interactivity = "none"
    
    # Store the original traceback handler
    old_showtraceback = shell.showtraceback

    # Define a new traceback handler
    def custom_showtraceback(*args, **kwargs):
        etype, value, tb = sys.exc_info()
        traceback_str = ''.join(itb.structured_traceback(etype, value, tb))
        print(traceback_str)

    shell.showtraceback = custom_showtraceback

    code = jupyterify_code(code)

    live = Live(console=Console())
    try:
        live.start()
        rich_stdout = RichOutStream(live, max_output_chars)

        # Check syntax before attempting to execute
        try:
            check_for_syntax_errors(code)
        except SyntaxError:
            # Do the same thing you do in custom_showtraceback
            etype, value, tb = sys.exc_info()
            traceback_str = ''.join(itb.structured_traceback(etype, value, tb))
            rich_stdout.write(traceback_str)

            live.refresh() # Sometimes this can happen so quickly, it doesn't auto refresh in time
            shell.ast_node_interactivity = "last_expr_or_assign" # Restore last node interactivity
            
            return rich_stdout.data.strip()

        # Check for forbidden_commands
        lines = code.split('\n')
        for line in lines:
          if line.strip() in forbidden_commands:
            message = f"Command '{line}' is not permitted. Modify `interpreter.forbidden_commands` to override."
            rich_stdout.write(message)
            
            live.refresh() # Sometimes this can happen so quickly, it doesn't auto refresh in time
            shell.ast_node_interactivity = "last_expr_or_assign" # Restore last

            return rich_stdout.data.strip()

        # If syntax is correct, execute the code
        with redirect_stdout(rich_stdout), redirect_stderr(rich_stdout), live:
            shell.run_cell(code)

        live.refresh() # Sometimes this can happen so quickly, it doesn't auto refresh in time
        shell.ast_node_interactivity = "last_expr_or_assign" # Restore last node interactivity

        return rich_stdout.data.strip()
    finally:
        # Restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Restore the original traceback handler
        shell.showtraceback = old_showtraceback

        live.stop()

#code = """print("<3")"""
#exec_and_capture_output(code)

def jupyterify_code(code):
    # Split code into lines
    code_lines = code.split('\n')

    # Separate magic commands and remember their indices
    magic_commands = {}
    code_lines_without_magic = []
    for i, line in enumerate(code_lines):
        stripped = line.strip()
        if stripped.startswith(('!', '%')):
            magic_commands[i] = line
        else:
            code_lines_without_magic.append(line)

    # Create the new version of the code without magic commands
    code_without_magic = '\n'.join(code_lines_without_magic)

    # Try to parse the code without magic commands as an AST
    try:
        tree = ast.parse(code_without_magic)
    except SyntaxError:
        return code

    # A single pip command would do this
    if len(tree.body) == 0:
        return code

    # Replace last statement with print if needed
    last_statement = tree.body[-1]
    if isinstance(last_statement, ast.Expr) and not (isinstance(last_statement.value, ast.Call) and isinstance(last_statement.value.func, ast.Name) and last_statement.value.func.id == 'print'):
        tree.body[-1] = ast.Expr(ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[last_statement.value], keywords=[]))

    # Convert modified AST back into source code
    new_code_lines = astor.to_source(tree).split('\n')

    # Reinsert magic commands in their original places
    for i, line in magic_commands.items():
        new_code_lines.insert(i, line)

    # Join the code lines back together into a single string
    new_code = '\n'.join(new_code_lines)

    return new_code