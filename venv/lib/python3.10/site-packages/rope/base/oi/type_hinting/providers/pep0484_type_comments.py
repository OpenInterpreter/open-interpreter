import re

from rope.base.oi.type_hinting import utils
from rope.base.oi.type_hinting.providers import interfaces


class AssignmentProvider(interfaces.IAssignmentProvider):
    def __init__(self, resolver):
        """
        :type resolver: rope.base.oi.type_hinting.resolvers.interfaces.IResolver
        """
        self._resolve = resolver

    PEP0484_TYPE_COMMENT_PATTERNS = (re.compile(r"type:\s*([^\n]+)"),)

    def __call__(self, pyname):
        """
        :type pyname: rope.base.pynamesdef.AssignedName
        :rtype: rope.base.pyobjects.PyDefinedObject | rope.base.pyobjects.PyObject or None
        """
        from rope.base.oi.soi import _get_lineno_for_node

        lineno = _get_lineno_for_node(pyname.assignments[0].ast_node)
        holding_scope = pyname.module.get_scope().get_inner_scope_for_line(lineno)
        line = holding_scope._get_global_scope()._scope_finder.lines.get_line(lineno)
        if "#" in line:
            type_strs = self._search_type_in_type_comment(line.split("#", 1)[1])
            if type_strs:
                return self._resolve(type_strs[0], holding_scope.pyobject)

    def _search_type_in_type_comment(self, code):
        """For more info see:
        https://www.python.org/dev/peps/pep-0484/#type-comments

        >>> AssignmentProvider()._search_type_in_type_comment('type: int')
        ['int']
        """
        for p in self.PEP0484_TYPE_COMMENT_PATTERNS:
            match = p.search(code)
            if match:
                return [match.group(1)]
