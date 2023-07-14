import rope.base.builtins  # Use full qualification for clarity.
from rope.base import ast, codeanalyze, exceptions, pynames, utils
from rope.refactor import patchedast


class Scope:
    def __init__(self, pycore, pyobject, parent_scope):
        self.pycore = pycore
        self.pyobject = pyobject
        self.parent = parent_scope

    def get_names(self):
        """Return the names defined or imported in this scope"""
        return self.pyobject.get_attributes()

    def get_defined_names(self):
        """Return the names defined in this scope"""
        return self.pyobject._get_structural_attributes()

    def get_name(self, name):
        """Return name `PyName` defined in this scope"""
        if name not in self.get_names():
            raise exceptions.NameNotFoundError("name %s not found" % name)
        return self.get_names()[name]

    def __getitem__(self, key):
        """The same as ``get_name(key)``"""
        return self.get_name(key)

    def __contains__(self, key):
        """The same as ``key in self.get_names()``"""
        return key in self.get_names()

    @utils.saveit
    def get_scopes(self):
        """Return the subscopes of this scope

        The returned scopes should be sorted by the order they appear.
        """
        return self._create_scopes()

    def lookup(self, name):
        if name in self.get_names():
            return self.get_names()[name]
        if self.parent is not None:
            return self.parent._propagated_lookup(name)
        return None

    def get_propagated_names(self):
        """Return the visible names of this scope

        Return the names defined in this scope that are visible from
        scopes containing this scope.  This method returns the same
        dictionary returned by `get_names()` except for `ClassScope`
        which returns an empty dict.
        """
        return self.get_names()

    def _propagated_lookup(self, name):
        if name in self.get_propagated_names():
            return self.get_propagated_names()[name]
        if self.parent is not None:
            return self.parent._propagated_lookup(name)
        return None

    def _create_scopes(self):
        return [
            pydefined.get_scope() for pydefined in self.pyobject._get_defined_objects()
        ]

    def _get_global_scope(self):
        current = self
        while current.parent is not None:
            current = current.parent
        return current

    def get_start(self):
        return self.pyobject.get_ast().lineno

    def get_body_start(self):
        body = self.pyobject.get_ast().body
        if body:
            return body[0].lineno
        return self.get_start()

    def get_end(self):
        pymodule = self._get_global_scope().pyobject
        return pymodule.logical_lines.logical_line_in(self.logical_end)[1]

    @utils.saveit
    def get_logical_end(self):
        global_scope = self._get_global_scope()
        return global_scope._scope_finder.find_scope_end(self)

    start = property(get_start)
    end = property(get_end)
    logical_end = property(get_logical_end)

    def get_kind(self):
        pass

    def get_region(self):
        self._calculate_scope_regions_for_module()
        node = self.pyobject.get_ast()
        region = patchedast.node_region(node)
        return region

    def _calculate_scope_regions_for_module(self):
        self._get_global_scope()._calculate_scope_regions()

    def in_region(self, offset):
        """Checks if offset is in scope region"""

        region = self.get_region()
        return region[0] < offset < region[1]


class GlobalScope(Scope):
    def __init__(self, pycore, module):
        super().__init__(pycore, module, None)
        self.names = module._get_concluded_data()

    def get_start(self):
        return 1

    def get_kind(self):
        return "Module"

    def get_name(self, name):
        try:
            return self.pyobject[name]
        except exceptions.AttributeNotFoundError:
            if name in self.builtin_names:
                return self.builtin_names[name]
            raise exceptions.NameNotFoundError("name %s not found" % name)

    @utils.saveit
    def _calculate_scope_regions(self):
        source = self._get_source()
        patchedast.patch_ast(self.pyobject.get_ast(), source)

    def _get_source(self):
        return self.pyobject.source_code

    def get_names(self):
        if self.names.get() is None:
            result = dict(self.builtin_names)
            result.update(super().get_names())
            self.names.set(result)
        return self.names.get()

    def get_inner_scope_for_line(self, lineno, indents=None):
        return self._scope_finder.get_holding_scope(self, lineno, indents)

    def get_inner_scope_for_offset(self, offset):
        return self._scope_finder.get_holding_scope_for_offset(self, offset)

    @property
    @utils.saveit
    def _scope_finder(self):
        return _HoldingScopeFinder(self.pyobject)

    @property
    def builtin_names(self):
        return rope.base.builtins.builtins.get_attributes()


class ComprehensionScope(Scope):
    def __init__(self, pycore, pyobject, visitor):
        super().__init__(pycore, pyobject, pyobject.parent.get_scope())
        self.names = None
        self.returned_asts = None
        self.defineds = None
        self.visitor = visitor

    def _get_names(self):
        if self.names is None:
            self._visit_comprehension()
        return self.names

    def get_names(self):
        return self._get_names()

    def _visit_comprehension(self):
        if self.names is None:
            new_visitor = self.visitor(self.pycore, self.pyobject)
            for node in ast.iter_child_nodes(self.pyobject.get_ast()):
                new_visitor.visit(node)
            self.names = dict(self.parent.get_names())
            self.names.update(new_visitor.names)
            self.defineds = new_visitor.defineds

    def get_logical_end(self):
        return self.get_start()

    logical_end = property(get_logical_end)

    def get_body_start(self):
        return self.get_start()


