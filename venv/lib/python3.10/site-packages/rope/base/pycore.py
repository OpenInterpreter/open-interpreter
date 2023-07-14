import bisect
import contextlib
import difflib
import warnings

import rope.base.libutils
import rope.base.oi.doa
import rope.base.oi.objectinfo
import rope.base.oi.soa
import rope.base.resourceobserver
import rope.base.resources
from rope.base import builtins, exceptions, pyobjectsdef, stdmods, taskhandle, utils


class PyCore:
    def __init__(self, project):
        self.project = project
        self._init_resource_observer()
        self.cache_observers = []
        self.module_cache = _ModuleCache(self)
        self.extension_cache = _ExtensionCache(self)
        self.object_info = rope.base.oi.objectinfo.ObjectInfoManager(project)
        self._init_python_files()
        self._init_automatic_soa()

    def _init_python_files(self):
        self.python_matcher = None
        patterns = self.project.prefs.get("python_files", None)
        if patterns is not None:
            self.python_matcher = rope.base.resources._ResourceMatcher()
            self.python_matcher.set_patterns(patterns)

    def _init_resource_observer(self):
        callback = self._invalidate_resource_cache
        observer = rope.base.resourceobserver.ResourceObserver(
            changed=callback, moved=callback, removed=callback
        )
        self.observer = rope.base.resourceobserver.FilteredResourceObserver(observer)
        self.project.add_observer(self.observer)

    def _init_automatic_soa(self):
        if not self.automatic_soa:
            return
        callback = self._file_changed_for_soa
        observer = rope.base.resourceobserver.ResourceObserver(
            changed=callback, moved=callback, removed=callback
        )
        self.project.add_observer(observer)

    @property
    def automatic_soa(self):
        auto_soa = self.project.prefs.get("automatic_soi", None)
        return self.project.prefs.get("automatic_soa", auto_soa)

    def _file_changed_for_soa(self, resource, new_resource=None):
        old_contents = self.project.history.contents_before_current_change(resource)
        if old_contents is not None:
            perform_soa_on_changed_scopes(self.project, resource, old_contents)

    def is_python_file(self, resource):
        if resource.is_folder():
            return False
        if self.python_matcher is None:
            return resource.name.endswith(".py")
        return self.python_matcher.does_match(resource)

    @utils.deprecated("Use `project.get_module` instead")
    def get_module(self, name, folder=None):
        """Returns a `PyObject` if the module was found."""
        return self.project.get_module(name, folder)

    def _builtin_submodules(self, modname):
        result = {}
        for extension in self.extension_modules:
            if extension.startswith(modname + "."):
                name = extension[len(modname) + 1 :]
                if "." not in name:
                    result[name] = self.builtin_module(extension)
        return result

    def builtin_module(self, name):
        return self.extension_cache.get_pymodule(name)

    @utils.deprecated("Use `project.get_relative_module` instead")
    def get_relative_module(self, name, folder, level):
        return self.project.get_relative_module(name, folder, level)

    @utils.deprecated("Use `libutils.get_string_module` instead")
    def get_string_module(self, code, resource=None, force_errors=False):
        """Returns a `PyObject` object for the given code

        If `force_errors` is `True`, `exceptions.ModuleSyntaxError` is
        raised if module has syntax errors.  This overrides
        ``ignore_syntax_errors`` project config.

        """
        return pyobjectsdef.PyModule(self, code, resource, force_errors=force_errors)

    @utils.deprecated("Use `libutils.get_string_scope` instead")
    def get_string_scope(self, code, resource=None):
        """Returns a `Scope` object for the given code"""
        return rope.base.libutils.get_string_scope(code, resource)

    def _invalidate_resource_cache(self, resource, new_resource=None):
        for observer in self.cache_observers:
            observer(resource)

    @utils.deprecated("Use `project.get_python_path_folders` instead")
    def get_python_path_folders(self):
        return self.project.get_python_path_folders()

    @utils.deprecated("Use `project.find_module` instead")
    def find_module(self, modname, folder=None):
        """Returns a resource corresponding to the given module

        returns None if it can not be found
        """
        return self.project.find_module(modname, folder)

    @utils.deprecated("Use `project.find_relative_module` instead")
    def find_relative_module(self, modname, folder, level):
        return self.project.find_relative_module(modname, folder, level)

    # INFO: It was decided not to cache source folders, since:
    #  - Does not take much time when the root folder contains
    #    packages, that is most of the time
    #  - We need a separate resource observer; `self.observer`
    #    does not get notified about module and folder creations
    @utils.deprecated("Use `project.get_source_folders` instead")
    def get_source_folders(self):
        """Returns project source folders"""
        return self.project.get_source_folders()

    def resource_to_pyobject(self, resource, force_errors=False):
        return self.module_cache.get_pymodule(resource, force_errors)

    @utils.deprecated("Use `project.get_python_files` instead")
    def get_python_files(self):
        """Returns all python files available in the project"""
        return self.project.get_python_files()

    def _is_package(self, folder):
        return (
            folder.has_child("__init__.py")
            and not folder.get_child("__init__.py").is_folder()
        )

    def _find_source_folders(self, folder):
        for resource in folder.get_folders():
            if self._is_package(resource):
                return [folder]
        result = []
        for resource in folder.get_files():
            if resource.name.endswith(".py"):
                result.append(folder)
                break
        for resource in folder.get_folders():
            result.extend(self._find_source_folders(resource))
        return result

    def run_module(self, resource, args=None, stdin=None, stdout=None):
        """Run `resource` module

        Returns a `rope.base.oi.doa.PythonFileRunner` object for
        controlling the process.

        """
        perform_doa = self.project.prefs.get("perform_doi", True)
        perform_doa = self.project.prefs.get("perform_doa", perform_doa)
        receiver = self.object_info.doa_data_received
        if not perform_doa:
            receiver = None
        runner = rope.base.oi.doa.PythonFileRunner(
            self, resource, args, stdin, stdout, receiver
        )
        runner.add_finishing_observer(self.module_cache.forget_all_data)
        runner.run()
        return runner

    def analyze_module(
        self,
        resource,
        should_analyze=lambda py: True,
        search_subscopes=lambda py: True,
        followed_calls=None,
    ):
        """Analyze `resource` module for static object inference

        This function forces rope to analyze this module to collect
        information about function calls.  `should_analyze` is a
        function that is called with a `PyDefinedObject` argument.  If
        it returns `True` the element is analyzed.  If it is `None` or
        returns `False` the element is not analyzed.

        `search_subscopes` is like `should_analyze`; The difference is
        that if it returns `False` the sub-scopes are all ignored.
        That is it is assumed that `should_analyze` returns `False`
        for all of its subscopes.

        `followed_calls` override the value of ``soa_followed_calls``
        project config.
        """
        if followed_calls is None:
            followed_calls = self.project.prefs.get("soa_followed_calls", 0)
        pymodule = self.resource_to_pyobject(resource)
        self.module_cache.forget_all_data()
        rope.base.oi.soa.analyze_module(
            self, pymodule, should_analyze, search_subscopes, followed_calls
        )

    def get_classes(self, task_handle=taskhandle.DEFAULT_TASK_HANDLE):

        warnings.warn(
            "`PyCore.get_classes()` is deprecated", DeprecationWarning, stacklevel=2
        )
        return []

    def __str__(self):
        return str(self.module_cache) + str(self.object_info)

    @utils.deprecated("Use `libutils.modname` instead")
    def modname(self, resource):
        return rope.base.libutils.modname(resource)

    @property
    @utils.cacheit
    def extension_modules(self):
        result = set(self.project.prefs.get("extension_modules", []))
        if self.project.prefs.get("import_dynload_stdmods", False):
            result.update(stdmods.dynload_modules())
        return result


