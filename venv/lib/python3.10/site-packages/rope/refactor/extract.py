import re
from contextlib import contextmanager
from itertools import chain

from rope.base import ast, codeanalyze
from rope.base.change import ChangeContents, ChangeSet
from rope.base.exceptions import RefactoringError
from rope.base.utils.datastructures import OrderedSet
from rope.refactor import patchedast, similarfinder, sourceutils, suites, usefunction


# Extract refactoring has lots of special cases.  I tried to split it
# to smaller parts to make it more manageable:
#
# _ExtractInfo: holds information about the refactoring; it is passed
# to the parts that need to have information about the refactoring
#
# _ExtractCollector: merely saves all of the information necessary for
# performing the refactoring.
#
# _DefinitionLocationFinder: finds where to insert the definition.
#
# _ExceptionalConditionChecker: checks for exceptional conditions in
# which the refactoring cannot be applied.
#
# _ExtractMethodParts: generates the pieces of code (like definition)
# needed for performing extract method.
#
# _ExtractVariableParts: like _ExtractMethodParts for variables.
#
# _ExtractPerformer: Uses above classes to collect refactoring
# changes.
#
# There are a few more helper functions and classes used by above
# classes.
class _ExtractRefactoring:

    kind_prefixes = {}

    def __init__(self, project, resource, start_offset, end_offset, variable=False):
        self.project = project
        self.resource = resource
        self.start_offset = self._fix_start(resource.read(), start_offset)
        self.end_offset = self._fix_end(resource.read(), end_offset)

    def _fix_start(self, source, offset):
        while offset < len(source) and source[offset].isspace():
            offset += 1
        return offset

    def _fix_end(self, source, offset):
        while offset > 0 and source[offset - 1].isspace():
            offset -= 1
        return offset

    def get_changes(self, extracted_name, similar=False, global_=False, kind=None):
        """Get the changes this refactoring makes

        :parameters:
            - `extracted_name`: target name, when starts with @ - set kind to
            classmethod, $ - staticmethod
            - `similar`: if `True`, similar expressions/statements are also
              replaced.
            - `global_`: if `True`, the extracted method/variable will
              be global.
            - `kind`: kind of target refactoring to (staticmethod, classmethod)

        """
        extracted_name, kind = self._get_kind_from_name(extracted_name, kind)

        info = _ExtractInfo(
            self.project,
            self.resource,
            self.start_offset,
            self.end_offset,
            extracted_name,
            variable=self._get_kind(kind) == "variable",
            similar=similar,
            make_global=global_,
        )
        info.kind = self._get_kind(kind)
        new_contents = _ExtractPerformer(info).extract()
        changes = ChangeSet(f"Extract {info.kind} <{extracted_name}>")
        changes.add_change(ChangeContents(self.resource, new_contents))
        return changes

    def _get_kind_from_name(self, extracted_name, kind):
        for sign, selected_kind in self.kind_prefixes.items():
            if extracted_name.startswith(sign):
                self._validate_kind_prefix(kind, selected_kind)
                return extracted_name[1:], selected_kind
        return extracted_name, kind

    @staticmethod
    def _validate_kind_prefix(kind, selected_kind):
        if kind and kind != selected_kind:
            raise RefactoringError("Kind and shortcut in name mismatch")

    @classmethod
    def _get_kind(cls, kind):
        raise NotImplementedError(f"You have to subclass {cls}")


class ExtractMethod(_ExtractRefactoring):
    kind = "method"
    allowed_kinds = ("function", "method", "staticmethod", "classmethod")
    kind_prefixes = {"@": "classmethod", "$": "staticmethod"}

    @classmethod
    def _get_kind(cls, kind):
        return kind if kind in cls.allowed_kinds else cls.kind


class ExtractVariable(_ExtractRefactoring):
    def __init__(self, *args, **kwds):
        kwds = dict(kwds)
        kwds["variable"] = True
        super().__init__(*args, **kwds)

    kind = "variable"

    def _get_kind(cls, kind):
        return cls.kind


