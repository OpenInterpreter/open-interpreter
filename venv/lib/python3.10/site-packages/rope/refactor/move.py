"""A module containing classes for move refactoring

`create_move()` is a factory for creating move refactoring objects
based on inputs.

"""
from __future__ import annotations

import typing
from typing import Union

from rope.base import (
    codeanalyze,
    evaluate,
    exceptions,
    libutils,
    pynames,
    pyobjects,
    taskhandle,
    worder,
)
from rope.base.change import ChangeContents, ChangeSet, MoveResource
from rope.refactor import functionutils, importutils, occurrences, rename, sourceutils
from rope.refactor.importutils.module_imports import (
    get_first_decorator_or_function_start_line,
)

if typing.TYPE_CHECKING:
    from rope.base import project, resources


def create_move(project, resource, offset=None):
    """A factory for creating Move objects

    Based on `resource` and `offset`, return one of `MoveModule`,
    `MoveGlobal` or `MoveMethod` for performing move refactoring.

    """
    if offset is None:
        return MoveModule(project, resource)
    this_pymodule = project.get_pymodule(resource)
    pyname = evaluate.eval_location(this_pymodule, offset)
    if pyname is not None:
        pyobject = pyname.get_object()
        if isinstance(pyobject, pyobjects.PyModule) or isinstance(
            pyobject, pyobjects.PyPackage
        ):
            return MoveModule(project, pyobject.get_resource())
        if isinstance(pyobject, pyobjects.PyFunction) and isinstance(
            pyobject.parent, pyobjects.PyClass
        ):
            return MoveMethod(project, resource, offset)
        if (
            isinstance(pyobject, pyobjects.PyDefinedObject)
            and isinstance(pyobject.parent, pyobjects.PyModule)
            or isinstance(pyname, pynames.AssignedName)
        ):
            return MoveGlobal(project, resource, offset)
    raise exceptions.RefactoringError(
        "Move only works on global classes/functions/variables, modules and methods."
    )


