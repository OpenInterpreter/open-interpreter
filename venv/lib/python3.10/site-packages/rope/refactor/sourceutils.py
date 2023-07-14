from rope.base import codeanalyze


def get_indents(lines, lineno):
    return codeanalyze.count_line_indents(lines.get_line(lineno))


def find_minimum_indents(source_code):
    result = 80
    lines = source_code.split("\n")
    for line in lines:
        if line.strip() == "":
            continue
        result = min(result, codeanalyze.count_line_indents(line))
    return result


def indent_lines(source_code, amount):
    if amount == 0:
        return source_code
    lines = source_code.splitlines(True)
    result = []
    for line in lines:
        if line.strip() == "":
            result.append("\n")
            continue
        if amount < 0:
            indents = codeanalyze.count_line_indents(line)
            result.append(max(0, indents + amount) * " " + line.lstrip())
        else:
            result.append(" " * amount + line)
    return "".join(result)


def fix_indentation(code: str, new_indents: int) -> str:
    """Change the indentation of `code` to `new_indents`"""
    min_indents = find_minimum_indents(code)
    return indent_lines(code, new_indents - min_indents)


def add_methods(pymodule, class_scope, methods_sources):
    source_code = pymodule.source_code
    lines = pymodule.lines
    insertion_line = class_scope.get_end()
    if class_scope.get_scopes():
        insertion_line = class_scope.get_scopes()[-1].get_end()
    insertion_offset = lines.get_line_end(insertion_line)
    methods = "\n\n" + "\n\n".join(methods_sources)
    indented_methods = fix_indentation(
        methods,
        get_indents(lines, class_scope.get_start())
        + get_indent(pymodule.pycore.project),
    )
    result = []
    result.append(source_code[:insertion_offset])
    result.append(indented_methods)
    result.append(source_code[insertion_offset:])
    return "".join(result)


def get_body(pyfunction):
    """Return unindented function body"""
    # FIXME scope = pyfunction.get_scope()
    pymodule = pyfunction.get_module()
    start, end = get_body_region(pyfunction)
    return fix_indentation(pymodule.source_code[start:end], 0)


def get_body_region(defined):
    """Return the start and end offsets of function body"""
    scope = defined.get_scope()
    pymodule = defined.get_module()
    lines = pymodule.lines
    node = defined.get_ast()
    start_line = node.lineno
    if defined.get_doc() is None:
        start_line = node.body[0].lineno
    elif len(node.body) > 1:
        start_line = node.body[1].lineno
    start = lines.get_line_start(start_line)
    scope_start = pymodule.logical_lines.logical_line_in(scope.start)
    if scope_start[1] >= start_line:
        # a one-liner!
        # XXX: what if colon appears in a string
        start = pymodule.source_code.index(":", start) + 1
        while pymodule.source_code[start].isspace():
            start += 1
    end = min(lines.get_line_end(scope.end) + 1, len(pymodule.source_code))
    return start, end


def get_indent(project):
    return project.prefs.get("indent_size", 4)