class _ExtractInfo:
    """Holds information about the extract to be performed"""

    def __init__(
        self, project, resource, start, end, new_name, variable, similar, make_global
    ):
        self.project = project
        self.resource = resource
        self.pymodule = project.get_pymodule(resource)
        self.global_scope = self.pymodule.get_scope()
        self.source = self.pymodule.source_code
        self.lines = self.pymodule.lines
        self.new_name = new_name
        self.variable = variable
        self.similar = similar
        self._init_parts(start, end)
        self.kind = None
        self._init_scope()
        self.make_global = make_global

    def _init_parts(self, start, end):
        self.region = (
            self._choose_closest_line_end(start),
            self._choose_closest_line_end(end, end=True),
        )

        start = self.logical_lines.logical_line_in(
            self.lines.get_line_number(self.region[0])
        )[0]
        end = self.logical_lines.logical_line_in(
            self.lines.get_line_number(self.region[1])
        )[1]
        self.region_lines = (start, end)

        self.lines_region = (
            self.lines.get_line_start(self.region_lines[0]),
            self.lines.get_line_end(self.region_lines[1]),
        )

    @property
    def logical_lines(self):
        return self.pymodule.logical_lines

    def _init_scope(self):
        start_line = self.region_lines[0]
        scope = self.global_scope.get_inner_scope_for_line(start_line)
        if scope.get_kind() != "Module" and scope.get_start() == start_line:
            scope = scope.parent
        self.scope = scope
        self.scope_region = self._get_scope_region(self.scope)

    def _get_scope_region(self, scope):
        return (
            self.lines.get_line_start(scope.get_start()),
            self.lines.get_line_end(scope.get_end()) + 1,
        )

    def _choose_closest_line_end(self, offset, end=False):
        lineno = self.lines.get_line_number(offset)
        line_start = self.lines.get_line_start(lineno)
        line_end = self.lines.get_line_end(lineno)
        if self.source[line_start:offset].strip() == "":
            if end:
                return line_start - 1
            else:
                return line_start
        elif self.source[offset:line_end].strip() == "":
            return min(line_end, len(self.source))
        return offset

    @property
    def one_line(self):
        return self.region != self.lines_region and (
            self.logical_lines.logical_line_in(self.region_lines[0])
            == self.logical_lines.logical_line_in(self.region_lines[1])
        )

    @property
    def global_(self):
        return self.scope.parent is None

    @property
    def method(self):
        return self.scope.parent is not None and self.scope.parent.get_kind() == "Class"

    @property
    def indents(self):
        return sourceutils.get_indents(self.pymodule.lines, self.region_lines[0])

    @property
    def scope_indents(self):
        if self.global_:
            return 0
        return sourceutils.get_indents(self.pymodule.lines, self.scope.get_start())

    @property
    def extracted(self):
        return self.source[self.region[0] : self.region[1]]

    _cached_parsed_extracted = None

    @property
    def _parsed_extracted(self):
        if self._cached_parsed_extracted is None:
            self._cached_parsed_extracted = _parse_text(self.extracted)
        return self._cached_parsed_extracted

    _returned = None

    @property
    def returned(self):
        """Does the extracted piece contain return statement"""
        if self._returned is None:
            self._returned = usefunction._returns_last(self._parsed_extracted)
        return self._returned

    _returning_named_expr = None

    @property
    def returning_named_expr(self):
        """Does the extracted piece contains named expression/:= operator)"""
        if self._returning_named_expr is None:
            self._returning_named_expr = usefunction._namedexpr_last(
                self._parsed_extracted
            )
        return self._returning_named_expr

    _returning_generator = None

    @property
    def returning_generator_exp(self):
        """Does the extracted piece contains a generator expression"""
        if self._returning_generator is None:
            self._returning_generator = (
                isinstance(self._parsed_extracted, ast.Module)
                and isinstance(self._parsed_extracted.body[0], ast.Expr)
                and isinstance(self._parsed_extracted.body[0].value, ast.GeneratorExp)
            )

        return self._returning_generator


class _ExtractCollector:
    """Collects information needed for performing the extract"""

    def __init__(self, info):
        self.definition = None
        self.body_pattern = None
        self.checks = {}
        self.replacement_pattern = None
        self.matches = None
        self.replacements = None
        self.definition_location = None


