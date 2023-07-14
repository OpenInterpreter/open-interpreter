"""Files and folders in a project are represented as resource objects.

Files and folders are access through `Resource` objects. `Resource` has
two subclasses: `File` and `Folder`. What we care about is that
refactorings and `rope.base.change.Change`s use resources.

There are two options to create a `Resource` for a path in a project.
Note that in these examples `path` is the path to a file or folder
relative to the project's root. A project's root folder is represented
by an empty string.

  1) Use the `rope.base.Project.get_resource()` method. E.g.:

       myresource = myproject.get_resource(path)


  2) Use the `rope.base.libutils` module. `libutils` has a function
     named `path_to_resource()`. It takes a project and a path:

       from rope.base import libutils

       myresource = libutils.path_to_resource(myproject, path)

Once we have a `Resource`, we can retrieve information from it, like
getting the path relative to the project's root (via `path`), reading
from and writing to the resource, moving the resource, etc.
"""

import os
import re
import warnings
from pathlib import Path

from rope.base import change, exceptions, fscommands


class Resource:
    """Represents files and folders in a project"""

    def __init__(self, project, path):
        self.project = project
        self._path = path

    def __repr__(self):
        return '<{}.{} "{}" at {}>'.format(
            self.__class__.__module__,
            self.__class__.__name__,
            self.path,
            hex(id(self)),
        )

    def move(self, new_location):
        """Move resource to `new_location`"""
        self._perform_change(
            change.MoveResource(self, new_location),
            f"Moving <{self.path}> to <{new_location}>",
        )

    def remove(self):
        """Remove resource from the project"""
        self._perform_change(change.RemoveResource(self), "Removing <%s>" % self.path)

    def is_folder(self):
        """Return true if the resource is a folder"""

    def create(self):
        """Create this resource"""

    def exists(self):
        return os.path.exists(self.real_path)

    @property
    def parent(self):
        parent = "/".join(self.path.split("/")[0:-1])
        return self.project.get_folder(parent)

    @property
    def path(self):
        """Return the path of this resource relative to the project root

        The path is the list of parent directories separated by '/' followed
        by the resource name.
        """
        return self._path

    @property
    def name(self):
        """Return the name of this resource"""
        return self.path.split("/")[-1]

    @property
    def real_path(self):
        """Return the file system path of this resource"""
        return self.project._get_resource_path(self.path)

    @property
    def pathlib(self):
        """Return the file as a pathlib path."""
        return Path(self.real_path)

    def __eq__(self, obj):
        return self.__class__ == obj.__class__ and self.path == obj.path

    def __ne__(self, obj):
        return not self.__eq__(obj)

    def __hash__(self):
        return hash(self.path)

    def _perform_change(self, change_, description):
        changes = change.ChangeSet(description)
        changes.add_change(change_)
        self.project.do(changes)


class File(Resource):
    """Represents a file"""

    def __init__(self, project, name):
        self.newlines = None
        super().__init__(project, name)

    def read(self):
        data = self.read_bytes()
        try:
            content, self.newlines = fscommands.file_data_to_unicode(data)
            return content
        except UnicodeDecodeError as e:
            raise exceptions.ModuleDecodeError(self.path, e.reason)

    def read_bytes(self):
        if not hasattr(self.project.fscommands, "read"):
            warnings.warn(
                "FileSystemCommands should implement read() method",
                DeprecationWarning,
                stacklevel=2,
            )
            with open(self.real_path, "rb") as handle:
                return handle.read()
        return self.project.fscommands.read(self.real_path)

    def write(self, contents):
        try:
            if contents == self.read():
                return
        except OSError:
            pass
        self._perform_change(
            change.ChangeContents(self, contents), "Writing file <%s>" % self.path
        )

    def is_folder(self):
        return False

    def create(self):
        self.parent.create_file(self.name)


class Folder(Resource):
    """Represents a folder"""

    def __init__(self, project, name):
        super().__init__(project, name)

    def is_folder(self):
        return True

    def get_children(self):
        """Return the children of this folder"""
        try:
            children = os.listdir(self.real_path)
        except OSError:
            return []
        result = []
        for name in children:
            try:
                child = self.get_child(name)
            except exceptions.ResourceNotFoundError:
                continue
            if not self.project.is_ignored(child):
                result.append(self.get_child(name))
        return result

    def create_file(self, file_name):
        self._perform_change(
            change.CreateFile(self, file_name),
            "Creating file <%s>" % self._get_child_path(file_name),
        )
        return self.get_child(file_name)

    def create_folder(self, folder_name):
        self._perform_change(
            change.CreateFolder(self, folder_name),
            "Creating folder <%s>" % self._get_child_path(folder_name),
        )
        return self.get_child(folder_name)

    def _get_child_path(self, name):
        if self.path:
            return self.path + "/" + name
        else:
            return name

    def get_child(self, name):
        return self.project.get_resource(self._get_child_path(name))

    def has_child(self, name):
        try:
            self.get_child(name)
            return True
        except exceptions.ResourceNotFoundError:
            return False

    def get_files(self):
        return [
            resource for resource in self.get_children() if not resource.is_folder()
        ]

    def get_folders(self):
        return [resource for resource in self.get_children() if resource.is_folder()]

    def contains(self, resource):
        if self == resource:
            return False
        return self.path == "" or resource.path.startswith(self.path + "/")

    def create(self):
        self.parent.create_folder(self.name)


class _ResourceMatcher:
    def __init__(self):
        self.patterns = []
        self._compiled_patterns = []

    def set_patterns(self, patterns):
        """Specify which resources to match

        `patterns` is a `list` of `str` that can contain ``*`` and
        ``?`` signs for matching resource names.

        """
        self._compiled_patterns = None
        self.patterns = patterns

    def _add_pattern(self, pattern):
        re_pattern = (
            pattern.replace(".", "\\.")
            .replace("*", "[^/]*")
            .replace("?", "[^/]")
            .replace("//", "/(.*/)?")
        )
        re_pattern = "^(.*/)?" + re_pattern + "(/.*)?$"
        self.compiled_patterns.append(re.compile(re_pattern))

    def does_match(self, resource):
        for pattern in self.compiled_patterns:
            if pattern.match(resource.path):
                return True
        path = os.path.join(resource.project.address, *resource.path.split("/"))
        return os.path.islink(path)

    @property
    def compiled_patterns(self):
        if self._compiled_patterns is None:
            self._compiled_patterns = []
            for pattern in self.patterns:
                self._add_pattern(pattern)
        return self._compiled_patterns
