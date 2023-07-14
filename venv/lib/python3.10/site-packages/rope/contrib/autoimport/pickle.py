"""
IMPORTANT: This is a deprecated implementation of autoimport using pickle-based
storage.

This pickle-based autoimport is provided only for backwards compatibility
purpose and will be removed and the sqlite backend will be the new default
implementation in the future.

If you are still using this module, you should migrate to the new and improved
sqlite-based storage backend (rope.contrib.autoimport.sqlite.AutoImport).
"""


import contextlib
import re

from rope.base import (
    builtins,
    exceptions,
    libutils,
    pynames,
    pyobjects,
    resourceobserver,
    resources,
    taskhandle,
)
from rope.refactor import importutils


class AutoImport:
    """A class for finding the module that provides a name

    This class maintains a cache of global names in python modules.
    Note that this cache is not accurate and might be out of date.

    """

    def __init__(self, project, observe=True, underlined=False):
        """Construct an AutoImport object

        If `observe` is `True`, listen for project changes and update
        the cache.

        If `underlined` is `True`, underlined names are cached, too.
        """
        self.project = project
        self.underlined = underlined
        self.names = project.data_files.read_data("globalnames")
        if self.names is None:
            self.names = {}
        project.data_files.add_write_hook(self._write)
        # XXX: using a filtered observer
        observer = resourceobserver.ResourceObserver(
            changed=self._changed, moved=self._moved, removed=self._removed
        )
        if observe:
            project.add_observer(observer)

    def import_assist(self, starting):
        """Return a list of ``(name, module)`` tuples

        This function tries to find modules that have a global name
        that starts with `starting`.
        """
        # XXX: breaking if gave up! use generators
        result = []
        for module in self.names:
            result.extend(
                (global_name, module)
                for global_name in self.names[module]
                if global_name.startswith(starting)
            )

        return result

    def get_modules(self, name):
        """Return the list of modules that have global `name`"""
        return [module for module in self.names if name in self.names[module]]

    def get_all_names(self):
        """Return the list of all cached global names"""
        result = set()
        for module in self.names:
            result.update(set(self.names[module]))
        return result

    def get_name_locations(self, name):
        """Return a list of ``(resource, lineno)`` tuples"""
        result = []
        for module in self.names:
            if name in self.names[module]:
                with contextlib.suppress(exceptions.ModuleNotFoundError):
                    pymodule = self.project.get_module(module)
                    if name in pymodule:
                        pyname = pymodule[name]
                        module, lineno = pyname.get_definition_location()
                        if module is not None:
                            resource = module.get_module().get_resource()
                            if resource is not None and lineno is not None:
                                result.append((resource, lineno))
        return result

    def generate_cache(
        self,
        resources=None,
        underlined=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Generate global name cache for project files

        If `resources` is a list of `rope.base.resource.File`, only
        those files are searched; otherwise all python modules in the
        project are cached.

        """
        if resources is None:
            resources = self.project.get_python_files()
        job_set = task_handle.create_jobset(
            "Generating autoimport cache", len(resources)
        )
        for file in resources:
            job_set.started_job("Working on <%s>" % file.path)
            self.update_resource(file, underlined)
            job_set.finished_job()

    def generate_modules_cache(
        self, modules, underlined=None, task_handle=taskhandle.DEFAULT_TASK_HANDLE
    ):
        """Generate global name cache for modules listed in `modules`"""
        job_set = task_handle.create_jobset(
            "Generating autoimport cache for modules", len(modules)
        )
        for modname in modules:
            job_set.started_job("Working on <%s>" % modname)
            if modname.endswith(".*"):
                mod = self.project.find_module(modname[:-2])
                if mod:
                    for sub in submodules(mod):
                        self.update_resource(sub, underlined)
            else:
                self.update_module(modname, underlined)
            job_set.finished_job()

    def clear_cache(self):
        """Clear all entries in global-name cache

        It might be a good idea to use this function before
        regenerating global names.

        """
        self.names.clear()

    def find_insertion_line(self, code):
        """Guess at what line the new import should be inserted"""
        match = re.search(r"^(def|class)\s+", code)
        if match is not None:
            code = code[: match.start()]
        try:
            pymodule = libutils.get_string_module(self.project, code)
        except exceptions.ModuleSyntaxError:
            return 1
        testmodname = "__rope_testmodule_rope"
        importinfo = importutils.NormalImport(((testmodname, None),))
        module_imports = importutils.get_module_imports(self.project, pymodule)
        module_imports.add_import(importinfo)
        code = module_imports.get_changed_source()
        offset = code.index(testmodname)
        lineno = code.count("\n", 0, offset) + 1
        return lineno

    def update_resource(self, resource, underlined=None):
        """Update the cache for global names in `resource`"""
        with contextlib.suppress(exceptions.ModuleSyntaxError):
            pymodule = self.project.get_pymodule(resource)
            modname = self._module_name(resource)
            self._add_names(pymodule, modname, underlined)

    def update_module(self, modname, underlined=None):
        """Update the cache for global names in `modname` module

        `modname` is the name of a module.
        """
        with contextlib.suppress(exceptions.ModuleNotFoundError):
            pymodule = self.project.get_module(modname)
            self._add_names(pymodule, modname, underlined)

    def _module_name(self, resource):
        return libutils.modname(resource)

    def _add_names(self, pymodule, modname, underlined):
        if underlined is None:
            underlined = self.underlined
        globals = []
        if isinstance(pymodule, pyobjects.PyDefinedObject):
            attributes = pymodule._get_structural_attributes()
        else:
            attributes = pymodule.get_attributes()
        for name, pyname in attributes.items():
            if not underlined and name.startswith("_"):
                continue
            if isinstance(pyname, (pynames.AssignedName, pynames.DefinedName)):
                globals.append(name)
            if isinstance(pymodule, builtins.BuiltinModule):
                globals.append(name)
        self.names[modname] = globals

    def _write(self):
        self.project.data_files.write_data("globalnames", self.names)

    def _changed(self, resource):
        if not resource.is_folder():
            self.update_resource(resource)

    def _moved(self, resource, newresource):
        if not resource.is_folder():
            modname = self._module_name(resource)
            if modname in self.names:
                del self.names[modname]
            self.update_resource(newresource)

    def _removed(self, resource):
        if not resource.is_folder():
            modname = self._module_name(resource)
            if modname in self.names:
                del self.names[modname]


def submodules(mod):
    if isinstance(mod, resources.File):
        if mod.name.endswith(".py") and mod.name != "__init__.py":
            return {mod}
        return set()
    if not mod.has_child("__init__.py"):
        return set()
    result = {mod}
    for child in mod.get_children():
        result |= submodules(child)
    return result
