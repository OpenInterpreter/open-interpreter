from rope.base import codeanalyze, evaluate, exceptions, libutils, utils, worder
from rope.base.codeanalyze import ArrayLinesAdapter, LogicalLineFinder


class FixSyntax:
    def __init__(self, project, code, resource, maxfixes=1):
        self.project = project
        self.code = code
        self.resource = resource
        self.maxfixes = maxfixes

    @utils.saveit
    def get_pymodule(self):
        """Get a `PyModule`"""
        msg = None
        code = self.code
        tries = 0
        while True:
            try:
                if (
                    tries == 0
                    and self.resource is not None
                    and self.resource.read() == code
                ):
                    return self.project.get_pymodule(self.resource, force_errors=True)
                return libutils.get_string_module(
                    self.project, code, resource=self.resource, force_errors=True
                )
            except exceptions.ModuleSyntaxError as e:
                if msg is None:
                    msg = f"{e.filename}:{e.lineno} {e.message_}"
                if tries < self.maxfixes:
                    tries += 1
                    self.commenter.comment(e.lineno)
                    code = "\n".join(self.commenter.lines)
                else:
                    raise exceptions.ModuleSyntaxError(
                        e.filename, e.lineno, f"Failed to fix error: {msg}"
                    )

    @property
    @utils.saveit
    def commenter(self):
        return _Commenter(self.code)

    def pyname_at(self, offset):
        pymodule = self.get_pymodule()

        def old_pyname():
            word_finder = worder.Worder(self.code, True)
            expression = word_finder.get_primary_at(offset)
            expression = expression.replace("\\\n", " ").replace("\n", " ")
            lineno = self.code.count("\n", 0, offset)
            scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
            return evaluate.eval_str(scope, expression)

        new_code = pymodule.source_code

        def new_pyname():
            newoffset = self.commenter.transferred_offset(offset)
            return evaluate.eval_location(pymodule, newoffset)

        if new_code.startswith(self.code[: offset + 1]):
            return new_pyname()
        result = old_pyname()
        if result is None:
            return new_pyname()
        return result


class _Commenter:
    def __init__(self, code):
        self.code = code
        self.lines = self.code.split("\n")
        self.lines.append("\n")
        self.origs = list(range(len(self.lines) + 1))
        self.diffs = [0] * (len(self.lines) + 1)

    def comment(self, lineno):
        start = _logical_start(self.lines, lineno, check_prev=True) - 1
        # using self._get_stmt_end() instead of self._get_block_end()
        # to lower commented lines
        end = self._get_stmt_end(start)
        indents = _get_line_indents(self.lines[start])
        if 0 < start:
            last_lineno = self._last_non_blank(start - 1)
            last_line = self.lines[last_lineno]
            if last_line.rstrip().endswith(":"):
                indents = _get_line_indents(last_line) + 4
        self._set(start, " " * indents + "pass")
        for line in range(start + 1, end + 1):
            self._set(line, self.lines[start])
        self._fix_incomplete_try_blocks(lineno, indents)

    def transferred_offset(self, offset):
        lineno = self.code.count("\n", 0, offset)
        diff = sum(self.diffs[:lineno])
        return offset + diff

    def _last_non_blank(self, start):
        while start > 0 and self.lines[start].strip() == "":
            start -= 1
        return start

    def _get_block_end(self, lineno):
        end_line = lineno
        base_indents = _get_line_indents(self.lines[lineno])
        for i in range(lineno + 1, len(self.lines)):
            if _get_line_indents(self.lines[i]) >= base_indents:
                end_line = i
            else:
                break
        return end_line

    def _get_stmt_end(self, lineno):
        base_indents = _get_line_indents(self.lines[lineno])
        for i in range(lineno + 1, len(self.lines)):
            if _get_line_indents(self.lines[i]) <= base_indents:
                return i - 1
        return lineno

    def _fix_incomplete_try_blocks(self, lineno, indents):
        block_start = lineno
        last_indents = indents
        while block_start > 0:
            block_start = (
                codeanalyze.get_block_start(ArrayLinesAdapter(self.lines), block_start)
                - 1
            )
            if self.lines[block_start].strip().startswith("try:"):
                indents = _get_line_indents(self.lines[block_start])
                if indents > last_indents:
                    continue
                last_indents = indents
                block_end = self._find_matching_deindent(block_start)
                line = self.lines[block_end].strip()
                if not (
                    line.startswith("finally:")
                    or line.startswith("except ")
                    or line.startswith("except:")
                ):
                    self._insert(block_end, " " * indents + "finally:")
                    self._insert(block_end + 1, " " * indents + "    pass")

    def _find_matching_deindent(self, line_number):
        indents = _get_line_indents(self.lines[line_number])
        current_line = line_number + 1
        while current_line < len(self.lines):
            line = self.lines[current_line]
            if not line.strip().startswith("#") and not line.strip() == "":
                # HACK: We should have used logical lines here
                if _get_line_indents(self.lines[current_line]) <= indents:
                    return current_line
            current_line += 1
        return len(self.lines) - 1

    def _set(self, lineno, line):
        self.diffs[self.origs[lineno]] += len(line) - len(self.lines[lineno])
        self.lines[lineno] = line

    def _insert(self, lineno, line):
        self.diffs[self.origs[lineno]] += len(line) + 1
        self.origs.insert(lineno, self.origs[lineno])
        self.lines.insert(lineno, line)


def _logical_start(lines, lineno, check_prev=False):
    logical_finder = LogicalLineFinder(ArrayLinesAdapter(lines))
    if check_prev:
        prev = lineno - 1
        while prev > 0:
            start, end = logical_finder.logical_line_in(prev)
            if end is None or start <= lineno < end:
                return start
            if start <= prev:
                break
            prev -= 1
    return logical_finder.logical_line_in(lineno)[0]


def _get_line_indents(line):
    return codeanalyze.count_line_indents(line)
