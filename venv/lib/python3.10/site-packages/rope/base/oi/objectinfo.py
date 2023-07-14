import warnings

from rope.base import exceptions, resourceobserver
from rope.base.oi import memorydb, objectdb, transform


class ObjectInfoManager:
    """Stores object information

    It uses an instance of `objectdb.ObjectDB` for storing
    information.

    """

    def __init__(self, project):
        self.project = project
        self.to_textual = transform.PyObjectToTextual(project)
        self.to_pyobject = transform.TextualToPyObject(project)
        self.doi_to_pyobject = transform.DOITextualToPyObject(project)
        self._init_objectdb()
        if project.prefs.get("validate_objectdb", False):
            self._init_validation()

    def _init_objectdb(self):
        dbtype = self.project.get_prefs().get("objectdb_type", None)
        persist = None
        if dbtype is not None:
            warnings.warn(
                '"objectdb_type" project config is deprecated;\n'
                'Use "save_objectdb" instead in your project '
                'config file.\n(".ropeproject/config.py" by default)\n',
                DeprecationWarning,
            )
            if dbtype != "memory" and self.project.ropefolder is not None:
                persist = True
        self.validation = TextualValidation(self.to_pyobject)
        db = memorydb.MemoryDB(self.project, persist=persist)
        self.objectdb = objectdb.ObjectDB(db, self.validation)

    def _init_validation(self):
        self.objectdb.validate_files()
        observer = resourceobserver.ResourceObserver(
            changed=self._resource_changed,
            moved=self._resource_moved,
            removed=self._resource_moved,
        )
        files = []
        for path in self.objectdb.get_files():
            resource = self.to_pyobject.path_to_resource(path)
            if resource is not None and resource.project == self.project:
                files.append(resource)
        self.observer = resourceobserver.FilteredResourceObserver(observer, files)
        self.objectdb.add_file_list_observer(_FileListObserver(self))
        self.project.add_observer(self.observer)

    def _resource_changed(self, resource):
        try:
            self.objectdb.validate_file(self.to_textual.resource_to_path(resource))
        except exceptions.ModuleSyntaxError:
            pass

    def _resource_moved(self, resource, new_resource=None):
        self.observer.remove_resource(resource)
        if new_resource is not None:
            old = self.to_textual.resource_to_path(resource)
            new = self.to_textual.resource_to_path(new_resource)
            self.objectdb.file_moved(old, new)
            self.observer.add_resource(new_resource)

    def get_returned(self, pyobject, args):
        result = self.get_exact_returned(pyobject, args)
        if result is not None:
            return result
        path, key = self._get_scope(pyobject)
        if path is None:
            return None
        for call_info in self.objectdb.get_callinfos(path, key):
            returned = call_info.get_returned()
            if returned and returned[0] not in ("unknown", "none"):
                result = returned
                break
            if result is None:
                result = returned
        if result is not None:
            return self.to_pyobject(result)

    def get_exact_returned(self, pyobject, args):
        path, key = self._get_scope(pyobject)
        if path is not None:
            returned = self.objectdb.get_returned(
                path, key, self._args_to_textual(pyobject, args)
            )
            if returned is not None:
                return self.to_pyobject(returned)

    def _args_to_textual(self, pyfunction, args):
        parameters = list(pyfunction.get_param_names(special_args=False))
        arguments = args.get_arguments(parameters)[: len(parameters)]
        textual_args = tuple(self.to_textual(arg) for arg in arguments)
        return textual_args

    def get_parameter_objects(self, pyobject):
        path, key = self._get_scope(pyobject)
        if path is None:
            return None
        arg_count = len(pyobject.get_param_names(special_args=False))
        unknowns = arg_count
        parameters = [None] * arg_count
        for call_info in self.objectdb.get_callinfos(path, key):
            args = call_info.get_parameters()
            for index, arg in enumerate(args[:arg_count]):
                old = parameters[index]
                if self.validation.is_more_valid(arg, old):
                    parameters[index] = arg
                    if self.validation.is_value_valid(arg):
                        unknowns -= 1
            if unknowns == 0:
                break
        if unknowns < arg_count:
            return [self.to_pyobject(parameter) for parameter in parameters]

    def get_passed_objects(self, pyfunction, parameter_index):
        path, key = self._get_scope(pyfunction)
        if path is None:
            return []
        result = []
        for call_info in self.objectdb.get_callinfos(path, key):
            args = call_info.get_parameters()
            if len(args) > parameter_index:
                parameter = self.to_pyobject(args[parameter_index])
                if parameter is not None:
                    result.append(parameter)
        return result

    def doa_data_received(self, data):
        def doi_to_normal(textual):
            pyobject = self.doi_to_pyobject(textual)
            return self.to_textual(pyobject)

        function = doi_to_normal(data[0])
        args = tuple(doi_to_normal(textual) for textual in data[1])
        returned = doi_to_normal(data[2])
        if function[0] == "defined" and len(function) == 3:
            self._save_data(function, args, returned)

    def function_called(self, pyfunction, params, returned=None):
        function_text = self.to_textual(pyfunction)
        params_text = tuple(self.to_textual(param) for param in params)
        returned_text = ("unknown",)
        if returned is not None:
            returned_text = self.to_textual(returned)
        self._save_data(function_text, params_text, returned_text)

    def save_per_name(self, scope, name, data):
        path, key = self._get_scope(scope.pyobject)
        if path is not None:
            self.objectdb.add_pername(path, key, name, self.to_textual(data))

    def get_per_name(self, scope, name):
        path, key = self._get_scope(scope.pyobject)
        if path is not None:
            result = self.objectdb.get_pername(path, key, name)
            if result is not None:
                return self.to_pyobject(result)

    def _save_data(self, function, args, returned=("unknown",)):
        self.objectdb.add_callinfo(function[1], function[2], args, returned)

    def _get_scope(self, pyobject):
        resource = pyobject.get_module().get_resource()
        if resource is None:
            return None, None
        textual = self.to_textual(pyobject)
        if textual[0] == "defined":
            path = textual[1]
            if len(textual) == 3:
                key = textual[2]
            else:
                key = ""
            return path, key
        return None, None

    def sync(self):
        self.objectdb.sync()

    def __str__(self):
        return str(self.objectdb)


class TextualValidation:
    def __init__(self, to_pyobject):
        self.to_pyobject = to_pyobject

    def is_value_valid(self, value):
        # ???: Should none and unknown be considered valid?
        if value is None or value[0] in ("none", "unknown"):
            return False
        return self.to_pyobject(value) is not None

    def is_more_valid(self, new, old):
        if old is None:
            return True
        return new[0] not in ("unknown", "none")

    def is_file_valid(self, path):
        return self.to_pyobject.path_to_resource(path) is not None

    def is_scope_valid(self, path, key):
        if key == "":
            textual = ("defined", path)
        else:
            textual = ("defined", path, key)
        return self.to_pyobject(textual) is not None


class _FileListObserver:
    def __init__(self, object_info):
        self.object_info = object_info
        self.observer = self.object_info.observer
        self.to_pyobject = self.object_info.to_pyobject

    def removed(self, path):
        resource = self.to_pyobject.path_to_resource(path)
        if resource is not None:
            self.observer.remove_resource(resource)

    def added(self, path):
        resource = self.to_pyobject.path_to_resource(path)
        if resource is not None:
            self.observer.add_resource(resource)
