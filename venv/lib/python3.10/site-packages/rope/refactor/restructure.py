import warnings

from rope.base import ast, builtins, change, codeanalyze, libutils, taskhandle
from rope.refactor import patchedast, similarfinder, sourceutils
from rope.refactor.importutils import module_imports


class Restructure:
    """A class to perform python restructurings

    A restructuring transforms pieces of code matching `pattern` to
    `goal`.  In the `pattern` wildcards can appear.  Wildcards match
    some piece of code based on their kind and arguments that are
    passed to them through `args`.

    `args` is a dictionary of wildcard names to wildcard arguments.
    If the argument is a tuple, the first item of the tuple is
    considered to be the name of the wildcard to use; otherwise the
    "default" wildcard is used.  For getting the list arguments a
    wildcard supports, see the pydoc of the wildcard.  (see
    `rope.refactor.wildcard.DefaultWildcard` for the default
    wildcard.)

    `wildcards` is the list of wildcard types that can appear in
    `pattern`.  See `rope.refactor.wildcards`.  If a wildcard does not
    specify its kind (by using a tuple in args), the wildcard named
    "default" is used.  So there should be a wildcard with "default"
    name in `wildcards`.

    `imports` is the list of imports that changed modules should
    import.  Note that rope handles duplicate imports and does not add
    the import if it already appears.

    Example #1::

      pattern ${pyobject}.get_attribute(${name})
      goal ${pyobject}[${name}]
      args pyobject: instance=rope.base.pyobjects.PyObject

    Example #2::

      pattern ${name} in ${pyobject}.get_attributes()
      goal ${name} in {pyobject}
      args pyobject: instance=rope.base.pyobjects.PyObject

    Example #3::

      pattern ${pycore}.create_module(${project}.root, ${name})
      goal generate.create_module(${project}, ${name})

      imports
       from rope.contrib import generate

      args
       project: type=rope.base.project.Project

    Example #4::

      pattern ${pow}(${param1}, ${param2})
      goal ${param1} ** ${param2}
      args pow: name=mod.pow, exact

    Example #5::

      pattern ${inst}.longtask(${p1}, ${p2})
      goal
       ${inst}.subtask1(${p1})
       ${inst}.subtask2(${p2})
      args
       inst: type=mod.A,unsure

    """

    def __init__(self, project, pattern, goal, args=None, imports=None, wildcards=None):
        """Construct a restructuring

        See class pydoc for more info about the arguments.

        """
        self.project = project
        self.pattern = pattern
        self.goal = goal
        self.args = args
        if self.args is None:
            self.args = {}
        self.imports = imports
        if self.imports is None:
            self.imports = []
        self.wildcards = wildcards
        self.template = similarfinder.CodeTemplate(self.goal)

    def get_changes(
        self,
        checks=None,
        imports=None,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get the changes needed by this restructuring

        `resources` can be a list of `rope.base.resources.File` to
        apply the restructuring on.  If `None`, the restructuring will
        be applied to all python files.

        `checks` argument has been deprecated.  Use the `args` argument
        of the constructor.  The usage of::

          strchecks = {'obj1.type': 'mod.A', 'obj2': 'mod.B',
                       'obj3.object': 'mod.C'}
          checks = restructuring.make_checks(strchecks)

        can be replaced with::

          args = {'obj1': 'type=mod.A', 'obj2': 'name=mod.B',
                  'obj3': 'object=mod.C'}

        where obj1, obj2 and obj3 are wildcard names that appear
        in restructuring pattern.

        """
        if checks is not None:
            warnings.warn(
                "The use of checks parameter is deprecated; "
                "use the args parameter of the constructor instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            for name, value in checks.items():
                self.args[name] = similarfinder._pydefined_to_str(value)
        if imports is not None:
            warnings.warn(
                "The use of imports parameter is deprecated; "
                "use imports parameter of the constructor, instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.imports = imports
        changes = change.ChangeSet(f"Restructuring <{self.pattern}> to <{self.goal}>")
        if resources is not None:
            files = [
                resource
                for resource in resources
                if libutils.is_python_file(self.project, resource)
            ]
        else:
            files = self.project.get_python_files()
        job_set = task_handle.create_jobset("Collecting Changes", len(files))
        for resource in files:
            job_set.started_job(resource.path)
            pymodule = self.project.get_pymodule(resource)
            finder = similarfinder.SimilarFinder(pymodule, wildcards=self.wildcards)
            matches = list(finder.get_matches(self.pattern, self.args))
            computer = self._compute_changes(matches, pymodule)
            result = computer.get_changed()
            if result is not None:
                imported_source = self._add_imports(resource, result, self.imports)
                changes.add_change(change.ChangeContents(resource, imported_source))
            job_set.finished_job()
        return changes

    def _compute_changes(self, matches, pymodule):
        return _ChangeComputer(
            pymodule.source_code,
            pymodule.get_ast(),
            pymodule.lines,
            self.template,
            matches,
        )

    def _add_imports(self, resource, source, imports):
        if not imports:
            return source
        import_infos = self._get_import_infos(resource, imports)
        pymodule = libutils.get_string_module(self.project, source, resource)
        imports = module_imports.ModuleImports(self.project, pymodule)
        for import_info in import_infos:
            imports.add_import(import_info)
        return imports.get_changed_source()

    def _get_import_infos(self, resource, imports):
        pymodule = libutils.get_string_module(
            self.project, "\n".join(imports), resource
        )
        imports = module_imports.ModuleImports(self.project, pymodule)
        return [imports.import_info for imports in imports.imports]

    def make_checks(self, string_checks):
        """Convert str to str dicts to str to PyObject dicts

        This function is here to ease writing a UI.

        """
        checks = {}
        for key, value in string_checks.items():
            is_pyname = not key.endswith(".object") and not key.endswith(".type")
            evaluated = self._evaluate(value, is_pyname=is_pyname)
            if evaluated is not None:
                checks[key] = evaluated
        return checks

    def _evaluate(self, code, is_pyname=True):
        attributes = code.split(".")
        pyname = None
        if attributes[0] in ("__builtin__", "__builtins__"):

            class _BuiltinsStub:
                def get_attribute(self, name):
                    return builtins.builtins[name]

            pyobject = _BuiltinsStub()
        else:
            pyobject = self.project.get_module(attributes[0])
        for attribute in attributes[1:]:
            pyname = pyobject[attribute]
            if pyname is None:
                return None
            pyobject = pyname.get_object()
        return pyname if is_pyname else pyobject


def replace(code, pattern, goal):
    """used by other refactorings"""
    finder = similarfinder.RawSimilarFinder(code)
    matches = list(finder.get_matches(pattern))
    ast = patchedast.get_patched_ast(code)
    lines = codeanalyze.SourceLinesAdapter(code)
    template = similarfinder.CodeTemplate(goal)
    computer = _ChangeComputer(code, ast, lines, template, matches)
    result = computer.get_changed()
    if result is None:
        return code
    return result


class _ChangeComputer:
    def __init__(self, code, ast, lines, goal, matches):
        self.source = code
        self.goal = goal
        self.matches = matches
        self.ast = ast
        self.lines = lines
        self.matched_asts = {}
        self._nearest_roots = {}
        if self._is_expression():
            for match in self.matches:
                self.matched_asts[match.ast] = match

    def get_changed(self):
        if self._is_expression():
            result = self._get_node_text(self.ast)
            if result == self.source:
                return None
            return result
        else:
            collector = codeanalyze.ChangeCollector(self.source)
            last_end = -1
            for match in self.matches:
                start, end = match.get_region()
                if start < last_end:
                    if not self._is_expression():
                        continue
                last_end = end
                replacement = self._get_matched_text(match)
                collector.add_change(start, end, replacement)
            return collector.get_changed()

    def _is_expression(self):
        return self.matches and isinstance(
            self.matches[0], similarfinder.ExpressionMatch
        )

    def _get_matched_text(self, match):
        mapping = {}
        for name in self.goal.get_names():
            node = match.get_ast(name)
            if node is None:
                raise similarfinder.BadNameInCheckError("Unknown name <%s>" % name)
            force = self._is_expression() and match.ast == node
            mapping[name] = self._get_node_text(node, force)
        unindented = self.goal.substitute(mapping)
        return self._auto_indent(match.get_region()[0], unindented)

    def _get_node_text(self, node, force=False):
        if not force and node in self.matched_asts:
            return self._get_matched_text(self.matched_asts[node])
        start, end = patchedast.node_region(node)
        main_text = self.source[start:end]
        collector = codeanalyze.ChangeCollector(main_text)
        for node in self._get_nearest_roots(node):
            sub_start, sub_end = patchedast.node_region(node)
            collector.add_change(
                sub_start - start, sub_end - start, self._get_node_text(node)
            )
        result = collector.get_changed()
        if result is None:
            return main_text
        return result

    def _auto_indent(self, offset, text):
        lineno = self.lines.get_line_number(offset)
        indents = sourceutils.get_indents(self.lines, lineno)
        result = []
        for index, line in enumerate(text.splitlines(True)):
            if index != 0 and line.strip():
                result.append(" " * indents)
            result.append(line)
        return "".join(result)

    def _get_nearest_roots(self, node):
        if node not in self._nearest_roots:
            result = []
            for child in ast.iter_child_nodes(node):
                if child in self.matched_asts:
                    result.append(child)
                else:
                    result.extend(self._get_nearest_roots(child))
            self._nearest_roots[node] = result
        return self._nearest_roots[node]
