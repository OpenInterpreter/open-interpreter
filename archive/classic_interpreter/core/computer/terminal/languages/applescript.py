import os

from .subprocess_language import SubprocessLanguage


class AppleScript(SubprocessLanguage):
    file_extension = "applescript"
    name = "AppleScript"

    def __init__(self):
        super().__init__()
        self.start_cmd = [os.environ.get("SHELL", "/bin/zsh")]

    def preprocess_code(self, code):
        """
        Inserts an end_of_execution marker and adds active line indicators.
        """
        # Add active line indicators to the code
        code = self.add_active_line_indicators(code)

        # Escape double quotes
        code = code.replace('"', r"\"")

        # Wrap in double quotes
        code = '"' + code + '"'

        # Prepend start command for AppleScript
        code = "osascript -e " + code

        # Append end of execution indicator
        code += '; echo "##end_of_execution##"'

        return code

    def add_active_line_indicators(self, code):
        """
        Adds log commands to indicate the active line of execution in the AppleScript.
        """
        modified_lines = []
        lines = code.split("\n")

        for idx, line in enumerate(lines):
            # Add log command to indicate the line number
            if line.strip():  # Only add if line is not empty
                modified_lines.append(f'log "##active_line{idx + 1}##"')
            modified_lines.append(line)

        return "\n".join(modified_lines)

    def detect_active_line(self, line):
        """
        Detects active line indicator in the output.
        """
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        """
        Detects end of execution marker in the output.
        """
        return "##end_of_execution##" in line