class _ExtractPerformer:
    def __init__(self, info):
        self.info = info
        _ExceptionalConditionChecker()(self.info)

    def extract(self):
        extract_info = self._collect_info()
        content = codeanalyze.ChangeCollector(self.info.source)
        definition = extract_info.definition
        lineno, indents = extract_info.definition_location
        offset = self.info.lines.get_line_start(lineno)
        indented = sourceutils.fix_indentation(definition, indents)
        content.add_change(offset, offset, indented)
        self._replace_occurrences(content, extract_info)
        return content.get_changed()

    def _replace_occurrences(self, content, extract_info):
        for match in extract_info.matches:
            replacement = similarfinder.CodeTemplate(extract_info.replacement_pattern)
            mapping = {}
            for name in replacement.get_names():
                node = match.get_ast(name)
                if node:
                    start, end = patchedast.node_region(match.get_ast(name))
                    mapping[name] = self.info.source[start:end]
                else:
                    mapping[name] = name
            region = match.get_region()
            content.add_change(region[0], region[1], replacement.substitute(mapping))

    def _collect_info(self):
        extract_collector = _ExtractCollector(self.info)
        self._find_definition(extract_collector)
        self._find_matches(extract_collector)
        self._find_definition_location(extract_collector)
        return extract_collector

    def _find_matches(self, collector):
        regions = self._where_to_search()
        finder = similarfinder.SimilarFinder(self.info.pymodule)
        matches = []
        for start, end in regions:
            region_matches = finder.get_matches(
                collector.body_pattern, collector.checks, start, end
            )
            # Don't extract overlapping regions
            last_match_end = -1
            for region_match in region_matches:
                if self.info.one_line and self._is_assignment(region_match):
                    continue
                start, end = region_match.get_region()
                if last_match_end < start:
                    matches.append(region_match)
                    last_match_end = end
        collector.matches = matches

    @staticmethod
    def _is_assignment(region_match):
        return isinstance(
            region_match.ast, (ast.Attribute, ast.Subscript)
        ) and isinstance(region_match.ast.ctx, ast.Store)

    def _where_to_search(self):
        if self.info.similar:
            if self.info.make_global or self.info.global_:
                return [(0, len(self.info.pymodule.source_code))]
            if self.info.method and not self.info.variable:
                class_scope = self.info.scope.parent
                regions = []
                method_kind = _get_function_kind(self.info.scope)
                for scope in class_scope.get_scopes():
                    if (
                        method_kind == "method"
                        and _get_function_kind(scope) != "method"
                    ):
                        continue
                    start = self.info.lines.get_line_start(scope.get_start())
                    end = self.info.lines.get_line_end(scope.get_end())
                    regions.append((start, end))
                return regions
            else:
                if self.info.variable:
                    return [self.info.scope_region]
                else:
                    return [self.info._get_scope_region(self.info.scope.parent)]
        else:
            return [self.info.region]

    def _find_definition_location(self, collector):
        matched_lines = []
        for match in collector.matches:
            start = self.info.lines.get_line_number(match.get_region()[0])
            start_line = self.info.logical_lines.logical_line_in(start)[0]
            matched_lines.append(start_line)
        location_finder = _DefinitionLocationFinder(self.info, matched_lines)
        collector.definition_location = (
            location_finder.find_lineno(),
            location_finder.find_indents(),
        )

    def _find_definition(self, collector):
        if self.info.variable:
            parts = _ExtractVariableParts(self.info)
        else:
            parts = _ExtractMethodParts(self.info)
        collector.definition = parts.get_definition()
        collector.body_pattern = parts.get_body_pattern()
        collector.replacement_pattern = parts.get_replacement_pattern()
        collector.checks = parts.get_checks()


