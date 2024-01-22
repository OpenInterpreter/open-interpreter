# Subprocess based

import ast
import os
import re
import shlex
import sys

from .subprocess_language import SubprocessLanguage


class Python(SubprocessLanguage):
    file_extension = "py"
    name = "Python"

    def __init__(self):
        super().__init__()

        executable = sys.executable
        if os.name != "nt":  # not Windows
            executable = shlex.quote(executable)
        self.start_cmd = [executable, "-i", "-q", "-u"]

    def preprocess_code(self, code):
        return preprocess_python(code)

    def line_postprocessor(self, line):
        if re.match(r"^(\s*>>>\s*|\s*\.\.\.\s*)", line):
            return None
        return line

    def detect_active_line(self, line):
        if "##active_line" in line:
            # Split the line by "##active_line" and grab the last element
            last_active_line = line.split("##active_line")[-1]
            # Split the last active line by "##" and grab the first element
            return int(last_active_line.split("##")[0])
        return None

    def detect_end_of_execution(self, line):
        return "##end_of_execution##" in line


def preprocess_python(code):
    """
    Add active line markers
    Wrap in a try except
    Add end of execution marker
    """

    # Add print commands that tell us what the active line is
    # but don't do this if any line starts with ! or %
    if not any(line.strip().startswith(("!", "%")) for line in code.split("\n")):
        code = add_active_line_prints(code)

    # Wrap in a try except
    code = wrap_in_try_except(code)

    # Remove any whitespace lines, as this will break indented blocks
    # (are we sure about this? test this)
    code_lines = code.split("\n")
    code_lines = [c for c in code_lines if c.strip() != ""]
    code = "\n".join(code_lines)

    # Add end command (we'll be listening for this so we know when it ends)
    code += '\n\nprint("##end_of_execution##")'

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
