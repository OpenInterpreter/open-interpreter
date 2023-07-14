from rope.base import evaluate, exceptions, libutils, pyobjects, taskhandle
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import importutils, occurrences, rename, sourceutils


class IntroduceFactory:
    def __init__(self, project, resource, offset):
        self.project = project
        self.offset = offset

        this_pymodule = self.project.get_pymodule(resource)
        self.old_pyname = evaluate.eval_location(this_pymodule, offset)
        if self.old_pyname is None or not isinstance(
            self.old_pyname.get_object(), pyobjects.PyClass
        ):
            raise exceptions.RefactoringError(
                "Introduce factory should be performed on a class."
            )
        self.old_name = self.old_pyname.get_object().get_name()
        self.pymodule = self.old_pyname.get_object().get_module()
        self.resource = self.pymodule.get_resource()

    def get_changes(
        self,
        factory_name,
        global_factory=False,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get the changes this refactoring makes

        `factory_name` indicates the name of the factory function to
        be added.  If `global_factory` is `True` the factory will be
        global otherwise a static method is added to the class.

        `resources` can be a list of `rope.base.resource.File` that
        this refactoring should be applied on; if `None` all python
        files in the project are searched.

        """
        if resources is None:
            resources = self.project.get_python_files()
        changes = ChangeSet("Introduce factory method <%s>" % factory_name)
        job_set = task_handle.create_jobset("Collecting Changes", len(resources))
        self._change_module(resources, changes, factory_name, global_factory, job_set)
        return changes

    def get_name(self):
        """Return the name of the class"""
        return self.old_name

    def _change_module(self, resources, changes, factory_name, global_, job_set):
        if global_:
            replacement = "__rope_factory_%s_" % factory_name
        else:
            replacement = self._new_function_name(factory_name, global_)

        for file_ in resources:
            job_set.started_job(file_.path)
            if file_ == self.resource:
                self._change_resource(changes, factory_name, global_)
                job_set.finished_job()
                continue
            changed_code = self._rename_occurrences(file_, replacement, global_)
            if changed_code is not None:
                if global_:
                    new_pymodule = libutils.get_string_module(
                        self.project, changed_code, self.resource
                    )
                    modname = libutils.modname(self.resource)
                    changed_code, imported = importutils.add_import(
                        self.project, new_pymodule, modname, factory_name
                    )
                    changed_code = changed_code.replace(replacement, imported)
                changes.add_change(ChangeContents(file_, changed_code))
            job_set.finished_job()

    def _change_resource(self, changes, factory_name, global_):
        class_scope = self.old_pyname.get_object().get_scope()
        source_code = self._rename_occurrences(
            self.resource, self._new_function_name(factory_name, global_), global_
        )
        if source_code is None:
            source_code = self.pymodule.source_code
        else:
            self.pymodule = libutils.get_string_module(
                self.project, source_code, resource=self.resource
            )
        lines = self.pymodule.lines
        start = self._get_insertion_offset(class_scope, lines)
        result = source_code[:start]
        result += self._get_factory_method(lines, class_scope, factory_name, global_)
        result += source_code[start:]
        changes.add_change(ChangeContents(self.resource, result))

    def _get_insertion_offset(self, class_scope, lines):
        start_line = class_scope.get_end()
        if class_scope.get_scopes():
            start_line = class_scope.get_scopes()[-1].get_end()
        start = lines.get_line_end(start_line) + 1
        return start

    def _get_factory_method(self, lines, class_scope, factory_name, global_):
        unit_indents = " " * sourceutils.get_indent(self.project)
        if global_:
            if self._get_scope_indents(lines, class_scope) > 0:
                raise exceptions.RefactoringError(
                    "Cannot make global factory method for nested classes."
                )
            return "\ndef {}(*args, **kwds):\n{}return {}(*args, **kwds)\n".format(
                factory_name,
                unit_indents,
                self.old_name,
            )
        unindented_factory = (
            "@staticmethod\ndef %s(*args, **kwds):\n" % factory_name
            + f"{unit_indents}return {self.old_name}(*args, **kwds)\n"
        )
        indents = self._get_scope_indents(lines, class_scope) + sourceutils.get_indent(
            self.project
        )
        return "\n" + sourceutils.indent_lines(unindented_factory, indents)

    def _get_scope_indents(self, lines, scope):
        return sourceutils.get_indents(lines, scope.get_start())

    def _new_function_name(self, factory_name, global_):
        if global_:
            return factory_name
        else:
            return self.old_name + "." + factory_name

    def _rename_occurrences(self, file_, changed_name, global_factory):
        finder = occurrences.create_finder(
            self.project, self.old_name, self.old_pyname, only_calls=True
        )
        return rename.rename_in_module(
            finder, changed_name, resource=file_, replace_primary=global_factory
        )


IntroduceFactoryRefactoring = IntroduceFactory
