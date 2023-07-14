"""This module can be used for finding similar code"""
import re

import rope.base.builtins  # Use full qualification for clarity.
import rope.refactor.wildcards  # Use full qualification for clarity.
from rope.base import ast, codeanalyze, exceptions, libutils
from rope.refactor import patchedast
from rope.refactor.patchedast import MismatchedTokenError


class BadNameInCheckError(exceptions.RefactoringError):
    pass


class SimilarFinder:
    """`SimilarFinder` can be used to find similar pieces of code

    See the notes in the `rope.refactor.restructure` module for more
    info.

    """

    def __init__(self, pymodule, wildcards=None):
        """Construct a SimilarFinder"""
        self.source = pymodule.source_code
        try:
            self.raw_finder = RawSimilarFinder(
                pymodule.source_code, pymodule.get_ast(), self._does_match
            )
        except MismatchedTokenError:
            print("in file %s" % pymodule.resource.path)
            raise
        self.pymodule = pymodule
        if wildcards is None:
            self.wildcards = {}
            for wildcard in [
                rope.refactor.wildcards.DefaultWildcard(pymodule.pycore.project)
            ]:
                self.wildcards[wildcard.get_name()] = wildcard
        else:
            self.wildcards = wildcards

    def get_matches(self, code, args=None, start=0, end=None):
        if args is None:
            args = {}
        self.args = args
        if end is None:
            end = len(self.source)
        skip_region = None
        if "skip" in args.get("", {}):
            resource, region = args[""]["skip"]
            if resource == self.pymodule.get_resource():
                skip_region = region
        return self.raw_finder.get_matches(code, start=start, end=end, skip=skip_region)

    def get_match_regions(self, *args, **kwds):
        for match in self.get_matches(*args, **kwds):
            yield match.get_region()

    def _does_match(self, node, name):
        arg = self.args.get(name, "")
        kind = "default"
        if isinstance(arg, (tuple, list)):
            kind = arg[0]
            arg = arg[1]
        suspect = rope.refactor.wildcards.Suspect(self.pymodule, node, name)
        return self.wildcards[kind].matches(suspect, arg)


class RawSimilarFinder:
    """A class for finding similar expressions and statements"""

    def __init__(self, source, node=None, does_match=None):
        if node is None:
            try:
                node = ast.parse(source)
            except SyntaxError:
                # needed to parse expression containing := operator
                node = ast.parse("(" + source + ")")
        if does_match is None:
            self.does_match = self._simple_does_match
        else:
            self.does_match = does_match
        self._init_using_ast(node, source)

    def _simple_does_match(self, node, name):
        return isinstance(node, (ast.expr, ast.Name))

    def _init_using_ast(self, node, source):
        self.source = source
        self._matched_asts = {}
        if not hasattr(node, "region"):
            patchedast.patch_ast(node, source)
        self.ast = node

    def get_matches(self, code, start=0, end=None, skip=None):
        """Search for `code` in source and return a list of `Match`-es

        `code` can contain wildcards.  ``${name}`` matches normal
        names and ``${?name} can match any expression.  You can use
        `Match.get_ast()` for getting the node that has matched a
        given pattern.

        """
        if end is None:
            end = len(self.source)
        for match in self._get_matched_asts(code):
            match_start, match_end = match.get_region()
            if start <= match_start and match_end <= end:
                if skip is not None and (skip[0] < match_end and skip[1] > match_start):
                    continue
                yield match

    def _get_matched_asts(self, code):
        if code not in self._matched_asts:
            wanted = self._create_pattern(code)
            matches = _ASTMatcher(self.ast, wanted, self.does_match).find_matches()
            self._matched_asts[code] = matches
        return self._matched_asts[code]

    def _create_pattern(self, expression):
        expression = self._replace_wildcards(expression)
        node = ast.parse(expression)
        # Getting Module.Stmt.nodes
        nodes = node.body
        if len(nodes) == 1 and isinstance(nodes[0], ast.Expr):
            # Getting Discard.expr
            wanted = nodes[0].value
        else:
            wanted = nodes
        return wanted

    def _replace_wildcards(self, expression):
        ropevar = _RopeVariable()
        template = CodeTemplate(expression)
        mapping = {name: ropevar.get_var(name) for name in template.get_names()}
        return template.substitute(mapping)


