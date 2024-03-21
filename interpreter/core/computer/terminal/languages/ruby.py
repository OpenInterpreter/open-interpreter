

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
        #print(processed_code)
        return processed_code

    def line_postprocessor(self, line):
        # If the line count attribute is set and non-zero, decrement and skip the line
        if hasattr(self, "code_line_count") and self.code_line_count > 0:
            self.code_line_count -= 1
            return None
        if "nil" in line:
           return None

        #  if re.match(r"^(\s*>>>\s*|\s*\.\.\.\s*|\s*>\s*|\s*\+\s*|\s*)$", line):
        #      return None
        #  if line.strip().startswith('[1] "') and line.endswith(
        #      '"'
        #  ):  # For strings, trim quotation marks
        #      return line[5:-1].strip()
        #  if line.strip().startswith(
        #      "[1]"
        #  ):  # Normal R output prefix for non-string outputs
        #      return line[4:].strip()

        return line

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line or "##execution_error##" in line


# import re

# from .subprocess_language import SubprocessLanguage


# class Ruby(SubprocessLanguage):
#     file_extension = "rb"
#     name = "Ruby"

#     def __init__(self):
#         super().__init__()
#         self.start_cmd = ["ruby"]  # Command to start Ruby

#     def preprocess_code(self, code):
#         """
#         Ruby code usually doesn't require preprocessing like R does for line markers,
#         but we'll add a similar structure for consistency.
#         Wrap in a begin-rescue block for error handling.
#         """

#         lines = code.split("\n")
#         processed_lines = []

#         for i, line in enumerate(lines, 1):
#             # Add active line print, Ruby uses 'puts' for printing
#             processed_lines.append(f'puts "##active_line{i}##"; {line}')

#         # Join lines to form the processed code
#         processed_code = "\n".join(processed_lines)

#         # Wrap in a begin-rescue block for error handling, similar to tryCatch in R
#         processed_code = f"""
# begin
# {processed_code}
# rescue => e
#   puts "##execution_error##\\n" + e.message
# end
# puts "##end_of_execution##"
# """
#         # Track the number of lines for similar reasons as in R, though it might be less necessary in Ruby
#         self.code_line_count = len(processed_code.split("\n")) - 1

#         return processed_code

#     def line_postprocessor(self, line):
#         # Similar logic to R for skipping lines if we have a code_line_count
#         if hasattr(self, "code_line_count") and self.code_line_count > 0:
#             self.code_line_count -= 1
#             return None

#         # Ruby doesn't use prompts like R's ">", so this can be simplified
#         if line.strip() == "":
#             return None
#         if "##active_line" in line:  # Skip active line markers
#             return None

#         return line

#     def detect_active_line(self, line):
#         # Similar to R, detect the active line marker
#         if "##active_line" in line:
#             return int(line.split("##active_line")[1].split("##")[0])
#         return None

#     def detect_end_of_execution(self, line):
#         # Similar to R, detect the end of execution or error markers
#         return "##end_of_execution##" in line or "##execution_error##" in line

