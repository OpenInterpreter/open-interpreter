from itertools import chain

from rope.base import ast


def find_visible(node, lines):
    """Return the line which is visible from all `lines`"""
    root = ast_suite_tree(node)
    return find_visible_for_suite(root, lines)


def find_visible_for_suite(root, lines):
    if len(lines) == 1:
        return lines[0]
    line1 = lines[0]
    line2 = find_visible_for_suite(root, lines[1:])
    suite1 = root.find_suite(line1)
    suite2 = root.find_suite(line2)

    def valid(suite):
        return suite is not None and not suite.ignored

    if valid(suite1) and not valid(suite2):
        return line1
    if not valid(suite1) and valid(suite2):
        return line2
    if not valid(suite1) and not valid(suite2):
        return None
    while suite1 != suite2 and suite1.parent != suite2.parent:
        if suite1._get_level() < suite2._get_level():
            line2 = suite2.get_start()
            suite2 = suite2.parent
        elif suite1._get_level() > suite2._get_level():
            line1 = suite1.get_start()
            suite1 = suite1.parent
        else:
            line1 = suite1.get_start()
            line2 = suite2.get_start()
            suite1 = suite1.parent
            suite2 = suite2.parent
    if suite1 == suite2:
        return min(line1, line2)
    return min(suite1.get_start(), suite2.get_start())


def ast_suite_tree(node):
    if hasattr(node, "lineno"):
        lineno = node.lineno
    else:
        lineno = 1
    return Suite(node.body, lineno)


class Suite:
    def __init__(self, child_nodes, lineno, parent=None, ignored=False):
        self.parent = parent
        self.lineno = lineno
        self.child_nodes = child_nodes
        self._children = None
        self.ignored = ignored

    def get_start(self):
        if self.parent is None:
            if self.child_nodes:
                return self.local_start()
            else:
                return 1
        return self.lineno

    def get_children(self):
        if self._children is None:
            walker = _SuiteWalker(self)
            for child in self.child_nodes:
                walker.visit(child)
            self._children = walker.suites
        return self._children

    def local_start(self):
        return self.child_nodes[0].lineno

    def local_end(self):
        end = self.child_nodes[-1].lineno
        if self.get_children():
            end = max(end, self.get_children()[-1].local_end())
        return end

    def find_suite(self, line):
        if line is None:
            return None
        for child in self.get_children():
            if child.local_start() <= line <= child.local_end():
                return child.find_suite(line)
        return self

    def _get_level(self):
        if self.parent is None:
            return 0
        return self.parent._get_level() + 1


class _SuiteWalker(ast.RopeNodeVisitor):
    def __init__(self, suite):
        self.suite = suite
        self.suites = []

    def _If(self, node):
        self._add_if_like_node(node)

    def _For(self, node):
        self._add_if_like_node(node)

    def _While(self, node):
        self._add_if_like_node(node)

    def _With(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite))

    def _AsyncWith(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite))

    def _Match(self, node):
        case_bodies = list(
            chain.from_iterable([[case.pattern] + case.body for case in node.cases])
        )
        self.suites.append(Suite(case_bodies, node.lineno, self.suite))

    def _TryFinally(self, node):
        proceed_to_except_handler = False
        if len(node.finalbody) == 1:
            try:
                proceed_to_except_handler = isinstance(
                    node.handlers[0], ast.ExceptHandler
                )
            except IndexError:
                pass
        if proceed_to_except_handler:
            self._TryExcept(node)
        else:
            self.suites.append(Suite(node.body, node.lineno, self.suite))
        self.suites.append(Suite(node.finalbody, node.lineno, self.suite))

    def _Try(self, node):
        if len(node.finalbody) == 1:
            self._TryFinally(node)
        else:
            self._TryExcept(node)

    def _TryExcept(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite))
        for handler in node.handlers:
            self.suites.append(Suite(handler.body, node.lineno, self.suite))
        if node.orelse:
            self.suites.append(Suite(node.orelse, node.lineno, self.suite))

    def _add_if_like_node(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite))
        if node.orelse:
            self.suites.append(Suite(node.orelse, node.lineno, self.suite))

    def _FunctionDef(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite, ignored=True))

    def _AsyncFunctionDef(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite, ignored=True))

    def _ClassDef(self, node):
        self.suites.append(Suite(node.body, node.lineno, self.suite, ignored=True))