class _DefinitionLocationFinder:
    def __init__(self, info, matched_lines):
        self.info = info
        self.matched_lines = matched_lines
        # This only happens when subexpressions cannot be matched
        if not matched_lines:
            self.matched_lines.append(self.info.region_lines[0])

    def find_lineno(self):
        if self.info.variable and not self.info.make_global:
            return self._get_before_line()
        if self.info.global_:
            toplevel = self._find_toplevel(self.info.scope)
            ast = self.info.pymodule.get_ast()
            newlines = sorted(self.matched_lines + [toplevel.get_end() + 1])
            return suites.find_visible(ast, newlines)
        if self.info.make_global:
            toplevel = self._find_toplevel(self.info.scope)
            return toplevel.get_end() + 1
        return self._get_after_scope()

    def _find_toplevel(self, scope):
        toplevel = scope
        if toplevel.parent is not None:
            while toplevel.parent.parent is not None:
                toplevel = toplevel.parent
        return toplevel

    def find_indents(self):
        if self.info.variable and not self.info.make_global:
            return sourceutils.get_indents(self.info.lines, self._get_before_line())
        else:
            if self.info.global_ or self.info.make_global:
                return 0
        return self.info.scope_indents

    def _get_before_line(self):
        ast = self.info.scope.pyobject.get_ast()
        return suites.find_visible(ast, self.matched_lines)

    def _get_after_scope(self):
        return self.info.scope.get_end() + 1


class _ExceptionalConditionChecker:
    def __call__(self, info):
        self.base_conditions(info)
        if info.one_line:
            self.one_line_conditions(info)
        else:
            self.multi_line_conditions(info)

    def base_conditions(self, info):
        if info.region[1] > info.scope_region[1]:
            raise RefactoringError("Bad region selected for extract method")
        end_line = info.region_lines[1]
        end_scope = info.global_scope.get_inner_scope_for_line(end_line)
        if end_scope != info.scope and end_scope.get_end() != end_line:
            raise RefactoringError("Bad region selected for extract method")
        try:
            extracted = info.extracted
            if info.one_line:
                extracted = "(%s)" % extracted
            if _UnmatchedBreakOrContinueFinder.has_errors(extracted):
                raise RefactoringError(
                    "A break/continue without having a matching for/while loop."
                )
        except SyntaxError:
            raise RefactoringError(
                "Extracted piece should contain complete statements."
            )

    def one_line_conditions(self, info):
        if self._is_region_on_a_word(info):
            raise RefactoringError("Should extract complete statements.")
        if info.variable and not info.one_line:
            raise RefactoringError("Extract variable should not span multiple lines.")
        if usefunction._named_expr_count(
            info._parsed_extracted
        ) - usefunction._namedexpr_last(info._parsed_extracted):
            raise RefactoringError(
                "Extracted piece cannot contain named expression (:= operator)."
            )

    def multi_line_conditions(self, info):
        node = _parse_text(info.source[info.region[0] : info.region[1]])
        count = usefunction._return_count(node)
        extracted = info.extracted
        if count > 1:
            raise RefactoringError(
                "Extracted piece can have only one return statement."
            )
        if usefunction._yield_count(node):
            raise RefactoringError("Extracted piece cannot have yield statements.")
        if not hasattr(
            ast, "PyCF_ALLOW_TOP_LEVEL_AWAIT"
        ) and _AsyncStatementFinder.has_errors(extracted):
            raise RefactoringError(
                "Extracted piece can only have async/await "
                "statements if Rope is running on Python "
                "3.8 or higher"
            )
        if count == 1 and not usefunction._returns_last(node):
            raise RefactoringError("Return should be the last statement.")
        if info.region != info.lines_region:
            raise RefactoringError(
                "Extracted piece should contain complete statements."
            )

    def _is_region_on_a_word(self, info):
        if (
            info.region[0] > 0
            and self._is_on_a_word(info, info.region[0] - 1)
            or self._is_on_a_word(info, info.region[1] - 1)
        ):
            return True

    def _is_on_a_word(self, info, offset):
        prev = info.source[offset]
        if not (prev.isalnum() or prev == "_") or offset + 1 == len(info.source):
            return False
        next = info.source[offset + 1]
        return next.isalnum() or next == "_"


