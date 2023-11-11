# Jupyter Python

import ast
import os
import queue
import sys
import threading
import time
import traceback

from jupyter_client import KernelManager

# Supresses a weird debugging error
os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
# turn off colors in "terminal"
os.environ["ANSI_COLORS_DISABLED"] = "1"


class PythonVision:
    file_extension = "py"
    proper_name = "Python"

    def __init__(self, config):
        self.config = config
        self.km = KernelManager(kernel_name="python3")
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()
        while not self.kc.is_alive():
            time.sleep(0.1)
        time.sleep(0.5)

    def terminate(self):
        self.kc.stop_channels()
        self.km.shutdown_kernel()

    def run(self, code):
        preprocessed_code = self.preprocess_code(code)
        message_queue = queue.Queue()
        self._execute_code(preprocessed_code, message_queue)
        return self._capture_output(message_queue)

    def _execute_code(self, code, message_queue):
        def iopub_message_listener():
            while True:
                try:
                    msg = self.kc.iopub_channel.get_msg(timeout=0.1)
                    content = msg["content"]

                    if msg["msg_type"] == "stream":
                        # Parse output for active lines first
                        def detect_active_line(line):
                            active_line = None
                            while "##active_line" in line:
                                active_line = int(
                                    line.split("##active_line")[1].split("##")[0]
                                )
                                line = line.replace(
                                    "##active_line" + str(active_line) + "##", ""
                                )
                            return line, active_line

                        line, active_line = detect_active_line(content["text"])

                        if active_line:
                            message_queue.put({"active_line": active_line})

                        message_queue.put({"output": line})
                    elif msg["msg_type"] == "error":
                        message_queue.put({"output": "\n".join(content["traceback"])})
                    elif msg["msg_type"] in ["display_data", "execute_result"]:
                        data = content["data"]
                        if "image/png" in data:
                            #### DISABLED PREFIX
                            # image_base64 = "data:image/png;base64," + data['image/png']
                            # message_queue.put({"image": image_base64})
                            message_queue.put({"image": data["image/png"]})
                        elif "image/jpeg" in data:
                            #### DISABLED PREFIX
                            # image_base64 = "data:image/jpeg;base64," + data['image/jpeg']
                            # message_queue.put({"image": image_base64})
                            message_queue.put({"image": data["image/jpeg"]})
                        elif "text/html" in data:
                            message_queue.put({"html": data["text/html"]})
                        elif "text/plain" in data:
                            message_queue.put({"output": data["text/plain"]})
                        elif "application/javascript" in data:
                            message_queue.put(
                                {"javascript": data["application/javascript"]}
                            )

                except queue.Empty:
                    if self.kc.shell_channel.msg_ready():
                        break

        listener_thread = threading.Thread(target=iopub_message_listener)
        listener_thread.start()

        self.kc.execute(code)
        listener_thread.join()

    def _capture_output(self, message_queue):
        while True:
            if not message_queue.empty():
                yield message_queue.get()
            else:
                time.sleep(0.1)
            try:
                output = message_queue.get(timeout=0.3)  # Waits for 0.3 seconds
                yield output
            except queue.Empty:
                # Try to yank 3 more times from it... maybe there's something in there...
                # (I don't know if this actually helps. Maybe we just need to yank 1 more time)
                for _ in range(3):
                    if not message_queue.empty():
                        yield message_queue.get()
                    time.sleep(0.2)
                break

    def _old_capture_output(self, message_queue):
        output = []
        while True:
            try:
                line = message_queue.get_nowait()
                output.append(line)
            except queue.Empty:
                break
        return output

    def preprocess_code(self, code):
        return preprocess_python(code)


def preprocess_python(code):
    """
    Add active line markers
    Wrap in a try except
    """

    # Add print commands that tell us what the active line is
    code = add_active_line_prints(code)

    # Wrap in a try except
    # code = wrap_in_try_except(code)

    # Remove any whitespace lines, as this will break indented blocks
    # (are we sure about this? test this)
    code_lines = code.split("\n")
    code_lines = [c for c in code_lines if c.strip() != ""]
    code = "\n".join(code_lines)

    return code


def add_active_line_prints(code):
    """
    Add print statements indicating line numbers to a python string.
    """
    tree = ast.parse(code)
    transformer = AddLinePrints()
    new_tree = transformer.visit(tree)
    return ast.unparse(new_tree)


class AddLinePrints(ast.NodeTransformer):
    """
    Transformer to insert print statements indicating the line number
    before every executable line in the AST.
    """

    def insert_print_statement(self, line_number):
        """Inserts a print statement for a given line number."""
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.Constant(value=f"##active_line{line_number}##")],
                keywords=[],
            )
        )

    def process_body(self, body):
        """Processes a block of statements, adding print calls."""
        new_body = []

        # In case it's not iterable:
        if not isinstance(body, list):
            body = [body]

        for sub_node in body:
            if hasattr(sub_node, "lineno"):
                new_body.append(self.insert_print_statement(sub_node.lineno))
            new_body.append(sub_node)

        return new_body

    def visit(self, node):
        """Overridden visit to transform nodes."""
        new_node = super().visit(node)

        # If node has a body, process it
        if hasattr(new_node, "body"):
            new_node.body = self.process_body(new_node.body)

        # If node has an orelse block (like in for, while, if), process it
        if hasattr(new_node, "orelse") and new_node.orelse:
            new_node.orelse = self.process_body(new_node.orelse)

        # Special case for Try nodes as they have multiple blocks
        if isinstance(new_node, ast.Try):
            for handler in new_node.handlers:
                handler.body = self.process_body(handler.body)
            if new_node.finalbody:
                new_node.finalbody = self.process_body(new_node.finalbody)

        return new_node


def wrap_in_try_except(code):
    # Add import traceback
    code = "import traceback\n" + code

    # Parse the input code into an AST
    parsed_code = ast.parse(code)

    # Wrap the entire code's AST in a single try-except block
    try_except = ast.Try(
        body=parsed_code.body,
        handlers=[
            ast.ExceptHandler(
                type=ast.Name(id="Exception", ctx=ast.Load()),
                name=None,
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="traceback", ctx=ast.Load()),
                                attr="print_exc",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        )
                    ),
                ],
            )
        ],
        orelse=[],
        finalbody=[],
    )

    # Assign the try-except block as the new body
    parsed_code.body = [try_except]

    # Convert the modified AST back to source code
    return ast.unparse(parsed_code)


# Usage
'''
config = {}  # Your configuration here
python_kernel = Python(config)

code = """
import pandas as pd
import numpy as np
df = pd.DataFrame(np.random.rand(10, 5))
# For HTML output
display(df)
# For image output using matplotlib
import matplotlib.pyplot as plt
plt.figure()
plt.plot(df)
plt.savefig('plot.png')  # Save the plot as a .png file
plt.show()
"""
output = python_kernel.run(code)
for line in output:
    display_output(line)
'''