class _ModuleCache:
    def __init__(self, pycore):
        self.pycore = pycore
        self.module_map = {}
        self.pycore.cache_observers.append(self._invalidate_resource)
        self.observer = self.pycore.observer

    def _invalidate_resource(self, resource):
        if resource in self.module_map:
            self.forget_all_data()
            self.observer.remove_resource(resource)
            del self.module_map[resource]

    def get_pymodule(self, resource, force_errors=False):
        if resource in self.module_map:
            return self.module_map[resource]
        if resource.is_folder():
            result = pyobjectsdef.PyPackage(
                self.pycore,
                resource,
                force_errors=force_errors,
            )
        else:
            result = pyobjectsdef.PyModule(
                self.pycore,
                resource=resource,
                force_errors=force_errors,
            )
            if result.has_errors:
                return result
        self.module_map[resource] = result
        self.observer.add_resource(resource)
        return result

    def forget_all_data(self):
        for pymodule in self.module_map.values():
            pymodule._forget_concluded_data()

    def __str__(self):
        return "PyCore caches %d PyModules\n" % len(self.module_map)


class _ExtensionCache:
    def __init__(self, pycore):
        self.pycore = pycore
        self.extensions = {}

    def get_pymodule(self, name):
        if name == "__builtin__":
            return builtins.builtins
        allowed = self.pycore.extension_modules
        if name not in self.extensions and name in allowed:
            self.extensions[name] = builtins.BuiltinModule(name, self.pycore)
        return self.extensions.get(name)


def perform_soa_on_changed_scopes(project, resource, old_contents):
    pycore = project.pycore
    if resource.exists() and pycore.is_python_file(resource):
        with contextlib.suppress(exceptions.ModuleSyntaxError):
            new_contents = resource.read()
            # detecting changes in new_contents relative to old_contents
            detector = _TextChangeDetector(new_contents, old_contents)

            def search_subscopes(pydefined):
                scope = pydefined.get_scope()
                return detector.is_changed(scope.get_start(), scope.get_end())

            def should_analyze(pydefined):
                scope = pydefined.get_scope()
                start = scope.get_start()
                end = scope.get_end()
                return detector.consume_changes(start, end)

            pycore.analyze_module(resource, should_analyze, search_subscopes)


class _TextChangeDetector:
    def __init__(self, old, new):
        self.old = old
        self.new = new
        self._set_diffs()

    def _set_diffs(self):
        differ = difflib.Differ()
        self.lines = []
        lineno = 0
        for line in differ.compare(
            self.old.splitlines(True), self.new.splitlines(True)
        ):
            if line.startswith(" "):
                lineno += 1
            elif line.startswith("-"):
                lineno += 1
                self.lines.append(lineno)

    def is_changed(self, start, end):
        """Tell whether any of start till end lines have changed

        The end points are inclusive and indices start from 1.
        """
        left, right = self._get_changed(start, end)
        return left < right

    def consume_changes(self, start, end):
        """Clear the changed status of lines from start till end"""
        left, right = self._get_changed(start, end)
        if left < right:
            del self.lines[left:right]
        return left < right

    def _get_changed(self, start, end):
        left = bisect.bisect_left(self.lines, start)
        right = bisect.bisect_right(self.lines, end)
        return left, right
