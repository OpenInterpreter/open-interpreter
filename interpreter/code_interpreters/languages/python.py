"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import sys
from ..subprocess_code_interpreter import SubprocessCodeInterpreter

class Python(SubprocessCodeInterpreter):
    def __init__(self):
        super().__init__()
        self.start_cmd = sys.executable + " -i -q -u"
        
    def preprocess_code(self, code):
        # Insert Python-specific code for tracking active line numbers,
        # printing special markers, etc.
        processed_code = ""
        for i, line in enumerate(code.split('\n'), 1):
            processed_code += f'\nprint("## active_line {i} ##")\n{line}'
        processed_code += '\nprint("## end_of_execution ##")'
        return processed_code.strip()
    
    def line_postprocessor(self, line):
        return line

    def detect_active_line(self, line):
        if "## active_line " in line:
            return int(line.split("## active_line ")[1].split(" ##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "## end_of_execution ##" in line