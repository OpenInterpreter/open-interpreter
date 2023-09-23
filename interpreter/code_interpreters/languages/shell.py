import platform
from ..subprocess_code_interpreter import SubprocessCodeInterpreter
import ast
import os

class Shell(SubprocessCodeInterpreter):
    def __init__(self):
        super().__init__()

        # Determine the start command based on the platform
        if platform.system() == 'Windows':
            self.start_cmd = 'cmd.exe'
        else:
            self.start_cmd = os.environ.get('SHELL', 'bash')

    def preprocess_code(self, code):
        return preprocess_shell(code)
    
    def line_postprocessor(self, line):
        return line

    def detect_active_line(self, line):
        if "## active_line " in line:
            return int(line.split("## active_line ")[1].split(" ##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "## end_of_execution ##" in line
        

def preprocess_shell(code):
    """
    Add active line markers
    Wrap in a try except (trap in shell)
    Add end of execution marker
    """
    
    # Add commands that tell us what the active line is
    code = add_active_line_prints(code)
    
    # Wrap in a trap for errors
    code = wrap_in_trap(code)
    
    # Add end command (we'll be listening for this so we know when it ends)
    code += '\necho "## end_of_execution ##"'
    
    return code


def add_active_line_prints(code):
    """
    Add echo statements indicating line numbers to a shell string.
    """
    lines = code.split('\n')
    for index, line in enumerate(lines):
        # Insert the echo command before the actual line
        lines[index] = f'echo "## active_line {index + 1} ##"\n{line}'
    return '\n'.join(lines)


def wrap_in_trap(code):
    """
    Wrap Bash code with a trap to catch errors and display them.
    """
    trap_code = """
trap 'echo "An error occurred on line $LINENO"; exit' ERR
set -E
"""
    return trap_code + code
