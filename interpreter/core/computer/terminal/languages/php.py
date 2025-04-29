import os

from .subprocess_language import SubprocessLanguage


class Php(SubprocessLanguage):
    file_extension = "php"
    name = "PHP"
    aliases = ["php"]

    def __init__(
            self,
    ):
        super().__init__()
        self.close_stdin = True
        self.start_cmd = ["php"]

    def preprocess_code(self, code):
        """
        Add active line markers
        Wrap in a try except (trap in shell)
        Add end of execution marker
        """
        lines = code.split("\n")

        if lines[0] == '':
            # remove empty line at the start
            lines.pop(0)

        if lines[-1] == '':
            # remove empty line at the end
            lines.pop(-1)

        if lines[-1] == '?>':
            # remove close tag at the end
            lines.pop(-1)

        r_code = ""
        for i, line in enumerate(lines, 1):
            if os.environ.get("INTERPRETER_ACTIVE_LINE_DETECTION", "True").lower() == "true":
                if -1 != line.find('<?'):
                    if -1 != line.find('<?php'):
                        line.replace("<?", "<?php")
                    r_code += (f'{line} ini_set("display_errors", 1);ini_set("display_startup_errors", 1);'
                               f'error_reporting(E_ALL);\n')
                    continue
                elif -1 == line.find('?>'):
                    # Add commands that tell us what the active line is
                    r_code += f'echo "##active_line{i}##", PHP_EOL;\n'
                r_code += f'{line}\n'

        # Add end command (we'll be listening for this so we know when it ends)
        r_code += 'echo PHP_EOL, "##end_of_execution##", PHP_EOL;'

        return r_code

    def line_postprocessor(self, line):
        return line

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line
