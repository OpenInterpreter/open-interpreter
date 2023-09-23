from ..subprocess_code_interpreter import SubprocessCodeInterpreter
import re

class JavaScript(SubprocessCodeInterpreter):
    def __init__(self):
        super().__init__()
        self.start_cmd = "node -i"
        
    def preprocess_code(self, code):
        return preprocess_javascript(code)
    
    def line_postprocessor(self, line):
        # Node's interactive REPL outputs a billion things
        # So we clean it up:
        if "Welcome to Node.js" in line:
            return None
        if line.strip() in ["undefined", 'Type ".help" for more information.']:
            return None
        # Remove trailing ">"s
        line = re.sub(r'^\s*(>\s*)+', '', line)
        return line

    def detect_active_line(self, line):
        if "## active_line " in line:
            return int(line.split("## active_line ")[1].split(" ##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "## end_of_execution ##" in line
    

def preprocess_javascript(code):
    """
    Add active line markers
    Wrap in a try catch
    Add end of execution marker
    """

    # Split code into lines
    lines = code.split("\n")
    processed_lines = []

    for i, line in enumerate(lines, 1):
        # Add active line print
        processed_lines.append(f'console.log("## active_line {i} ##");')
        processed_lines.append(line)

    # Join lines to form the processed code
    processed_code = "\n".join(processed_lines)

    # Wrap in a try-catch and add end of execution marker
    processed_code = f"""
try {{
{processed_code}
}} catch (e) {{
    console.log(e);
}}
console.log("## end_of_execution ##");
"""

    return processed_code