import warnings

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
from rope.refactor import occurrences


class Rename:
    """A class for performing rename refactoring

    It can rename everything: classes, functions, modules, packages,
    methods, variables and keyword arguments.

    """

    def __init__(self, project, resource, offset=None):
        """If `offset` is None, the `resource` itself will be renamed"""
        self.project = project
        self.resource = resource
        if offset is not None:
            self.old_name = worder.get_name_at(self.resource, offset)
            this_pymodule = self.project.get_pymodule(self.resource)
            self.old_instance, self.old_pyname = evaluate.eval_location2(
                this_pymodule, offset
            )
            if self.old_pyname is None:
                raise exceptions.RefactoringError(
                    "Rename refactoring should be performed"
                    " on resolvable python identifiers."
                )
        else:
            if not resource.is_folder() and resource.name == "__init__.py":
                resource = resource.parent
            dummy_pymodule = libutils.get_string_module(self.project, "")
            self.old_instance = None
            self.old_pyname = pynames.ImportedModule(dummy_pymodule, resource=resource)
            if resource.is_folder():
                self.old_name = resource.name
            else:
                self.old_name = resource.name[:-3]

    def get_old_name(self):
        return self.old_name

    def get_changes(
        self,
        new_name,
        in_file=None,
        in_hierarchy=False,
        unsure=None,
        docs=False,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get the changes needed for this refactoring

        Parameters:

        - `in_hierarchy`: when renaming a method this keyword forces
          to rename all matching methods in the hierarchy
        - `docs`: when `True` rename refactoring will rename
          occurrences in comments and strings where the name is
          visible.  Setting it will make renames faster, too.
        - `unsure`: decides what to do about unsure occurrences.
          If `None`, they are ignored.  Otherwise `unsure` is
          called with an instance of `occurrence.Occurrence` as
          parameter.  If it returns `True`, the occurrence is
          considered to be a match.
        - `resources` can be a list of `rope.base.resources.File` to
          apply this refactoring on.  If `None`, the restructuring
          will be applied to all python files.
        - `in_file`: this argument has been deprecated; use
          `resources` instead.

        """
        if unsure in (True, False):
            warnings.warn(
                "unsure parameter should be a function that returns " "True or False",
                DeprecationWarning,
                stacklevel=2,
            )

            def unsure_func(value=unsure):
                return value

            unsure = unsure_func
        if in_file is not None:
            warnings.warn(
                "`in_file` argument has been deprecated; use `resources` " "instead. ",
                DeprecationWarning,
                stacklevel=2,
            )
            if in_file:
                resources = [self.resource]
        if _is_local(self.old_pyname):
            resources = [self.resource]
        if resources is None:
            resources = self.project.get_python_files()
        changes = ChangeSet(f"Renaming <{self.old_name}> to <{new_name}>")
        finder = occurrences.create_finder(
            self.project,
            self.old_name,
            self.old_pyname,
            unsure=unsure,
            docs=docs,
            instance=self.old_instance,
            in_hierarchy=in_hierarchy and self.is_method(),
        )
        job_set = task_handle.create_jobset("Collecting Changes", len(resources))
        for file_ in resources:
            job_set.started_job(file_.path)
            new_content = rename_in_module(finder, new_name, resource=file_)
            if new_content is not None:
                changes.add_change(ChangeContents(file_, new_content))
            job_set.finished_job()
        if self._is_renaming_a_module():
            resource = self.old_pyname.get_object().get_resource()
            if self._is_allowed_to_move(resources, resource):
                self._rename_module(resource, new_name, changes)
        return changes

    def _is_allowed_to_move(self, resources, resource):
        if resource.is_folder():
            try:
                return resource.get_child("__init__.py") in resources
            except exceptions.ResourceNotFoundError:
                return False
        else:
            return resource in resources

    def _is_renaming_a_module(self):
        return isinstance(self.old_pyname.get_object(), pyobjects.AbstractModule)

    def is_method(self):
        pyname = self.old_pyname
        return (
            isinstance(pyname, pynames.DefinedName)
            and isinstance(pyname.get_object(), pyobjects.PyFunction)
            and isinstance(pyname.get_object().parent, pyobjects.PyClass)
        )

    def _rename_module(self, resource, new_name, changes):
        if not resource.is_folder():
            new_name = new_name + ".py"
        parent_path = resource.parent.path
        if parent_path == "":
            new_location = new_name
        else:
            new_location = parent_path + "/" + new_name
        changes.add_change(MoveResource(resource, new_location))


class ChangeOccurrences:
    """A class for changing the occurrences of a name in a scope

    This class replaces the occurrences of a name.  Note that it only
    changes the scope containing the offset passed to the constructor.
    What's more it does not have any side-effects.  That is for
    example changing occurrences of a module does not rename the
    module; it merely replaces the occurrences of that module in a
    scope with the given expression.  This class is useful for
    performing many custom refactorings.

    """

    def __init__(self, project, resource, offset):
        self.project = project
        self.resource = resource
        self.offset = offset
        self.old_name = worder.get_name_at(resource, offset)
        self.pymodule = project.get_pymodule(self.resource)
        self.old_pyname = evaluate.eval_location(self.pymodule, offset)

    def get_old_name(self):
        word_finder = worder.Worder(self.resource.read())
        return word_finder.get_primary_at(self.offset)

    def _get_scope_offset(self):
        scope = self.pymodule.get_scope().get_inner_scope_for_offset(self.offset)
        return scope.get_region()

    def get_changes(self, new_name, only_calls=False, reads=True, writes=True):
        changes = ChangeSet(f"Changing <{self.old_name}> occurrences to <{new_name}>")
        scope_start, scope_end = self._get_scope_offset()
        finder = occurrences.create_finder(
            self.project,
            self.old_name,
            self.old_pyname,
            imports=False,
            only_calls=only_calls,
        )
        new_contents = rename_in_module(
            finder,
            new_name,
            pymodule=self.pymodule,
            replace_primary=True,
            region=(scope_start, scope_end),
            reads=reads,
            writes=writes,
        )
        if new_contents is not None:
            changes.add_change(ChangeContents(self.resource, new_contents))
        return changes


def rename_in_module(
    occurrences_finder,
    new_name,
    resource=None,
    pymodule=None,
    replace_primary=False,
    region=None,
    reads=True,
    writes=True,
):
    """Returns the changed source or `None` if there is no changes"""
    if resource is not None:
        source_code = resource.read()
    else:
        source_code = pymodule.source_code
    change_collector = codeanalyze.ChangeCollector(source_code)
    for occurrence in occurrences_finder.find_occurrences(resource, pymodule):
        if replace_primary and occurrence.is_a_fixed_primary():
            continue
        if replace_primary:
            start, end = occurrence.get_primary_range()
        else:
            start, end = occurrence.get_word_range()
        if (not reads and not occurrence.is_written()) or (
            not writes and occurrence.is_written()
        ):
            continue
        if region is None or region[0] <= start < region[1]:
            change_collector.add_change(start, end, new_name)
    return change_collector.get_changed()


def _is_local(pyname):
    module, lineno = pyname.get_definition_location()
    if lineno is None:
        return False
    scope = module.get_scope().get_inner_scope_for_line(lineno)
    if isinstance(pyname, pynames.DefinedName) and scope.get_kind() in (
        "Function",
        "Class",
    ):
        scope = scope.parent
    return (
        scope.get_kind() == "Function"
        and pyname in scope.get_names().values()
        and isinstance(pyname, pynames.AssignedName)
    )