class _ExtractMethodParts(ast.RopeNodeVisitor):
    def __init__(self, info):
        self.info = info
        self.info_collector = self._create_info_collector()
        self.info.kind = self._get_kind_by_scope()
        self._check_constraints()

    def _get_kind_by_scope(self):
        if self._extacting_from_staticmethod():
            return "staticmethod"
        elif self._extracting_from_classmethod():
            return "classmethod"
        return self.info.kind

    def _check_constraints(self):
        if self._extracting_staticmethod() or self._extracting_classmethod():
            if not self.info.method:
                raise RefactoringError(
                    "Cannot extract to staticmethod/classmethod outside class"
                )

    def _extacting_from_staticmethod(self):
        return (
            self.info.method and _get_function_kind(self.info.scope) == "staticmethod"
        )

    def _extracting_from_classmethod(self):
        return self.info.method and _get_function_kind(self.info.scope) == "classmethod"

    def get_definition(self):
        if self.info.global_:
            return "\n%s\n" % self._get_function_definition()
        else:
            return "\n%s" % self._get_function_definition()

    def get_replacement_pattern(self):
        variables = []
        variables.extend(self._find_function_arguments())
        variables.extend(self._find_function_returns())
        return similarfinder.make_pattern(self._get_call(), variables)

    def get_body_pattern(self):
        variables = []
        variables.extend(self._find_function_arguments())
        variables.extend(self._find_function_returns())
        variables.extend(self._find_temps())
        return similarfinder.make_pattern(self._get_body(), variables)

    def _get_body(self):
        result = sourceutils.fix_indentation(self.info.extracted, 0)
        if self.info.one_line:
            result = "(%s)" % result
        return result

    def _find_temps(self):
        return usefunction.find_temps(self.info.project, self._get_body())

    def get_checks(self):
        if self.info.method and not self.info.make_global:
            if _get_function_kind(self.info.scope) == "method":
                class_name = similarfinder._pydefined_to_str(
                    self.info.scope.parent.pyobject
                )
                return {self._get_self_name(): "type=" + class_name}
        return {}

    def _create_info_collector(self):
        zero = self.info.scope.get_start() - 1
        start_line = self.info.region_lines[0] - zero
        end_line = self.info.region_lines[1] - zero
        info_collector = _FunctionInformationCollector(
            start_line, end_line, self.info.global_
        )
        body = self.info.source[self.info.scope_region[0] : self.info.scope_region[1]]
        node = _parse_text(body)
        info_collector.visit(node)
        return info_collector

    def _get_function_definition(self):
        args = self._find_function_arguments()
        returns = self._find_function_returns()

        result = []
        self._append_decorators(result)
        result.append("def %s:\n" % self._get_function_signature(args))
        unindented_body = self._get_unindented_function_body(returns)
        indents = sourceutils.get_indent(self.info.project)
        function_body = sourceutils.indent_lines(unindented_body, indents)
        result.append(function_body)
        definition = "".join(result)

        return definition + "\n"

    def _append_decorators(self, result):
        if self._extracting_staticmethod():
            result.append("@staticmethod\n")
        elif self._extracting_classmethod():
            result.append("@classmethod\n")

    def _extracting_classmethod(self):
        return self.info.kind == "classmethod"

    def _extracting_staticmethod(self):
        return self.info.kind == "staticmethod"

    def _get_function_signature(self, args):
        args = list(args)
        prefix = ""
        if self._extracting_method() or self._extracting_classmethod():
            self_name = self._get_self_name()
            if self_name is None:
                raise RefactoringError(
                    "Extracting a method from a function with no self argument."
                )
            if self_name in args:
                args.remove(self_name)
            args.insert(0, self_name)
        return prefix + self.info.new_name + "(%s)" % self._get_comma_form(args)

    def _extracting_method(self):
        return not self._extracting_staticmethod() and (
            self.info.method
            and not self.info.make_global
            and _get_function_kind(self.info.scope) == "method"
        )

    def _get_self_name(self):
        if self._extracting_classmethod():
            return "cls"
        return self._get_scope_self_name()

    def _get_scope_self_name(self):
        if self.info.scope.pyobject.get_kind() == "staticmethod":
            return
        param_names = self.info.scope.pyobject.get_param_names()
        if param_names:
            return param_names[0]

    def _get_function_call(self, args):
        return "{prefix}{name}({args})".format(
            prefix=self._get_function_call_prefix(args),
            name=self.info.new_name,
            args=self._get_comma_form(args),
        )

    def _get_function_call_prefix(self, args):
        prefix = ""
        if self.info.method and not self.info.make_global:
            if self._extracting_staticmethod() or self._extracting_classmethod():
                prefix = self.info.scope.parent.pyobject.get_name() + "."
            else:
                self_name = self._get_self_name()
                if self_name in args:
                    args.remove(self_name)
                prefix = self_name + "."
        return prefix

    def _get_comma_form(self, names):
        return ", ".join(names)

    def _get_call(self):
        args = self._find_function_arguments()
        returns = self._find_function_returns()
        call_prefix = ""
        if returns and (not self.info.one_line or self.info.returning_named_expr):
            assignment_operator = " := " if self.info.one_line else " = "
            call_prefix = self._get_comma_form(returns) + assignment_operator
        if self.info.returned:
            call_prefix = "return "
        return call_prefix + self._get_function_call(args)

    def _find_function_arguments(self):
        # if not make_global, do not pass any global names; they are
        # all visible.
        if self.info.global_ and not self.info.make_global:
            return list(
                self.info_collector.read
                & self.info_collector.postread
                & self.info_collector.written
            )
        if not self.info.one_line:
            result = self.info_collector.prewritten & self.info_collector.read
            result |= (
                self.info_collector.prewritten
                & self.info_collector.postread
                & (self.info_collector.maybe_written - self.info_collector.written)
            )
            return list(result)
        start = self.info.region[0]
        if start == self.info.lines_region[0]:
            start = start + re.search("\\S", self.info.extracted).start()
        function_definition = self.info.source[start : self.info.region[1]]
        read = _VariableReadsAndWritesFinder.find_reads_for_one_liners(
            function_definition
        )
        return list(self.info_collector.prewritten.intersection(read))

    def _find_function_returns(self):
        if self.info.one_line:
            written = self.info_collector.written | self.info_collector.maybe_written
            return list(written & self.info_collector.postread)

        if self.info.returned:
            return []
        written = self.info_collector.written | self.info_collector.maybe_written
        return list(written & self.info_collector.postread)

    def _get_unindented_function_body(self, returns):
        if self.info.one_line:
            return self._get_single_expression_function_body()
        return self._get_multiline_function_body(returns)

    def _get_multiline_function_body(self, returns):
        unindented_body = sourceutils.fix_indentation(self.info.extracted, 0)
        unindented_body = self._insert_globals(unindented_body)
        if returns:
            unindented_body += "\nreturn %s" % self._get_comma_form(returns)
        return unindented_body

    def _get_single_expression_function_body(self):
        extracted = _get_single_expression_body(self.info.extracted, info=self.info)
        body = "return " + extracted
        return self._insert_globals(body)

    def _insert_globals(self, unindented_body):
        globals_in_body = self._get_globals_in_body(unindented_body)
        globals_ = self.info_collector.globals_ & (
            self.info_collector.written | self.info_collector.maybe_written
        )
        globals_ = globals_ - globals_in_body

        if globals_:
            unindented_body = "global {}\n{}".format(
                ", ".join(globals_), unindented_body
            )
        return unindented_body

    @staticmethod
    def _get_globals_in_body(unindented_body):
        node = _parse_text(unindented_body)
        visitor = _GlobalFinder()
        visitor.visit(node)
        return visitor.globals_


