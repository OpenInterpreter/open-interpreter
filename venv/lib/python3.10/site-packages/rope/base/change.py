import datetime
import difflib
import os
import time
from typing import Union

import rope.base.fscommands
from rope.base import exceptions, taskhandle, utils
from rope.base.fscommands import FileContent


class Change:
    """The base class for changes

    Rope refactorings return `Change` objects.  They can be previewed,
    committed or undone.
    """

    def do(self, job_set=None):
        """Perform the change

        .. note:: Do use this directly.  Use `Project.do()` instead.
        """

    def undo(self, job_set=None):
        """Perform the change

        .. note:: Do use this directly.  Use `History.undo()` instead.
        """

    def get_description(self):
        """Return the description of this change

        This can be used for previewing the changes.
        """
        return str(self)

    def get_changed_resources(self):
        """Return the list of resources that will be changed"""
        return []

    @property
    @utils.saveit
    def _operations(self):
        return _ResourceOperations(self.resource.project)


class ChangeSet(Change):
    """A collection of `Change` objects

    This class holds a collection of changes.  This class provides
    these fields:

    * `changes`: the list of changes
    * `description`: the goal of these changes
    """

    def __init__(self, description, timestamp=None):
        self.changes = []
        self.description = description
        self.time = timestamp

    def do(self, job_set=taskhandle.DEFAULT_JOB_SET):
        try:
            done = []
            for change in self.changes:
                change.do(job_set)
                done.append(change)
            self.time = time.time()
        except Exception:
            for change in done:
                change.undo()
            raise

    def undo(self, job_set=taskhandle.DEFAULT_JOB_SET):
        try:
            done = []
            for change in reversed(self.changes):
                change.undo(job_set)
                done.append(change)
        except Exception:
            for change in done:
                change.do()
            raise

    def add_change(self, change):
        self.changes.append(change)

    def get_description(self):
        result = [str(self) + ":\n\n\n"]
        for change in self.changes:
            result.append(change.get_description())
            result.append("\n")
        return "".join(result)

    def __str__(self):
        if self.time is not None:
            date = datetime.datetime.fromtimestamp(self.time)
            if date.date() == datetime.date.today():
                string_date = "today"
            elif date.date() == (datetime.date.today() - datetime.timedelta(1)):
                string_date = "yesterday"
            elif date.year == datetime.date.today().year:
                string_date = date.strftime("%b %d")
            else:
                string_date = date.strftime("%d %b, %Y")
            string_time = date.strftime("%H:%M:%S")
            string_time = f"{string_date} {string_time} "
            return self.description + " - " + string_time
        return self.description

    def get_changed_resources(self):
        result = set()
        for change in self.changes:
            result.update(change.get_changed_resources())
        return result


def _handle_job_set(function):
    """A decorator for handling `taskhandle.JobSet`

    A decorator for handling `taskhandle.JobSet` for `do` and `undo`
    methods of `Change`.
    """

    def call(self, job_set=taskhandle.DEFAULT_JOB_SET):
        job_set.started_job(str(self))
        function(self)
        job_set.finished_job()

    return call


class ChangeContents(Change):
    """A class to change the contents of a file

    Fields:

    * `resource`: The `rope.base.resources.File` to change
    * `new_contents`: What to write in the file
    """

    def __init__(self, resource, new_contents, old_contents=None):
        self.resource = resource
        # IDEA: Only saving diffs; possible problems when undo/redoing
        self.new_contents = new_contents
        self.old_contents = old_contents

    @_handle_job_set
    def do(self):
        if self.old_contents is None:
            self.old_contents = self.resource.read()
        self._operations.write_file(self.resource, self.new_contents)

    @_handle_job_set
    def undo(self):
        if self.old_contents is None:
            raise exceptions.HistoryError("Undoing a change that is not performed yet!")
        self._operations.write_file(self.resource, self.old_contents)

    def __str__(self):
        return "Change <%s>" % self.resource.path

    def get_description(self):
        new = self.new_contents
        old = self.old_contents
        if old is None:
            if self.resource.exists():
                old = self.resource.read()
            else:
                old = ""
        result = difflib.unified_diff(
            old.splitlines(True),
            new.splitlines(True),
            "a/" + self.resource.path,
            "b/" + self.resource.path,
        )
        return "".join(list(result))

    def get_changed_resources(self):
        return [self.resource]


class MoveResource(Change):
    """Move a resource to a new location

    Fields:

    * `resource`: The `rope.base.resources.Resource` to move
    * `new_resource`: The destination for move; It is the moved
      resource not the folder containing that resource.
    """

    def __init__(self, resource, new_location, exact=False):
        self.project = resource.project
        self.resource = resource
        if not exact:
            new_location = _get_destination_for_move(resource, new_location)
        if resource.is_folder():
            self.new_resource = self.project.get_folder(new_location)
        else:
            self.new_resource = self.project.get_file(new_location)

    @_handle_job_set
    def do(self):
        self._operations.move(self.resource, self.new_resource)

    @_handle_job_set
    def undo(self):
        self._operations.move(self.new_resource, self.resource)

    def __str__(self):
        return "Move <%s>" % self.resource.path

    def get_description(self):
        return "rename from {}\nrename to {}".format(
            self.resource.path,
            self.new_resource.path,
        )

    def get_changed_resources(self):
        return [self.resource, self.new_resource]


class CreateResource(Change):
    """A class to create a resource

    Fields:

    * `resource`: The resource to create
    """

    def __init__(self, resource):
        self.resource = resource

    @_handle_job_set
    def do(self):
        self._operations.create(self.resource)

    @_handle_job_set
    def undo(self):
        self._operations.remove(self.resource)

    def __str__(self):
        return "Create Resource <%s>" % (self.resource.path)

    def get_description(self):
        return "new file %s" % (self.resource.path)

    def get_changed_resources(self):
        return [self.resource]

    def _get_child_path(self, parent, name):
        if parent.path == "":
            return name
        else:
            return parent.path + "/" + name