class FunctionScope(Scope):
    def __init__(self, pycore, pyobject, visitor):
        super().__init__(pycore, pyobject, pyobject.parent.get_scope())
        self.names = None
        self.returned_asts = None
        self.is_generator = None
        self.defineds = None
        self.visitor = visitor

    def _get_names(self):
        if self.names is None:
            self._visit_function()
        return self.names

    def _visit_function(self):
        if self.names is None:
            new_visitor = self.visitor(self.pycore, self.pyobject)
            for n in ast.iter_child_nodes(self.pyobject.get_ast()):
                new_visitor.visit(n)
            self.names = new_visitor.names
            self.names.update(self.pyobject.get_parameters())
            self.returned_asts = new_visitor.returned_asts
            self.is_generator = new_visitor.generator
            self.defineds = new_visitor.defineds

    def _get_returned_asts(self):
        if self.names is None:
            self._visit_function()
        return self.returned_asts

    def _is_generator(self):
        if self.is_generator is None:
            self._get_returned_asts()
        return self.is_generator

    def get_names(self):
        return self._get_names()

    def _create_scopes(self):
        if self.defineds is None:
            self._visit_function()
        return [pydefined.get_scope() for pydefined in self.defineds]

    def get_kind(self):
        return "Function"

    def invalidate_data(self):
        for pyname in self.get_names().values():
            if isinstance(pyname, (pynames.AssignedName, pynames.EvaluatedName)):
                pyname.invalidate()


class ClassScope(Scope):
    def __init__(self, pycore, pyobject):
        super().__init__(pycore, pyobject, pyobject.parent.get_scope())

    def get_kind(self):
        return "Class"

    def get_propagated_names(self):
        return {}


class _HoldingScopeFinder:
    def __init__(self, pymodule):
        self.pymodule = pymodule

    def get_indents(self, lineno):
        return codeanalyze.count_line_indents(self.lines.get_line(lineno))

    def _get_scope_indents(self, scope):
        return self.get_indents(scope.get_start())

    def get_holding_scope(self, module_scope, lineno, line_indents=None):
        if line_indents is None:
            line_indents = self.get_indents(lineno)
        current_scope = module_scope
        new_scope = current_scope
        while new_scope is not None and (
            new_scope.get_kind() == "Module"
            or self._get_scope_indents(new_scope) <= line_indents
        ):
            current_scope = new_scope
            if (
                current_scope.get_start() == lineno
                and current_scope.get_kind() != "Module"
            ):
                return current_scope
            new_scope = None
            for scope in current_scope.get_scopes():
                if scope.get_start() <= lineno:
                    if lineno <= scope.get_end():
                        new_scope = scope
                        break
                else:
                    break
        return current_scope

    def _is_empty_line(self, lineno):
        line = self.lines.get_line(lineno)
        return line.strip() == "" or line.lstrip().startswith("#")

    def _get_body_indents(self, scope):
        return self.get_indents(scope.get_body_start())

    @staticmethod
    def get_holding_scope_for_offset(scope, offset):
        for inner_scope in scope.get_scopes():
            if inner_scope.in_region(offset):
                return _HoldingScopeFinder.get_holding_scope_for_offset(
                    inner_scope, offset
                )
        return scope

    def find_scope_end(self, scope):
        if not scope.parent:
            return self.lines.length()
        end = scope.pyobject.get_ast().body[-1].lineno
        scope_start = self.pymodule.logical_lines.logical_line_in(scope.start)
        if scope_start[1] >= end:
            # handling one-liners
            body_indents = self._get_scope_indents(scope) + 4
        else:
            body_indents = self._get_body_indents(scope)
        for line_start in self.logical_lines.generate_starts(
            min(end + 1, self.lines.length()), self.lines.length() + 1
        ):
            if not self._is_empty_line(line_start):
                if self.get_indents(line_start) < body_indents:
                    return end
                else:
                    end = line_start
        return end

    @property
    def lines(self):
        return self.pymodule.lines

    @property
    def code(self):
        return self.pymodule.source_code

    @property
    def logical_lines(self):
        return self.pymodule.logical_lines


class TemporaryScope(Scope):
    """Currently used for list comprehensions and generator expressions

    These scopes do not appear in the `get_scopes()` method of their
    parent scopes.
    """

    def __init__(self, pycore, parent_scope, names):
        super().__init__(pycore, parent_scope.pyobject, parent_scope)
        self.names = names

    def get_names(self):
        return self.names

    def get_defined_names(self):
        return self.names

    def _create_scopes(self):
        return []

    def get_kind(self):
        return "Temporary"