class _ExtractVariableParts:
    def __init__(self, info):
        self.info = info

    def get_definition(self):
        extracted = _get_single_expression_body(self.info.extracted, info=self.info)
        return self.info.new_name + " = " + extracted + "\n"

    def get_body_pattern(self):
        return "(%s)" % self.info.extracted.strip()

    def get_replacement_pattern(self):
        return self.info.new_name

    def get_checks(self):
        return {}


class _FunctionInformationCollector(ast.RopeNodeVisitor):
    def __init__(self, start, end, is_global):
        self.start = start
        self.end = end
        self.is_global = is_global
        self.prewritten = OrderedSet()
        self.maybe_written = OrderedSet()
        self.written = OrderedSet()
        self.read = OrderedSet()
        self.postread = OrderedSet()
        self.postwritten = OrderedSet()
        self.host_function = True
        self.conditional = False
        self.globals_ = OrderedSet()
        self.surrounded_by_loop = 0
        self.loop_depth = 0

    def _read_variable(self, name, lineno):
        if self.start <= lineno <= self.end:
            if name not in self.written:
                if not self.conditional or name not in self.maybe_written:
                    self.read.add(name)
        if self.end < lineno:
            if name not in self.postwritten:
                self.postread.add(name)

    def _written_variable(self, name, lineno):
        if self.start <= lineno <= self.end:
            if self.conditional:
                self.maybe_written.add(name)
            else:
                self.written.add(name)
            if self.loop_depth > 0 and name in self.read:
                self.postread.add(name)
        if self.start > lineno:
            self.prewritten.add(name)
        if self.end < lineno:
            self.postwritten.add(name)

    def _FunctionDef(self, node):
        if not self.is_global and self.host_function:
            self.host_function = False
            for name in _get_argnames(node.args):
                self._written_variable(name, node.lineno)
            for child in node.body:
                self.visit(child)
        else:
            self._written_variable(node.name, node.lineno)
            visitor = _VariableReadsAndWritesFinder()
            for child in node.body:
                visitor.visit(child)
            for name in visitor.read - visitor.written:
                self._read_variable(name, node.lineno)

    def _Global(self, node):
        self.globals_.add(*node.names)

    def _AsyncFunctionDef(self, node):
        self._FunctionDef(node)

    def _Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.AugStore)):
            self._written_variable(node.id, node.lineno)
        if not isinstance(node.ctx, ast.Store):
            self._read_variable(node.id, node.lineno)

    def _MatchAs(self, node):
        self._written_variable(node.name, node.lineno)
        if node.pattern:
            self.visit(node.pattern)

    def _Assign(self, node):
        self.visit(node.value)
        for child in node.targets:
            self.visit(child)

    def _AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            target_id = node.target.id
            self._read_variable(target_id, node.target.lineno)
            self._written_variable(target_id, node.target.lineno)
        else:
            self.visit(node.target)

    def _ClassDef(self, node):
        self._written_variable(node.name, node.lineno)

    def _ListComp(self, node):
        self._comp_exp(node)

    def _GeneratorExp(self, node):
        self._comp_exp(node)

    def _SetComp(self, node):
        self._comp_exp(node)

    def _DictComp(self, node):
        self._comp_exp(node)

    def _comp_exp(self, node):
        read = OrderedSet(self.read)
        written = OrderedSet(self.written)
        maybe_written = OrderedSet(self.maybe_written)

        for child in ast.iter_child_nodes(node):
            self.visit(child)

        comp_names = list(
            chain.from_iterable(
                self._flatten_nested_tuple_of_names(generator.target)
                for generator in node.generators
            )
        )
        self.read = self.read - comp_names | read
        self.written = self.written - comp_names | written
        self.maybe_written = self.maybe_written - comp_names | maybe_written

    def _flatten_nested_tuple_of_names(self, node):
        if isinstance(node, ast.Tuple):
            for elt in node.elts:
                yield self._flatten_nested_tuple_of_names(elt)
        elif isinstance(node, ast.Name):
            yield node.id
        else:
            assert False, f"Unexpected node type in list comprehension target: {node!r}"

    def _If(self, node):
        self._handle_conditional_node(node)

    def _While(self, node):
        with self._handle_loop_context(node):
            self._handle_conditional_node(node)

    def _For(self, node):
        with self._handle_loop_context(node), self._handle_conditional_context(node):
            # iter has to be checked before the target variables
            self.visit(node.iter)
            self.visit(node.target)

            for child in node.body:
                self.visit(child)
            for child in node.orelse:
                self.visit(child)

    def _handle_conditional_node(self, node):
        with self._handle_conditional_context(node):
            for child in ast.iter_child_nodes(node):
                self.visit(child)

    @contextmanager
    def _handle_conditional_context(self, node):
        if self.start <= node.lineno <= self.end:
            self.conditional = True
        try:
            yield
        finally:
            self.conditional = False

    @contextmanager
    def _handle_loop_context(self, node):
        if node.lineno < self.start:
            self.loop_depth += 1
        try:
            yield
        finally:
            self.loop_depth -= 1


