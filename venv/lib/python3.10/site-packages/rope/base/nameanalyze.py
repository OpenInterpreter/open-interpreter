from rope.base import ast


def get_name_levels(node):
    """Return a list of ``(name, level)`` tuples for assigned names

    The `level` is `None` for simple assignments and is a list of
    numbers for tuple assignments for example in::

      a, (b, c) = x

    The levels for for `a` is ``[0]``, for `b` is ``[1, 0]`` and for
    `c` is ``[1, 1]``.

    """
    visitor = _NodeNameCollector()
    visitor.visit(node)
    return visitor.names


class _NodeNameCollector(ast.RopeNodeVisitor):
    def __init__(self, levels=None):
        self.names = []
        self.levels = levels
        self.index = 0

    def _add_node(self, node):
        new_levels = []
        if self.levels is not None:
            new_levels = list(self.levels)
            new_levels.append(self.index)
        self.index += 1
        self._added(node, new_levels)

    def _added(self, node, levels):
        if hasattr(node, "id"):
            self.names.append((node.id, levels))

    def _Name(self, node):
        self._add_node(node)

    def _ExceptHandler(self, node):
        self.names.append((node.name, []))

    def _Tuple(self, node):
        new_levels = []
        if self.levels is not None:
            new_levels = list(self.levels)
            new_levels.append(self.index)
        self.index += 1
        visitor = _NodeNameCollector(new_levels)
        for child in ast.iter_child_nodes(node):
            visitor.visit(child)
        self.names.extend(visitor.names)

    def _Subscript(self, node):
        self._add_node(node)

    def _Attribute(self, node):
        self._add_node(node)

    def _Slice(self, node):
        self._add_node(node)
