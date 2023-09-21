"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import subprocess
import threading
from queue import Queue
import time
import traceback
from .base_code_interpreter import BaseCodeInterpreter

class SubprocessCodeInterpreter(BaseCodeInterpreter):
    def __init__(self):
        self.start_cmd = ""
        self.process = None
        self.debug_mode = False
        self.output_queue = Queue()
        self.done = threading.Event()

    def detect_active_line(self, line):
        return None
    
    def detect_end_of_execution(self, line):
        return None
    
    def line_postprocessor(self, line):
        return line
    
    def preprocess_code(self, code):
        """
        This needs to insert an end_of_execution marker of some kind,
        which can be detected by detect_end_of_execution.

        Optionally, add active line markers for detect_active_line.
        """
        return code
    
    def terminate(self):
        self.process.terminate()

    def start_process(self):
        self.process = subprocess.Popen(self.start_cmd.split(),
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        bufsize=0)
        threading.Thread(target=self.handle_stream_output,
                            args=(self.process.stdout, False),
                            daemon=True).start()
        threading.Thread(target=self.handle_stream_output,
                            args=(self.process.stderr, True),
                            daemon=True).start()

    def run(self, code):
        retry_count = 0
        max_retries = 3

        # Setup
        try:
            code = self.preprocess_code(code)
            if not self.process:
                self.start_process()
        except:
            yield {"output": traceback.format_exc()}
            return
            

        while retry_count <= max_retries:
            if self.debug_mode:
                print(f"Running code:\n{code}\n---")

            self.done.clear()

            try:
                self.process.stdin.write(code + "\n")
                self.process.stdin.flush()
                break
            except:
                yield {"output": traceback.format_exc()}
                yield {"output": f"Retrying... ({retry_count}/{max_retries})"}
                retry_count += 1
                if retry_count > max_retries:
                    yield {"output": "Maximum retries reached. Could not execute code."}
                    return

        while not self.done.is_set():
            if not self.output_queue.empty():
                item = self.output_queue.get()
                yield item
            else:
                self.done.wait(0.1)

    def handle_stream_output(self, stream, is_error_stream):
        for line in iter(stream.readline, ''):
            if self.debug_mode:
                print(f"Received output line:\n{line}\n---")

            line = self.line_postprocessor(line)

            if self.detect_active_line(line):
                active_line = self.detect_active_line(line)
                self.output_queue.put({"active_line": active_line})
            elif self.detect_end_of_execution(line):
                self.output_queue.put({"active_line": None})
                time.sleep(0.1)
                self.done.set()
            elif is_error_stream and "KeyboardInterrupt" in line:
                self.output_queue.put({"output": "KeyboardInterrupt"})
                time.sleep(0.1)
                self.done.set()
            else:
                self.output_queue.put({"output": line})