class MoveMethod:
    """For moving methods

    It makes a new method in the destination class and changes
    the body of the old method to call the new method.  You can
    inline the old method to change all of its occurrences.

    """

    def __init__(self, project, resource, offset):
        self.project = project
        this_pymodule = self.project.get_pymodule(resource)
        pyname = evaluate.eval_location(this_pymodule, offset)
        self.method_name = worder.get_name_at(resource, offset)
        self.pyfunction = pyname.get_object()
        if self.pyfunction.get_kind() != "method":
            raise exceptions.RefactoringError("Only normal methods can be moved.")

    def get_changes(
        self,
        dest_attr,
        new_name=None,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,  # FIXME: this is unused
    ):
        """Return the changes needed for this refactoring

        Parameters:

        - `dest_attr`: the name of the destination attribute
        - `new_name`: the name of the new method; if `None` uses
          the old name
        - `resources` can be a list of `rope.base.resources.File` to
          apply this refactoring on.  If `None`, the restructuring
          will be applied to all python files.

        """
        changes = ChangeSet("Moving method <%s>" % self.method_name)
        if resources is None:
            resources = self.project.get_python_files()
        if new_name is None:
            new_name = self.get_method_name()
        resource1, start1, end1, new_content1 = self._get_changes_made_by_old_class(
            dest_attr, new_name
        )
        collector1 = codeanalyze.ChangeCollector(resource1.read())
        collector1.add_change(start1, end1, new_content1)

        resource2, start2, end2, new_content2 = self._get_changes_made_by_new_class(
            dest_attr, new_name
        )
        if resource1 == resource2:
            collector1.add_change(start2, end2, new_content2)
        else:
            collector2 = codeanalyze.ChangeCollector(resource2.read())
            collector2.add_change(start2, end2, new_content2)
            result = collector2.get_changed()
            import_tools = importutils.ImportTools(self.project)
            new_imports = self._get_used_imports(import_tools)
            if new_imports:
                goal_pymodule = libutils.get_string_module(
                    self.project, result, resource2
                )
                result = _add_imports_to_module(
                    import_tools, goal_pymodule, new_imports
                )
            if resource2 in resources:
                changes.add_change(ChangeContents(resource2, result))

        if resource1 in resources:
            changes.add_change(ChangeContents(resource1, collector1.get_changed()))
        return changes

    def get_method_name(self):
        return self.method_name

    def _get_used_imports(self, import_tools):
        return importutils.get_imports(self.project, self.pyfunction)

    def _get_changes_made_by_old_class(self, dest_attr, new_name):
        pymodule = self.pyfunction.get_module()
        indents = self._get_scope_indents(self.pyfunction)
        body = "return self.{}.{}({})\n".format(
            dest_attr,
            new_name,
            self._get_passed_arguments_string(),
        )
        region = sourceutils.get_body_region(self.pyfunction)
        return (
            pymodule.get_resource(),
            region[0],
            region[1],
            sourceutils.fix_indentation(body, indents),
        )

    def _get_scope_indents(self, pyobject):
        pymodule = pyobject.get_module()
        return sourceutils.get_indents(
            pymodule.lines, pyobject.get_scope().get_start()
        ) + sourceutils.get_indent(self.project)

    def _get_changes_made_by_new_class(self, dest_attr, new_name):
        old_pyclass = self.pyfunction.parent
        if dest_attr not in old_pyclass:
            raise exceptions.RefactoringError(
                "Destination attribute <%s> not found" % dest_attr
            )
        pyclass = old_pyclass[dest_attr].get_object().get_type()
        if not isinstance(pyclass, pyobjects.PyClass):
            raise exceptions.RefactoringError(
                "Unknown class type for attribute <%s>" % dest_attr
            )
        pymodule = pyclass.get_module()
        resource = pyclass.get_module().get_resource()
        start, end = sourceutils.get_body_region(pyclass)
        pre_blanks = "\n"
        if pymodule.source_code[start:end].strip() != "pass":
            pre_blanks = "\n\n"
            start = end
        indents = self._get_scope_indents(pyclass)
        body = pre_blanks + sourceutils.fix_indentation(
            self.get_new_method(new_name), indents
        )
        return resource, start, end, body

    def get_new_method(self, name):
        return "{}\n{}".format(
            self._get_new_header(name),
            sourceutils.fix_indentation(
                self._get_body(), sourceutils.get_indent(self.project)
            ),
        )

    def _get_unchanged_body(self):
        return sourceutils.get_body(self.pyfunction)

    def _get_body(self, host="host"):
        self_name = self._get_self_name()
        body = self_name + " = None\n" + self._get_unchanged_body()
        pymodule = libutils.get_string_module(self.project, body)
        finder = occurrences.create_finder(self.project, self_name, pymodule[self_name])
        result = rename.rename_in_module(finder, host, pymodule=pymodule)
        if result is None:
            result = body
        return result[result.index("\n") + 1 :]

    def _get_self_name(self):
        return self.pyfunction.get_param_names()[0]

    def _get_new_header(self, name):
        header = "def %s(self" % name
        if self._is_host_used():
            header += ", host"
        definition_info = functionutils.DefinitionInfo.read(self.pyfunction)
        others = definition_info.arguments_to_string(1)
        if others:
            header += ", " + others
        return header + "):"

    def _get_passed_arguments_string(self):
        result = ""
        if self._is_host_used():
            result = "self"
        definition_info = functionutils.DefinitionInfo.read(self.pyfunction)
        others = definition_info.arguments_to_string(1)
        if others:
            if result:
                result += ", "
            result += others
        return result

    def _is_host_used(self):
        return self._get_body("__old_self") != self._get_unchanged_body()