def _get_argnames(arguments):
    result = []
    result.extend(node.arg for node in getattr(arguments, "posonlyargs", []))
    result.extend(node.arg for node in arguments.args)
    if arguments.vararg:
        result.append(arguments.vararg.arg)
    if arguments.kwarg:
        result.append(arguments.kwarg.arg)
    result.extend(node.arg for node in arguments.kwonlyargs)
    return result


class _VariableReadsAndWritesFinder(ast.RopeNodeVisitor):
    def __init__(self):
        self.written = set()
        self.read = set()

    def _Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.AugStore)):
            self.written.add(node.id)
        if not isinstance(node, ast.Store):
            self.read.add(node.id)

    def _FunctionDef(self, node):
        self.written.add(node.name)
        visitor = _VariableReadsAndWritesFinder()
        for child in ast.iter_child_nodes(node):
            visitor.visit(child)
        self.read.update(visitor.read - visitor.written)

    def _Class(self, node):
        self.written.add(node.name)

    @staticmethod
    def find_reads_and_writes(code):
        if code.strip() == "":
            return set(), set()
        node = _parse_text(code)
        visitor = _VariableReadsAndWritesFinder()
        visitor.visit(node)
        return visitor.read, visitor.written

    @staticmethod
    def find_reads_for_one_liners(code):
        if code.strip() == "":
            return set(), set()
        node = _parse_text(code)
        visitor = _VariableReadsAndWritesFinder()
        visitor.visit(node)
        return visitor.read


