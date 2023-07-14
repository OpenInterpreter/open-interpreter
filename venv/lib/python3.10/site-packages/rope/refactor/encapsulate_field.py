from rope.base import evaluate, exceptions, libutils, pynames, taskhandle, utils, worder
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import occurrences, sourceutils


class EncapsulateField:
    def __init__(self, project, resource, offset):
        self.project = project
        self.name = worder.get_name_at(resource, offset)
        this_pymodule = self.project.get_pymodule(resource)
        self.pyname = evaluate.eval_location(this_pymodule, offset)
        if not self._is_an_attribute(self.pyname):
            raise exceptions.RefactoringError(
                "Encapsulate field should be performed on class attributes."
            )
        self.resource = self.pyname.get_definition_location()[0].get_resource()

    def get_changes(
        self,
        getter=None,
        setter=None,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get the changes this refactoring makes

        If `getter` is not `None`, that will be the name of the
        getter, otherwise ``get_${field_name}`` will be used.  The
        same is true for `setter` and if it is None set_${field_name} is
        used.

        `resources` can be a list of `rope.base.resource.File` that
        the refactoring should be applied on; if `None` all python
        files in the project are searched.

        """
        if resources is None:
            resources = self.project.get_python_files()
        changes = ChangeSet("Encapsulate field <%s>" % self.name)
        job_set = task_handle.create_jobset("Collecting Changes", len(resources))
        if getter is None:
            getter = "get_" + self.name
        if setter is None:
            setter = "set_" + self.name
        renamer = GetterSetterRenameInModule(
            self.project, self.name, self.pyname, getter, setter
        )
        for file in resources:
            job_set.started_job(file.path)
            if file == self.resource:
                result = self._change_holding_module(changes, renamer, getter, setter)
                changes.add_change(ChangeContents(self.resource, result))
            else:
                result = renamer.get_changed_module(file)
                if result is not None:
                    changes.add_change(ChangeContents(file, result))
            job_set.finished_job()
        return changes

    def get_field_name(self):
        """Get the name of the field to be encapsulated"""
        return self.name

    def _is_an_attribute(self, pyname):
        if pyname is not None and isinstance(pyname, pynames.AssignedName):
            pymodule, lineno = self.pyname.get_definition_location()
            scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
            if scope.get_kind() == "Class":
                return pyname in scope.get_names().values()
            parent = scope.parent
            if parent is not None and parent.get_kind() == "Class":
                return pyname in parent.get_names().values()
        return False

    def _get_defining_class_scope(self):
        defining_scope = self._get_defining_scope()
        if defining_scope.get_kind() == "Function":
            defining_scope = defining_scope.parent
        return defining_scope

    def _get_defining_scope(self):
        pymodule, line = self.pyname.get_definition_location()
        return pymodule.get_scope().get_inner_scope_for_line(line)

    def _change_holding_module(self, changes, renamer, getter, setter):
        pymodule = self.project.get_pymodule(self.resource)
        class_scope = self._get_defining_class_scope()
        defining_object = self._get_defining_scope().pyobject
        start, end = sourceutils.get_body_region(defining_object)

        new_source = renamer.get_changed_module(
            pymodule=pymodule, skip_start=start, skip_end=end
        )
        if new_source is not None:
            pymodule = libutils.get_string_module(
                self.project, new_source, self.resource
            )
            class_scope = pymodule.get_scope().get_inner_scope_for_line(
                class_scope.get_start()
            )
        indents = sourceutils.get_indent(self.project) * " "
        getter = f"def {getter}(self):\n{indents}return self.{self.name}"
        setter = f"def {setter}(self, value):\n{indents}self.{self.name} = value"
        new_source = sourceutils.add_methods(pymodule, class_scope, [getter, setter])
        return new_source


class GetterSetterRenameInModule:
    def __init__(self, project, name, pyname, getter, setter):
        self.project = project
        self.name = name
        self.finder = occurrences.create_finder(project, name, pyname)
        self.getter = getter
        self.setter = setter

    def get_changed_module(
        self, resource=None, pymodule=None, skip_start=0, skip_end=0
    ):
        change_finder = _FindChangesForModule(
            self, resource, pymodule, skip_start, skip_end
        )
        return change_finder.get_changed_module()


class _FindChangesForModule:
    def __init__(self, finder, resource, pymodule, skip_start, skip_end):
        self.project = finder.project
        self.finder = finder.finder
        self.getter = finder.getter
        self.setter = finder.setter
        self.resource = resource
        self.pymodule = pymodule
        self.last_modified = 0
        self.last_set = None
        self.set_index = None
        self.skip_start = skip_start
        self.skip_end = skip_end

    def get_changed_module(self):
        result = []
        for occurrence in self.finder.find_occurrences(self.resource, self.pymodule):
            start, end = occurrence.get_word_range()
            if self.skip_start <= start < self.skip_end:
                continue
            self._manage_writes(start, result)
            result.append(self.source[self.last_modified : start])
            if self._is_assigned_in_a_tuple_assignment(occurrence):
                raise exceptions.RefactoringError(
                    "Cannot handle tuple assignments in encapsulate field."
                )
            if occurrence.is_written():
                assignment_type = self.worder.get_assignment_type(start)
                if assignment_type == "=":
                    result.append(self.setter + "(")
                else:
                    var_name = (
                        self.source[occurrence.get_primary_range()[0] : start]
                        + self.getter
                        + "()"
                    )
                    result.append(
                        self.setter + "(" + var_name + " %s " % assignment_type[:-1]
                    )
                current_line = self.lines.get_line_number(start)
                start_line, end_line = self.pymodule.logical_lines.logical_line_in(
                    current_line
                )
                self.last_set = self.lines.get_line_end(end_line)
                end = self.source.index("=", end) + 1
                self.set_index = len(result)
            else:
                result.append(self.getter + "()")
            self.last_modified = end
        if self.last_modified != 0:
            self._manage_writes(len(self.source), result)
            result.append(self.source[self.last_modified :])
            return "".join(result)
        return None

    def _manage_writes(self, offset, result):
        if self.last_set is not None and self.last_set <= offset:
            result.append(self.source[self.last_modified : self.last_set])
            set_value = "".join(result[self.set_index :]).strip()
            del result[self.set_index :]
            result.append(set_value + ")")
            self.last_modified = self.last_set
            self.last_set = None

    def _is_assigned_in_a_tuple_assignment(self, occurrence):
        offset = occurrence.get_word_range()[0]
        return self.worder.is_assigned_in_a_tuple_assignment(offset)

    @property
    @utils.saveit
    def source(self):
        if self.resource is not None:
            return self.resource.read()
        else:
            return self.pymodule.source_code

    @property
    @utils.saveit
    def lines(self):
        if self.pymodule is None:
            self.pymodule = self.project.get_pymodule(self.resource)
        return self.pymodule.lines

    @property
    @utils.saveit
    def worder(self):
        return worder.Worder(self.source)