class _ASTMatcher:
    def __init__(self, body, pattern, does_match):
        """Searches the given pattern in the body AST.

        body is an AST node and pattern can be either an AST node or
        a list of ASTs nodes
        """
        self.body = body
        self.pattern = pattern
        self.matches = None
        self.ropevar = _RopeVariable()
        self.matches_callback = does_match

    def find_matches(self):
        if self.matches is None:
            self.matches = []
            # _check_nodes always returns None, so
            # call_for_nodes traverses self.body's entire tree.
            ast.call_for_nodes(self.body, self._check_node)
        return self.matches

    def _check_node(self, node):
        if isinstance(self.pattern, list):
            self._check_statements(node)
        else:
            self._check_expression(node)

    def _check_expression(self, node):
        mapping = {}
        if self._match_nodes(self.pattern, node, mapping):
            self.matches.append(ExpressionMatch(node, mapping))

    def _check_statements(self, node):
        for field, child in ast.iter_fields(node):
            if isinstance(child, (list, tuple)):
                self.__check_stmt_list(child)

    def __check_stmt_list(self, nodes):
        for index in range(len(nodes)):
            if len(nodes) - index >= len(self.pattern):
                current_stmts = nodes[index : index + len(self.pattern)]
                mapping = {}
                if self._match_stmts(current_stmts, mapping):
                    self.matches.append(StatementMatch(current_stmts, mapping))

    def _match_nodes(self, expected, node, mapping):
        if isinstance(expected, ast.Name):
            if self.ropevar.is_var(expected.id):
                return self._match_wildcard(expected, node, mapping)
        if not isinstance(expected, ast.AST):
            return expected == node
        if expected.__class__ != node.__class__:
            return False

        children1 = self._get_children(expected)
        children2 = self._get_children(node)
        if len(children1) != len(children2):
            return False
        for child1, child2 in zip(children1, children2):
            if isinstance(child1, ast.AST):
                if not self._match_nodes(child1, child2, mapping):
                    return False
            elif isinstance(child1, (list, tuple)):
                if not isinstance(child2, (list, tuple)) or len(child1) != len(child2):
                    return False
                for c1, c2 in zip(child1, child2):
                    if not self._match_nodes(c1, c2, mapping):
                        return False
            else:
                if type(child1) is not type(child2) or child1 != child2:
                    return False
        return True

    def _get_children(self, node):
        """Return not `ast.expr_context` children of `node`"""
        return [
            child
            for field, child in ast.iter_fields(node)
            if not isinstance(child, ast.expr_context)
        ]

    def _match_stmts(self, current_stmts, mapping):
        if len(current_stmts) != len(self.pattern):
            return False
        for stmt, expected in zip(current_stmts, self.pattern):
            if not self._match_nodes(expected, stmt, mapping):
                return False
        return True

    def _match_wildcard(self, node1, node2, mapping):
        name = self.ropevar.get_base(node1.id)
        if name not in mapping:
            if self.matches_callback(node2, name):
                mapping[name] = node2
                return True
            return False
        else:
            return self._match_nodes(mapping[name], node2, {})


class Match:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_region(self):
        """Returns match region"""

    def get_ast(self, name):
        """Return the ast node that has matched rope variables"""
        return self.mapping.get(name, None)


class ExpressionMatch(Match):
    def __init__(self, ast, mapping):
        super().__init__(mapping)
        self.ast = ast

    def get_region(self):
        return self.ast.region


class StatementMatch(Match):
    def __init__(self, ast_list, mapping):
        super().__init__(mapping)
        self.ast_list = ast_list

    def get_region(self):
        return self.ast_list[0].region[0], self.ast_list[-1].region[1]


class CodeTemplate:
    def __init__(self, template):
        self.template = template
        self._find_names()

    def _find_names(self):
        self.names = {}
        for match in CodeTemplate._get_pattern().finditer(self.template):
            if "name" in match.groupdict() and match.group("name") is not None:
                start, end = match.span("name")
                name = self.template[start + 2 : end - 1]
                if name not in self.names:
                    self.names[name] = []
                self.names[name].append((start, end))

    def get_names(self):
        return self.names.keys()

    def substitute(self, mapping):
        collector = codeanalyze.ChangeCollector(self.template)
        for name, occurrences in self.names.items():
            for region in occurrences:
                collector.add_change(region[0], region[1], mapping[name])
        result = collector.get_changed()
        if result is None:
            return self.template
        return result

    _match_pattern = None

    @classmethod
    def _get_pattern(cls):
        if cls._match_pattern is None:
            pattern = (
                codeanalyze.get_comment_pattern()
                + "|"
                + codeanalyze.get_string_pattern()
                + "|"
                + r"(?P<name>\$\{[^\s\$\}]*\})"
            )
            cls._match_pattern = re.compile(pattern)
        return cls._match_pattern


class _RopeVariable:
    """Transform and identify rope inserted wildcards"""

    _normal_prefix = "__rope__variable_normal_"
    _any_prefix = "__rope__variable_any_"

    def get_var(self, name):
        if name.startswith("?"):
            return self._get_any(name)
        else:
            return self._get_normal(name)

    def is_var(self, name):
        return self._is_normal(name) or self._is_var(name)

    def get_base(self, name):
        if self._is_normal(name):
            return name[len(self._normal_prefix) :]
        if self._is_var(name):
            return "?" + name[len(self._any_prefix) :]

    def _get_normal(self, name):
        return self._normal_prefix + name

    def _get_any(self, name):
        return self._any_prefix + name[1:]

    def _is_normal(self, name):
        return name.startswith(self._normal_prefix)

    def _is_var(self, name):
        return name.startswith(self._any_prefix)


def make_pattern(code, variables):
    variables = set(variables)
    collector = codeanalyze.ChangeCollector(code)

    def does_match(node, name):
        return isinstance(node, ast.Name) and node.id == name

    finder = RawSimilarFinder(code, does_match=does_match)
    for variable in variables:
        for match in finder.get_matches("${%s}" % variable):
            start, end = match.get_region()
            collector.add_change(start, end, "${%s}" % variable)
    result = collector.get_changed()
    return result if result is not None else code


def _pydefined_to_str(pydefined):
    address = []
    if isinstance(
        pydefined, (rope.base.builtins.BuiltinClass, rope.base.builtins.BuiltinFunction)
    ):
        return f"__builtins__.{pydefined.get_name()}"
    while pydefined.parent is not None:
        address.insert(0, pydefined.get_name())
        pydefined = pydefined.parent
    module_name = libutils.modname(pydefined.resource)
    return ".".join(module_name.split(".") + address)
