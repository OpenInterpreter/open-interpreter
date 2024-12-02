import os
import queue
import re
import subprocess
import threading
import time
import traceback

from .subprocess_language import SubprocessLanguage


class Java(SubprocessLanguage):
    file_extension = "java"
    name = "Java"

    def __init__(self):
        super().__init__()
        self.start_cmd = None  # We will handle the start command in the run method

    def preprocess_code(self, code):
        return preprocess_java(code)

    def line_postprocessor(self, line):
        # Clean up output from javac and java
        return line.strip()

    def detect_active_line(self, line):
        if "##active_line" in line:
            return int(line.split("##active_line")[1].split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line

    def run(self, code):
        try:
            # Extract the class name from the code
            match = re.search(r"class\s+(\w+)", code)
            if not match:
                yield {
                    "type": "console",
                    "format": "output",
                    "content": "Error: No class definition found in the provided code.",
                }
                return

            class_name = match.group(1)
            file_name = f"{class_name}.java"

            # Write the Java code to a file, preserving newlines
            with open(file_name, "w", newline="\n") as file:
                file.write(code)

            # Compile the Java code
            compile_process = subprocess.Popen(
                ["javac", file_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = compile_process.communicate()

            if compile_process.returncode != 0:
                yield {
                    "type": "console",
                    "format": "output",
                    "content": f"Compilation Error:\n{stderr}",
                }
                return

            # Run the compiled Java code
            run_process = subprocess.Popen(
                ["java", class_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout_thread = threading.Thread(
                target=self.handle_stream_output,
                args=(run_process.stdout, False),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.handle_stream_output,
                args=(run_process.stderr, True),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            stdout_thread.join()
            stderr_thread.join()

            run_process.wait()
            self.done.set()

            while True:
                if not self.output_queue.empty():
                    yield self.output_queue.get()
                else:
                    time.sleep(0.1)
                try:
                    output = self.output_queue.get(timeout=0.3)
                    yield output
                except queue.Empty:
                    if self.done.is_set():
                        for _ in range(3):
                            if not self.output_queue.empty():
                                yield self.output_queue.get()
                            time.sleep(0.2)
                        break

        except Exception as e:
            yield {
                "type": "console",
                "format": "output",
                "content": f"{traceback.format_exc()}",
            }
        finally:
            # Clean up the generated Java files
            if os.path.exists(file_name):
                os.remove(file_name)
            class_file = file_name.replace(".java", ".class")
            if os.path.exists(class_file):
                os.remove(class_file)


def preprocess_java(code):
    """
    Add active line markers
    Add end of execution marker
    """
    lines = code.split("\n")
    processed_lines = []

    for i, line in enumerate(lines, 1):
        # Add active line print
        processed_lines.append(f'System.out.println("##active_line{i}##");')
        processed_lines.append(line)

    # Join lines to form the processed code
    code = "\n".join(processed_lines)

    # Add end of execution marker
    code += '\nSystem.out.println("##end_of_execution##");'
    return code