class MoveGlobal:
    """For moving global function and classes"""

    project: project.Project

    def __init__(self, project, resource, offset):
        self.project = project
        this_pymodule = self.project.get_pymodule(resource)
        self.old_pyname = evaluate.eval_location(this_pymodule, offset)
        if self.old_pyname is None:
            raise exceptions.RefactoringError(
                "Move refactoring should be performed on a class/function/variable."
            )
        if self._is_variable(self.old_pyname):
            self.old_name = worder.get_name_at(resource, offset)
            pymodule = this_pymodule
        else:
            self.old_name = self.old_pyname.get_object().get_name()
            pymodule = self.old_pyname.get_object().get_module()
        self._check_exceptional_conditions()
        self.source = pymodule.get_resource()
        self.tools = _MoveTools(
            self.project, self.source, self.old_pyname, self.old_name
        )
        self.import_tools = self.tools.import_tools

    def _import_filter(self, stmt):
        module_name = libutils.modname(self.source)

        if isinstance(stmt.import_info, importutils.NormalImport):
            # Affect any statement that imports the source module
            return any(
                module_name == name
                for name, alias in stmt.import_info.names_and_aliases
            )
        elif isinstance(stmt.import_info, importutils.FromImport):
            # Affect statements importing from the source package
            if "." in module_name:
                package_name, basename = module_name.rsplit(".", 1)
                if stmt.import_info.module_name == package_name and any(
                    basename == name
                    for name, alias in stmt.import_info.names_and_aliases
                ):
                    return True
            return stmt.import_info.module_name == module_name
        return False

    def _check_exceptional_conditions(self):
        if self._is_variable(self.old_pyname):
            pymodule = self.old_pyname.get_definition_location()[0]
            try:
                pymodule.get_scope().get_name(self.old_name)
            except exceptions.NameNotFoundError:
                self._raise_refactoring_error()
        elif not (
            isinstance(self.old_pyname.get_object(), pyobjects.PyDefinedObject)
            and self._is_global(self.old_pyname.get_object())
        ):
            self._raise_refactoring_error()

    def _raise_refactoring_error(self):
        raise exceptions.RefactoringError(
            "Move refactoring should be performed on a global class, function "
            "or variable."
        )

    def _is_global(self, pyobject):
        return pyobject.get_scope().parent == pyobject.get_module().get_scope()

    def _is_variable(self, pyname):
        return isinstance(pyname, pynames.AssignedName)

    def get_changes(
        self,
        dest: Union[None, str, resources.Resource],
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Return the changes needed for this refactoring

        Parameters:

        - `dest`: the Resource or dotted moddule name of the move destination
        - `resources` can be a list of `rope.base.resources.File` to
          apply this refactoring on.  If `None`, the restructuring
          will be applied to all python files.

        """
        if isinstance(dest, str):
            dest = self.project.find_module(dest)
        if resources is None:
            resources = self.project.get_python_files()
        if dest is None or not dest.exists():
            raise exceptions.RefactoringError("Move destination does not exist.")
        if dest.is_folder() and dest.has_child("__init__.py"):
            dest = dest.get_child("__init__.py")
        if dest.is_folder():
            raise exceptions.RefactoringError(
                "Move destination for non-modules should not be folders."
            )
        if self.source == dest:
            raise exceptions.RefactoringError(
                "Moving global elements to the same module."
            )
        return self._calculate_changes(dest, resources, task_handle)

    def _calculate_changes(self, dest, resources, task_handle):
        changes = ChangeSet("Moving global <%s>" % self.old_name)
        job_set = task_handle.create_jobset("Collecting Changes", len(resources))
        for file_ in resources:
            job_set.started_job(file_.path)
            if file_ == self.source:
                changes.add_change(self._source_module_changes(dest))
            elif file_ == dest:
                changes.add_change(self._dest_module_changes(dest))
            elif self.tools.occurs_in_module(resource=file_):
                pymodule = self.project.get_pymodule(file_)
                # Changing occurrences
                placeholder = "__rope_renaming_%s_" % self.old_name
                source = self.tools.rename_in_module(placeholder, resource=file_)
                should_import = source is not None
                # Removing out of date imports
                pymodule = self.tools.new_pymodule(pymodule, source)
                source = self.import_tools.organize_imports(
                    pymodule, sort=False, import_filter=self._import_filter
                )
                # Adding new import
                if should_import:
                    pymodule = self.tools.new_pymodule(pymodule, source)
                    source, imported = importutils.add_import(
                        self.project, pymodule, self._new_modname(dest), self.old_name
                    )
                    source = source.replace(placeholder, imported)
                source = self.tools.new_source(pymodule, source)
                if source != file_.read():
                    changes.add_change(ChangeContents(file_, source))
            job_set.finished_job()
        return changes

    def _source_module_changes(self, dest):
        placeholder = "__rope_moving_%s_" % self.old_name
        handle = _ChangeMoveOccurrencesHandle(placeholder)
        occurrence_finder = occurrences.create_finder(
            self.project, self.old_name, self.old_pyname
        )
        start, end = self._get_moving_region()
        renamer = ModuleSkipRenamer(occurrence_finder, self.source, handle, start, end)
        source = renamer.get_changed_module()
        pymodule = libutils.get_string_module(self.project, source, self.source)
        source = self.import_tools.organize_imports(pymodule, sort=False)
        if handle.occurred:
            pymodule = libutils.get_string_module(self.project, source, self.source)
            # Adding new import
            source, imported = importutils.add_import(
                self.project, pymodule, self._new_modname(dest), self.old_name
            )
            source = source.replace(placeholder, imported)
        return ChangeContents(self.source, source)

    def _new_modname(self, dest):
        return libutils.modname(dest)

    def _dest_module_changes(self, dest):
        # Changing occurrences
        pymodule = self.project.get_pymodule(dest)
        source = self.tools.rename_in_module(self.old_name, pymodule)
        pymodule = self.tools.new_pymodule(pymodule, source)

        moving, imports = self._get_moving_element_with_imports()
        pymodule, has_changed = self._add_imports2(pymodule, imports)

        module_with_imports = self.import_tools.module_imports(pymodule)
        source = pymodule.source_code
        lineno = 0
        if module_with_imports.imports:
            lineno = module_with_imports.imports[-1].end_line - 1
        else:
            while lineno < pymodule.lines.length() and pymodule.lines.get_line(
                lineno + 1
            ).lstrip().startswith("#"):
                lineno += 1
        if lineno > 0:
            cut = pymodule.lines.get_line_end(lineno) + 1
            result = source[:cut] + "\n\n" + moving + source[cut:]
        else:
            result = moving + source

        # Organizing imports
        source = result
        pymodule = libutils.get_string_module(self.project, source, dest)
        source = self.import_tools.organize_imports(pymodule, sort=False, unused=False)
        # Remove unused imports of the old module
        pymodule = libutils.get_string_module(self.project, source, dest)
        source = self.import_tools.organize_imports(
            pymodule,
            sort=False,
            selfs=False,
            unused=True,
            import_filter=self._import_filter,
        )
        return ChangeContents(dest, source)

    def _get_moving_element_with_imports(self):
        return moving_code_with_imports(
            self.project, self.source, self._get_moving_element()
        )

    def _get_module_with_imports(self, source_code, resource):
        pymodule = libutils.get_string_module(self.project, source_code, resource)
        return self.import_tools.module_imports(pymodule)

    def _get_moving_element(self):
        start, end = self._get_moving_region()
        moving = self.source.read()[start:end]
        return moving.rstrip() + "\n"

    def _get_moving_region(self):
        pymodule = self.project.get_pymodule(self.source)
        lines = pymodule.lines
        if self._is_variable(self.old_pyname):
            logical_lines = pymodule.logical_lines
            lineno = logical_lines.logical_line_in(
                self.old_pyname.get_definition_location()[1]
            )[0]
            start = lines.get_line_start(lineno)
            end_line = logical_lines.logical_line_in(lineno)[1]
        else:
            node = self.old_pyname.get_object().ast_node
            start = lines.get_line_start(
                get_first_decorator_or_function_start_line(node)
            )
            end_line = self.old_pyname.get_object().get_scope().get_end()

        # Include comment lines before the definition
        start_line = lines.get_line_number(start)
        while start_line > 1 and lines.get_line(start_line - 1).startswith("#"):
            start_line -= 1
        start = lines.get_line_start(start_line)

        while end_line < lines.length() and lines.get_line(end_line + 1).strip() == "":
            end_line += 1
        end = min(lines.get_line_end(end_line) + 1, len(pymodule.source_code))
        return start, end

    def _add_imports2(self, pymodule, new_imports):
        source = self.tools.add_imports(pymodule, new_imports)
        if source is None:
            return pymodule, False
        else:
            resource = pymodule.get_resource()
            pymodule = libutils.get_string_module(self.project, source, resource)
            return pymodule, True


class MoveModule:
    """For moving modules and packages"""

    def __init__(self, project, resource):
        self.project = project
        if not resource.is_folder() and resource.name == "__init__.py":
            resource = resource.parent
        if resource.is_folder() and not resource.has_child("__init__.py"):
            raise exceptions.RefactoringError("Cannot move non-package folder.")
        dummy_pymodule = libutils.get_string_module(self.project, "")
        self.old_pyname = pynames.ImportedModule(dummy_pymodule, resource=resource)
        self.source = self.old_pyname.get_object().get_resource()
        if self.source.is_folder():
            self.old_name = self.source.name
        else:
            self.old_name = self.source.name[:-3]
        self.tools = _MoveTools(
            self.project, self.source, self.old_pyname, self.old_name
        )
        self.import_tools = self.tools.import_tools

    def get_changes(
        self, dest, resources=None, task_handle=taskhandle.DEFAULT_TASK_HANDLE
    ):
        if resources is None:
            resources = self.project.get_python_files()
        if dest is None or not dest.is_folder():
            raise exceptions.RefactoringError(
                "Move destination for modules should be packages."
            )
        return self._calculate_changes(dest, resources, task_handle)

    def _calculate_changes(self, dest, resources, task_handle):
        changes = ChangeSet("Moving module <%s>" % self.old_name)
        job_set = task_handle.create_jobset("Collecting changes", len(resources))
        for module in resources:
            job_set.started_job(module.path)
            if module == self.source:
                self._change_moving_module(changes, dest)
            else:
                source = self._change_occurrences_in_module(dest, resource=module)
                if source is not None:
                    changes.add_change(ChangeContents(module, source))
            job_set.finished_job()
        if self.project == self.source.project:
            changes.add_change(MoveResource(self.source, dest.path))
        return changes

    def _new_modname(self, dest):
        destname = libutils.modname(dest)
        if destname:
            return destname + "." + self.old_name
        return self.old_name

    def _new_import(self, dest):
        return importutils.NormalImport([(self._new_modname(dest), None)])

    def _change_moving_module(self, changes, dest):
        if not self.source.is_folder():
            pymodule = self.project.get_pymodule(self.source)
            source = self.import_tools.relatives_to_absolutes(pymodule)
            pymodule = self.tools.new_pymodule(pymodule, source)
            source = self._change_occurrences_in_module(dest, pymodule)
            source = self.tools.new_source(pymodule, source)
            if source != self.source.read():
                changes.add_change(ChangeContents(self.source, source))

    def _change_occurrences_in_module(self, dest, pymodule=None, resource=None):
        if not self.tools.occurs_in_module(pymodule=pymodule, resource=resource):
            return
        if pymodule is None:
            pymodule = self.project.get_pymodule(resource)
        new_name = self._new_modname(dest)
        module_imports = importutils.get_module_imports(self.project, pymodule)
        changed = False
        source = None
        if libutils.modname(dest):
            changed = self._change_import_statements(dest, new_name, module_imports)
            if changed:
                source = module_imports.get_changed_source()
                source = self.tools.new_source(pymodule, source)
                pymodule = self.tools.new_pymodule(pymodule, source)

        new_import = self._new_import(dest)
        source = self.tools.rename_in_module(
            new_name,
            imports=True,
            pymodule=pymodule,
            resource=resource if not changed else None,
        )
        should_import = self.tools.occurs_in_module(
            pymodule=pymodule, resource=resource, imports=False
        )
        pymodule = self.tools.new_pymodule(pymodule, source)
        source = self.tools.remove_old_imports(pymodule)
        if should_import:
            pymodule = self.tools.new_pymodule(pymodule, source)
            source = self.tools.add_imports(pymodule, [new_import])
        source = self.tools.new_source(pymodule, source)
        if source is not None and source != pymodule.resource.read():
            return source
        return None

    def _change_import_statements(self, dest, new_name, module_imports):
        moving_module = self.source
        parent_module = moving_module.parent

        changed = False
        for import_stmt in module_imports.imports:
            if not any(
                name_and_alias[0] == self.old_name
                for name_and_alias in import_stmt.import_info.names_and_aliases
            ) and not any(
                name_and_alias[0] == libutils.modname(self.source)
                for name_and_alias in import_stmt.import_info.names_and_aliases
            ):
                continue

            # Case 1: Look for normal imports of the moving module.
            if isinstance(import_stmt.import_info, importutils.NormalImport):
                continue

            # Case 2: The moving module is from-imported.
            changed = (
                self._handle_moving_in_from_import_stmt(
                    dest, import_stmt, module_imports, parent_module
                )
                or changed
            )

            # Case 3: Names are imported from the moving module.
            context = importutils.importinfo.ImportContext(self.project, None)
            if (
                not import_stmt.import_info.is_empty()
                and import_stmt.import_info.get_imported_resource(context)
                == moving_module
            ):
                import_stmt.import_info = importutils.FromImport(
                    new_name,
                    import_stmt.import_info.level,
                    import_stmt.import_info.names_and_aliases,
                )
                changed = True

        return changed

    def _handle_moving_in_from_import_stmt(
        self, dest, import_stmt, module_imports, parent_module
    ):
        changed = False
        context = importutils.importinfo.ImportContext(self.project, None)
        if import_stmt.import_info.get_imported_resource(context) == parent_module:
            imports = import_stmt.import_info.names_and_aliases
            new_imports = []
            for name, alias in imports:
                # The moving module was imported.
                if name == self.old_name:
                    changed = True
                    new_import = importutils.FromImport(
                        libutils.modname(dest), 0, [(self.old_name, alias)]
                    )
                    module_imports.add_import(new_import)
                else:
                    new_imports.append((name, alias))

            # Update the imports if the imported names were changed.
            if new_imports != imports:
                changed = True
                if new_imports:
                    import_stmt.import_info = importutils.FromImport(
                        import_stmt.import_info.module_name,
                        import_stmt.import_info.level,
                        new_imports,
                    )
                else:
                    import_stmt.empty_import()
        return changed


class _ChangeMoveOccurrencesHandle:
    def __init__(self, new_name):
        self.new_name = new_name
        self.occurred = False

    def occurred_inside_skip(self, change_collector, occurrence):
        pass

    def occurred_outside_skip(self, change_collector, occurrence):
        start, end = occurrence.get_primary_range()
        change_collector.add_change(start, end, self.new_name)
        self.occurred = True


class _MoveTools:
    def __init__(self, project, source, pyname, old_name):
        self.project = project
        self.source = source
        self.old_pyname = pyname
        self.old_name = old_name
        self.import_tools = importutils.ImportTools(self.project)

    def remove_old_imports(self, pymodule):
        old_source = pymodule.source_code
        module_with_imports = self.import_tools.module_imports(pymodule)

        class CanSelect:
            changed = False
            old_name = self.old_name
            old_pyname = self.old_pyname

            def __call__(self, name):
                try:
                    if (
                        name == self.old_name
                        and pymodule[name].get_object() == self.old_pyname.get_object()
                    ):
                        self.changed = True
                        return False
                except exceptions.AttributeNotFoundError:
                    pass
                return True

        can_select = CanSelect()
        module_with_imports.filter_names(can_select)
        new_source = module_with_imports.get_changed_source()
        if old_source != new_source:
            return new_source

    def rename_in_module(self, new_name, pymodule=None, imports=False, resource=None):
        occurrence_finder = self._create_finder(imports)
        source = rename.rename_in_module(
            occurrence_finder,
            new_name,
            replace_primary=True,
            pymodule=pymodule,
            resource=resource,
        )
        return source

    def occurs_in_module(self, pymodule=None, resource=None, imports=True):
        finder = self._create_finder(imports)
        occurrences = finder.find_occurrences(pymodule=pymodule, resource=resource)
        sentinel = object()
        return next(occurrences, sentinel) is not sentinel

    def _create_finder(self, imports):
        return occurrences.create_finder(
            self.project,
            self.old_name,
            self.old_pyname,
            imports=imports,
            keywords=False,
        )

    def new_pymodule(self, pymodule, source):
        if source is not None:
            return libutils.get_string_module(
                self.project, source, pymodule.get_resource()
            )
        return pymodule

    def new_source(self, pymodule, source):
        if source is None:
            return pymodule.source_code
        return source

    def add_imports(self, pymodule, new_imports):
        return _add_imports_to_module(self.import_tools, pymodule, new_imports)


def _add_imports_to_module(import_tools, pymodule, new_imports):
    module_with_imports = import_tools.module_imports(pymodule)
    for new_import in new_imports:
        module_with_imports.add_import(new_import)
    return module_with_imports.get_changed_source()


def moving_code_with_imports(project, resource, source):
    import_tools = importutils.ImportTools(project)
    pymodule = libutils.get_string_module(project, source, resource)

    # Strip comment prefix, if any. These need to stay before the moving
    # section, but imports would be added between them.
    lines = codeanalyze.SourceLinesAdapter(source)
    start = 1
    while start < lines.length() and lines.get_line(start).startswith("#"):
        start += 1
    moving_prefix = source[: lines.get_line_start(start)]
    pymodule = libutils.get_string_module(
        project, source[lines.get_line_start(start) :], resource
    )

    origin = project.get_pymodule(resource)

    imports = [stmt.import_info for stmt in import_tools.module_imports(origin).imports]

    back_names = [name for name in origin if name not in pymodule]
    imports.append(import_tools.get_from_import(resource, back_names))

    source = _add_imports_to_module(import_tools, pymodule, imports)
    pymodule = libutils.get_string_module(project, source, resource)

    source = import_tools.relatives_to_absolutes(pymodule)
    pymodule = libutils.get_string_module(project, source, resource)
    source = import_tools.organize_imports(pymodule, selfs=False)
    pymodule = libutils.get_string_module(project, source, resource)

    # extracting imports after changes
    module_imports = import_tools.module_imports(pymodule)
    imports = [import_stmt.import_info for import_stmt in module_imports.imports]
    start = 1
    if module_imports.imports:
        start = module_imports.imports[-1].end_line
    lines = codeanalyze.SourceLinesAdapter(source)
    while start < lines.length() and not lines.get_line(start).strip():
        start += 1

    # Reinsert the prefix which was removed at the beginning
    moving = moving_prefix + source[lines.get_line_start(start) :]
    return moving, imports


class ModuleSkipRenamerHandle:
    def occurred_outside_skip(self, change_collector, occurrence):
        pass

    def occurred_inside_skip(self, change_collector, occurrence):
        pass


class ModuleSkipRenamer:
    """Rename occurrences in a module

    This class can be used when you want to treat a region in a file
    separately from other parts when renaming.

    """

    def __init__(
        self,
        occurrence_finder,
        resource,
        handle=None,
        skip_start=0,
        skip_end=0,
        replacement="",
    ):
        """Constructor

        if replacement is `None` the region is not changed.  Otherwise
        it is replaced with `replacement`.

        """
        self.occurrence_finder = occurrence_finder
        self.resource = resource
        self.skip_start = skip_start
        self.skip_end = skip_end
        self.replacement = replacement
        self.handle = handle
        if self.handle is None:
            self.handle = ModuleSkipRenamerHandle()

    def get_changed_module(self):
        source = self.resource.read()
        change_collector = codeanalyze.ChangeCollector(source)
        if self.replacement is not None:
            change_collector.add_change(
                self.skip_start, self.skip_end, self.replacement
            )
        for occurrence in self.occurrence_finder.find_occurrences(self.resource):
            start, end = occurrence.get_primary_range()
            if self.skip_start <= start < self.skip_end:
                self.handle.occurred_inside_skip(change_collector, occurrence)
            else:
                self.handle.occurred_outside_skip(change_collector, occurrence)
        result = change_collector.get_changed()
        if result is not None and result != source:
            return result