class CreateFolder(CreateResource):
    """A class to create a folder

    See docs for `CreateResource`.
    """

    def __init__(self, parent, name):
        resource = parent.project.get_folder(self._get_child_path(parent, name))
        super().__init__(resource)


class CreateFile(CreateResource):
    """A class to create a file

    See docs for `CreateResource`.
    """

    def __init__(self, parent, name):
        resource = parent.project.get_file(self._get_child_path(parent, name))
        super().__init__(resource)


class RemoveResource(Change):
    """A class to remove a resource

    Fields:

    * `resource`: The resource to be removed
    """

    def __init__(self, resource):
        self.resource = resource

    @_handle_job_set
    def do(self):
        self._operations.remove(self.resource)

    # TODO: Undoing remove operations
    @_handle_job_set
    def undo(self):
        raise NotImplementedError("Undoing `RemoveResource` is not implemented yet.")

    def __str__(self):
        return "Remove <%s>" % (self.resource.path)

    def get_changed_resources(self):
        return [self.resource]


def count_changes(change):
    """Counts the number of basic changes a `Change` will make"""
    if isinstance(change, ChangeSet):
        result = 0
        for child in change.changes:
            result += count_changes(child)
        return result
    return 1


def create_job_set(task_handle, change):
    return task_handle.create_jobset(str(change), count_changes(change))


class _ResourceOperations:
    def __init__(self, project):
        self.project = project
        self.fscommands = project.fscommands
        self.direct_commands = rope.base.fscommands.FileSystemCommands()

    def _get_fscommands(self, resource):
        if self.project.is_ignored(resource):
            return self.direct_commands
        return self.fscommands

    def write_file(self, resource, contents: Union[str, FileContent]):
        data: FileContent
        if not isinstance(contents, bytes):
            data = rope.base.fscommands.unicode_to_file_data(
                contents,
                newlines=resource.newlines,
            )
        else:
            data = contents
        fscommands = self._get_fscommands(resource)
        fscommands.write(resource.real_path, data)
        for observer in list(self.project.observers):
            observer.resource_changed(resource)

    def move(self, resource, new_resource):
        fscommands = self._get_fscommands(resource)
        fscommands.move(resource.real_path, new_resource.real_path)
        for observer in list(self.project.observers):
            observer.resource_moved(resource, new_resource)

    def create(self, resource):
        if resource.is_folder():
            self._create_resource(resource.path, kind="folder")
        else:
            self._create_resource(resource.path)
        for observer in list(self.project.observers):
            observer.resource_created(resource)

    def remove(self, resource):
        fscommands = self._get_fscommands(resource)
        fscommands.remove(resource.real_path)
        for observer in list(self.project.observers):
            observer.resource_removed(resource)

    def _create_resource(self, file_name, kind="file"):
        resource_path = self.project._get_resource_path(file_name)
        if os.path.exists(resource_path):
            raise exceptions.RopeError("Resource <%s> already exists" % resource_path)
        resource = self.project.get_file(file_name)
        if not resource.parent.exists():
            raise exceptions.ResourceNotFoundError(
                "Parent folder of <%s> does not exist" % resource.path
            )
        fscommands = self._get_fscommands(resource)
        try:
            if kind == "file":
                fscommands.create_file(resource_path)
            else:
                fscommands.create_folder(resource_path)
        except OSError as e:
            raise exceptions.RopeError(e)


def _get_destination_for_move(resource, destination):
    dest_path = resource.project._get_resource_path(destination)
    if os.path.isdir(dest_path):
        if destination != "":
            return destination + "/" + resource.name
        else:
            return resource.name
    return destination


class ChangeToData:
    def convertChangeSet(self, change):
        description = change.description
        changes = [self(child) for child in change.changes]
        return (description, changes, change.time)

    def convertChangeContents(self, change):
        return (change.resource.path, change.new_contents, change.old_contents)

    def convertMoveResource(self, change):
        return (change.resource.path, change.new_resource.path)

    def convertCreateResource(self, change):
        return (change.resource.path, change.resource.is_folder())

    def convertRemoveResource(self, change):
        return (change.resource.path, change.resource.is_folder())

    def __call__(self, change):
        change_type = type(change)
        if change_type in (CreateFolder, CreateFile):
            change_type = CreateResource
        method = getattr(self, "convert" + change_type.__name__)
        return (change_type.__name__, method(change))


class DataToChange:
    def __init__(self, project):
        self.project = project

    def makeChangeSet(self, description, changes, time=None):
        result = ChangeSet(description, time)
        for child in changes:
            result.add_change(self(child))
        return result

    def makeChangeContents(self, path, new_contents, old_contents):
        resource = self.project.get_file(path)
        return ChangeContents(resource, new_contents, old_contents)

    def makeMoveResource(self, old_path, new_path):
        resource = self.project.get_file(old_path)
        return MoveResource(resource, new_path, exact=True)

    def makeCreateResource(self, path, is_folder):
        if is_folder:
            resource = self.project.get_folder(path)
        else:
            resource = self.project.get_file(path)
        return CreateResource(resource)

    def makeRemoveResource(self, path, is_folder):
        if is_folder:
            resource = self.project.get_folder(path)
        else:
            resource = self.project.get_file(path)
        return RemoveResource(resource)

    def __call__(self, data):
        method = getattr(self, "make" + data[0])
        return method(*data[1])
