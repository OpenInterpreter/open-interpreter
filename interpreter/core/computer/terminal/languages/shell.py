import os
import platform
import re
from .subprocess_language import SubprocessLanguage

class Shell(SubprocessLanguage):
    file_extension = 'sh'
    name = 'Shell'
    aliases = ['bash', 'sh', 'zsh', 'batch', 'bat']

    def __init__(self):
        """Auto-generated docstring for function __init__."""
        super().__init__()
        if platform.system() == 'Windows':
            self.start_cmd = ['cmd.exe']
        else:
            self.start_cmd = [os.environ.get('SHELL', 'bash')]

    def preprocess_code(self, code):
        """Auto-generated docstring for function preprocess_code."""
        return preprocess_shell(code)

    def line_postprocessor(self, line):
        """Auto-generated docstring for function line_postprocessor."""
        return line

    def detect_active_line(self, line):
        """Auto-generated docstring for function detect_active_line."""
        if '##active_line' in line:
            return int(line.split('##active_line')[1].split('##')[0])
        return None

    def detect_end_of_execution(self, line):
        """Auto-generated docstring for function detect_end_of_execution."""
        return '##end_of_execution##' in line

def preprocess_shell(code):
    """
    Add active line markers
    Wrap in a try except (trap in shell)
    Add end of execution marker
    """
    if not has_multiline_commands(code) and os.environ.get('INTERPRETER_ACTIVE_LINE_DETECTION', 'True').lower() == 'true':
        code = add_active_line_prints(code)
    code += '\necho "##end_of_execution##"'
    return code

def add_active_line_prints(code):
    """
    Add echo statements indicating line numbers to a shell string.
    """
    lines = code.split('\n')
    for index, line in enumerate(lines):
        lines[index] = f'echo "##active_line{index + 1}##"\n{line}'
    return '\n'.join(lines)

def has_multiline_commands(script_text):
    """Auto-generated docstring for function has_multiline_commands."""
    continuation_patterns = ['\\\\$', '\\|$', '&&\\s*$', '\\|\\|\\s*$', '<\\($', '\\($', '{\\s*$', '\\bif\\b', '\\bwhile\\b', '\\bfor\\b', 'do\\s*$', 'then\\s*$']
    for line in script_text.splitlines():
        if any((re.search(pattern, line.rstrip()) for pattern in continuation_patterns)):
            return True
    return False