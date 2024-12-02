import re
from pathlib import Path

from .subprocess_language import SubprocessLanguage


class Ruby(SubprocessLanguage):
    file_extension = "rb"
    name = "Ruby"

    def __init__(self):
        super().__init__()
        self.start_cmd = ["irb"]

    def preprocess_code(self, code):
        """
        Add active line markers
        Wrap in a tryCatch for better error handling
        Add end of execution marker
        """

        lines = code.split("\n")
        processed_lines = []

        for i, line in enumerate(lines, 1):
            # Add active line print
            processed_lines.append(f'puts "##active_line{i}##"')
            processed_lines.append(line)
        # Join lines to form the processed code
        processed_code = "\n".join(processed_lines)

        # Wrap in a tryCatch for error handling and add end of execution marker
        processed_code = f"""
begin
  {processed_code}
rescue => e
  puts "##execution_error##\\n" + e.message
ensure
  puts "##end_of_execution##\\n"
end
"""
        self.code_line_count = len(processed_code.split("\n"))
        # print(processed_code)
        return processed_code

    def line_postprocessor(self, line):
        # If the line count attribute is set and non-zero, decrement and skip the line
        if hasattr(self, "code_line_count") and self.code_line_count > 0:
            self.code_line_count -= 1
            return None
        if "nil" in line:
            return None
        return line

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line or "##execution_error##" in line
