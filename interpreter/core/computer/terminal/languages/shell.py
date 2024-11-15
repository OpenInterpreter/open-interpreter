import os
import queue
import re
import subprocess
import threading

from .subprocess_language import SubprocessLanguage


def preprocess_shell(code):
    """
    Add active line markers
    Wrap in a try except (trap in shell)
    Add end of execution marker
    """

    # Add commands that tell us what the active line is
    # if it's multiline, just skip this. soon we should make it work with multiline
    if (
            not has_multiline_commands(code)
            and os.environ.get("INTERPRETER_ACTIVE_LINE_DETECTION", "True").lower()
            == "true"
    ):
        code = add_active_line_prints(code)

    # Add end command (we'll be listening for this so we know when it ends)
    code += '\necho "##end_of_execution##"'

    return code

def has_multiline_commands(script_text):
    """
    Check if the shell script contains multiline commands.
    """
    # Patterns that indicate a line continues
    continuation_patterns = [
        r"\\$",           # Line continuation character at the end of the line
        r"\|$",           # Pipe character at the end of the line indicating a pipeline continuation
        r"&&\s*$",        # Logical AND at the end of the line
        r"\|\|\s*$",      # Logical OR at the end of the line
        r"<\($",          # Start of process substitution
        r"\($",           # Start of subshell
        r"{\s*$",         # Start of a block
        r"\bif\b",        # Start of an if statement
        r"\bwhile\b",     # Start of a while loop
        r"\bfor\b",       # Start of a for loop
        r"do\s*$",        # 'do' keyword for loops
        r"then\s*$",      # 'then' keyword for if statements
    ]

    # Check each line for multiline patterns
    for line in script_text.splitlines():
        if any(re.search(pattern, line.rstrip()) for pattern in continuation_patterns):
            return True

    return False

def add_active_line_prints(code):
    """
    Add echo statements indicating line numbers to a shell string.
    """
    lines = code.split("\n")
    for index, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            continue
        # Insert the echo command before the actual line
        lines[index] = f'echo "##active_line{index + 1}##"\n{line}'
    return "\n".join(lines)

def preprocess_shell(code):
    # Add commands that tell us what the active line is
    if (
            not has_multiline_commands(code)
            and os.environ.get("INTERPRETER_ACTIVE_LINE_DETECTION", "True").lower()
            == "true"
    ):
        code = add_active_line_prints(code)

    # Add end command (we'll be listening for this so we know when it ends)
    code += '\necho "##end_of_execution##"'

    return code

class Shell(SubprocessLanguage):
    file_extension = "sh"
    name = "Shell"
    aliases = ["bash", "sh", "zsh", "batch", "bat"]

    def run(self, code):
        code = preprocess_shell(code)
        self.output_queue = queue.Queue()
        self.done = threading.Event()

        process = subprocess.Popen(
            code,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # Prevent subprocess from waiting for input
            text=True
        )

        threading.Thread(
            target=self.handle_stream_output,
            args=(process.stdout, False),
            daemon=True,
        ).start()
        threading.Thread(
            target=self.handle_stream_output,
            args=(process.stderr, True),
            daemon=True,
        ).start()

        threading.Thread(
            target=self.wait_for_process,
            args=(process,),
            daemon=True,
        ).start()

        while True:
            try:
                output = self.output_queue.get(timeout=0.1)
                yield output
            except queue.Empty:
                if self.done.is_set():
                    break

    def handle_stream_output(self, stream, is_error_stream):
        try:
            for line in iter(stream.readline, ""):
                line = line.rstrip('\n')
                if self.detect_active_line(line):
                    active_line = self.detect_active_line(line)
                    self.output_queue.put(
                        {
                            "type": "console",
                            "format": "active_line",
                            "content": active_line,
                        }
                    )
                    line = re.sub(r"##active_line\d+##", "", line)
                    if line:
                        self.output_queue.put(
                            {"type": "console", "format": "output", "content": line}
                        )
                elif self.detect_end_of_execution(line):
                    line = line.replace("##end_of_execution##", "").strip()
                    if line:
                        self.output_queue.put(
                            {"type": "console", "format": "output", "content": line}
                        )
                else:
                    self.output_queue.put(
                        {"type": "console", "format": "output", "content": line}
                    )
        except Exception as e:
            self.output_queue.put(
                {"type": "console", "format": "error", "content": str(e)}
            )
        finally:
            stream.close()

    def wait_for_process(self, process, timeout=30):
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            self.output_queue.put(
                {
                    "type": "console",
                    "format": "error",
                    "content": f"Process timed out after {timeout} seconds.",
                }
            )
        finally:
            self.done.set()

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line


