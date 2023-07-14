import warnings

from rope.base import change, codeanalyze, evaluate, exceptions, libutils, pyobjects
from rope.refactor import occurrences, rename, sourceutils


class MethodObject:
    def __init__(self, project, resource, offset):
        self.project = project
        this_pymodule = self.project.get_pymodule(resource)
        pyname = evaluate.eval_location(this_pymodule, offset)
        if pyname is None or not isinstance(pyname.get_object(), pyobjects.PyFunction):
            raise exceptions.RefactoringError(
                "Replace method with method object refactoring should be "
                "performed on a function."
            )
        self.pyfunction = pyname.get_object()
        self.pymodule = self.pyfunction.get_module()
        self.resource = self.pymodule.get_resource()

    def get_new_class(self, name):
        body = sourceutils.fix_indentation(
            self._get_body(), sourceutils.get_indent(self.project) * 2
        )
        return "class {}(object):\n\n{}{}def __call__(self):\n{}".format(
            name,
            self._get_init(),
            " " * sourceutils.get_indent(self.project),
            body,
        )

    def get_changes(self, classname=None, new_class_name=None):
        if new_class_name is not None:
            warnings.warn(
                "new_class_name parameter is deprecated; use classname",
                DeprecationWarning,
                stacklevel=2,
            )
            classname = new_class_name
        collector = codeanalyze.ChangeCollector(self.pymodule.source_code)
        start, end = sourceutils.get_body_region(self.pyfunction)
        indents = sourceutils.get_indents(
            self.pymodule.lines, self.pyfunction.get_scope().get_start()
        ) + sourceutils.get_indent(self.project)
        new_contents = " " * indents + "return {}({})()\n".format(
            classname,
            ", ".join(self._get_parameter_names()),
        )
        collector.add_change(start, end, new_contents)
        insertion = self._get_class_insertion_point()
        collector.add_change(
            insertion, insertion, "\n\n" + self.get_new_class(classname)
        )
        changes = change.ChangeSet("Replace method with method object refactoring")
        changes.add_change(
            change.ChangeContents(self.resource, collector.get_changed())
        )
        return changes

    def _get_class_insertion_point(self):
        current = self.pyfunction
        while current.parent != self.pymodule:
            current = current.parent
        end = self.pymodule.lines.get_line_end(current.get_scope().get_end())
        return min(end + 1, len(self.pymodule.source_code))

    def _get_body(self):
        body = sourceutils.get_body(self.pyfunction)
        for param in self._get_parameter_names():
            body = param + " = None\n" + body
            pymod = libutils.get_string_module(self.project, body, self.resource)
            pyname = pymod[param]
            finder = occurrences.create_finder(self.project, param, pyname)
            result = rename.rename_in_module(finder, "self." + param, pymodule=pymod)
            body = result[result.index("\n") + 1 :]
        return body

    def _get_init(self):
        params = self._get_parameter_names()
        indents = " " * sourceutils.get_indent(self.project)
        if not params:
            return ""
        header = indents + "def __init__(self"
        body = ""
        for arg in params:
            new_name = arg
            if arg == "self":
                new_name = "host"
            header += ", %s" % new_name
            body += indents * 2 + f"self.{arg} = {new_name}\n"
        header += "):"
        return f"{header}\n{body}\n"

    def _get_parameter_names(self):
        return self.pyfunction.get_param_names()
