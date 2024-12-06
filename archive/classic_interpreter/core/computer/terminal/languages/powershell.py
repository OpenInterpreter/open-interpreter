import os
import platform
import shutil

from .subprocess_language import SubprocessLanguage


class PowerShell(SubprocessLanguage):
    file_extension = "ps1"
    name = "PowerShell"

    def __init__(self):
        super().__init__()

        # Determine the start command based on the platform (use "powershell" for Windows)
        if platform.system() == "Windows":
            self.start_cmd = ["powershell.exe"]
            # self.start_cmd = os.environ.get('SHELL', 'powershell.exe')
        else:
            # On non-Windows platforms, prefer pwsh (PowerShell Core) if available, or fall back to bash
            self.start_cmd = ["pwsh"] if shutil.which("pwsh") else ["bash"]

    def preprocess_code(self, code):
        return preprocess_powershell(code)

    def line_postprocessor(self, line):
        return line

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line


def preprocess_powershell(code):
    """
    Add active line markers
    Wrap in try-catch block
    Add end of execution marker
    """
    # Add commands that tell us what the active line is
    code = add_active_line_prints(code)

    # Wrap in try-catch block for error handling
    code = wrap_in_try_catch(code)

    # Add end marker (we'll be listening for this to know when it ends)
    code += '\nWrite-Output "##end_of_execution##"'

    return code


def add_active_line_prints(code):
    """
    Add Write-Output statements indicating line numbers to a PowerShell script.
    """
    lines = code.split("\n")
    for index, line in enumerate(lines):
        # Insert the Write-Output command before the actual line
        lines[index] = f'Write-Output "##active_line{index + 1}##"\n{line}'
    return "\n".join(lines)


def wrap_in_try_catch(code):
    """
    Wrap PowerShell code in a try-catch block to catch errors and display them.
    """
    try_catch_code = """
try {
    $ErrorActionPreference = "Stop"
"""
    return try_catch_code + code + "\n} catch {\n    Write-Error $_\n}\n"