class _BaseErrorFinder(ast.RopeNodeVisitor):
    @classmethod
    def has_errors(cls, code):
        if code.strip() == "":
            return False
        node = _parse_text(code)
        visitor = cls()
        visitor.visit(node)
        return visitor.error


class _UnmatchedBreakOrContinueFinder(_BaseErrorFinder):
    def __init__(self):
        self.error = False
        self.loop_count = 0

    def _For(self, node):
        self.loop_encountered(node)

    def _While(self, node):
        self.loop_encountered(node)

    def loop_encountered(self, node):
        self.loop_count += 1
        for child in node.body:
            self.visit(child)
        self.loop_count -= 1
        if node.orelse:
            if isinstance(node.orelse, (list, tuple)):
                for node_ in node.orelse:
                    self.visit(node_)
            else:
                self.visit(node.orelse)

    def _Break(self, node):
        self.check_loop()

    def _Continue(self, node):
        self.check_loop()

    def check_loop(self):
        if self.loop_count < 1:
            self.error = True

    def _FunctionDef(self, node):
        pass

    def _ClassDef(self, node):
        pass


class _AsyncStatementFinder(_BaseErrorFinder):
    def __init__(self):
        self.error = False

    def _AsyncFor(self, node):
        self.error = True

    def _AsyncWith(self, node):
        self.error = True

    def _FunctionDef(self, node):
        pass

    def _ClassDef(self, node):
        pass


class _GlobalFinder(ast.RopeNodeVisitor):
    def __init__(self):
        self.globals_ = OrderedSet()

    def _Global(self, node):
        self.globals_.add(*node.names)


def _get_function_kind(scope):
    return scope.pyobject.get_kind()


def _parse_text(body):
    body = sourceutils.fix_indentation(body, 0)
    try:
        node = ast.parse(body)
    except SyntaxError:
        # needed to parse expression containing := operator
        try:
            node = ast.parse("(" + body + ")")
        except SyntaxError:
            node = ast.parse(
                "async def __rope_placeholder__():\n"
                + sourceutils.fix_indentation(body, 4)
            )
            node.body = node.body[0].body
    return node


def _join_lines(code):
    lines = []
    for line in code.splitlines():
        if line.endswith("\\"):
            lines.append(line[:-1].strip())
        else:
            lines.append(line.strip())
    return " ".join(lines)


def _get_single_expression_body(extracted, info):
    extracted = sourceutils.fix_indentation(extracted, 0)
    already_parenthesized = (
        extracted.lstrip()[0] in "({[" and extracted.rstrip()[-1] in ")}]"
    )
    large_multiline = extracted.count("\n") >= 2 and already_parenthesized
    if not large_multiline:
        extracted = _join_lines(extracted)
    multiline_expression = "\n" in extracted
    if (
        info.returning_named_expr
        or info.returning_generator_exp
        or (multiline_expression and not large_multiline)
    ):
        extracted = "(" + extracted + ")"
    return extracted
