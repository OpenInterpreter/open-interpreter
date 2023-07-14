"""Finding bad name and attribute accesses

`find_errors` function can be used to find possible bad name and
attribute accesses.  As an example::

  errors = find_errors(project, project.get_resource('mod.py'))
  for error in errors:
      print('%s: %s' % (error.lineno, error.error))

prints possible errors for ``mod.py`` file.

TODO:

* use task handles
* reporting names at most once
* attributes of extension modules that don't appear in
  extension_modules project config can be ignored
* not calling `PyScope.get_inner_scope_for_line()` if it is a
  bottleneck; needs profiling
* not reporting occurrences where rope cannot infer the object
* rope saves multiple objects for some of the names in its objectdb
  use all of them not to give false positives
* ... ;-)

"""
from rope.base import ast, evaluate, pyobjects


def find_errors(project, resource):
    """Find possible bad name and attribute accesses

    It returns a list of `Error`.
    """
    pymodule = project.get_pymodule(resource)
    finder = _BadAccessFinder(pymodule)
    finder.visit(pymodule.get_ast())
    return finder.errors


class _BadAccessFinder(ast.RopeNodeVisitor):
    def __init__(self, pymodule):
        self.pymodule = pymodule
        self.scope = pymodule.get_scope()
        self.errors = []

    def _Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            return
        scope = self.scope.get_inner_scope_for_line(node.lineno)
        pyname = scope.lookup(node.id)
        if pyname is None:
            self._add_error(node, "Unresolved variable")
        elif self._is_defined_after(scope, pyname, node.lineno):
            self._add_error(node, "Defined later")

    def _Attribute(self, node):
        if not isinstance(node.ctx, ast.Store):
            scope = self.scope.get_inner_scope_for_line(node.lineno)
            pyname = evaluate.eval_node(scope, node.value)
            if pyname is not None and pyname.get_object() != pyobjects.get_unknown():
                if node.attr not in pyname.get_object():
                    self._add_error(node, "Unresolved attribute")
        self.visit(node.value)

    def _add_error(self, node, msg):
        if isinstance(node, ast.Attribute):
            name = node.attr
        else:
            name = node.id
        if name != "None":
            error = Error(node.lineno, msg + " " + name)
            self.errors.append(error)

    def _is_defined_after(self, scope, pyname, lineno):
        location = pyname.get_definition_location()
        if location is not None and location[1] is not None:
            if (
                location[0] == self.pymodule
                and lineno <= location[1] <= scope.get_end()
            ):
                return True


class Error:
    def __init__(self, lineno, error):
        self.lineno = lineno
        self.error = error

    def __str__(self):
        return f"{self.lineno}: {self.error}"
