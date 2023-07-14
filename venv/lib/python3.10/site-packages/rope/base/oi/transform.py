"""Provides classes for persisting `PyObject`"""
import os
import re

import rope.base.builtins  # Use full qualification for clarity.
from rope.base import exceptions


class PyObjectToTextual:
    """For transforming `PyObject` to textual form

    This can be used for storing `PyObjects` in files.  Use
    `TextualToPyObject` for converting back.

    """

    def __init__(self, project):
        self.project = project

    def transform(self, pyobject):
        """Transform a `PyObject` to textual form"""
        if pyobject is None:
            return ("none",)
        object_type = type(pyobject)
        try:
            method = getattr(self, object_type.__name__ + "_to_textual")
            return method(pyobject)
        except AttributeError:
            return ("unknown",)

    def __call__(self, pyobject):
        return self.transform(pyobject)

    def PyObject_to_textual(self, pyobject):
        if isinstance(pyobject.get_type(), rope.base.pyobjects.AbstractClass):
            result = self.transform(pyobject.get_type())
            if result[0] == "defined":
                return ("instance", result)
            return result
        return ("unknown",)

    def PyFunction_to_textual(self, pyobject):
        return self._defined_to_textual(pyobject)

    def PyClass_to_textual(self, pyobject):
        return self._defined_to_textual(pyobject)

    def _defined_to_textual(self, pyobject):
        address = []
        while pyobject.parent is not None:
            address.insert(0, pyobject.get_name())
            pyobject = pyobject.parent
        return (
            "defined",
            self._get_pymodule_path(pyobject.get_module()),
            ".".join(address),
        )

    def PyModule_to_textual(self, pyobject):
        return ("defined", self._get_pymodule_path(pyobject))

    def PyPackage_to_textual(self, pyobject):
        return ("defined", self._get_pymodule_path(pyobject))

    def List_to_textual(self, pyobject):
        return ("builtin", "list", self.transform(pyobject.holding))

    def Dict_to_textual(self, pyobject):
        return (
            "builtin",
            "dict",
            self.transform(pyobject.keys),
            self.transform(pyobject.values),
        )

    def Tuple_to_textual(self, pyobject):
        objects = [
            self.transform(holding) for holding in pyobject.get_holding_objects()
        ]
        return tuple(["builtin", "tuple"] + objects)

    def Set_to_textual(self, pyobject):
        return ("builtin", "set", self.transform(pyobject.holding))

    def Iterator_to_textual(self, pyobject):
        return ("builtin", "iter", self.transform(pyobject.holding))

    def Generator_to_textual(self, pyobject):
        return ("builtin", "generator", self.transform(pyobject.holding))

    def Str_to_textual(self, pyobject):
        return ("builtin", "str")

    def File_to_textual(self, pyobject):
        return ("builtin", "file")

    def BuiltinFunction_to_textual(self, pyobject):
        return ("builtin", "function", pyobject.get_name())

    def _get_pymodule_path(self, pymodule):
        return self.resource_to_path(pymodule.get_resource())

    def resource_to_path(self, resource):
        if resource.project == self.project:
            return resource.path
        else:
            return resource.real_path


class TextualToPyObject:
    """For transforming textual form to `PyObject`"""

    def __init__(self, project, allow_in_project_absolutes=False):
        self.project = project

    def __call__(self, textual):
        return self.transform(textual)

    def transform(self, textual):
        """Transform an object from textual form to `PyObject`"""
        if textual is None:
            return None
        type = textual[0]
        try:
            method = getattr(self, type + "_to_pyobject")
            return method(textual)
        except AttributeError:
            return None

    def builtin_to_pyobject(self, textual):
        method = getattr(self, "builtin_%s_to_pyobject" % textual[1], None)
        if method is not None:
            return method(textual)

    def builtin_str_to_pyobject(self, textual):
        return rope.base.builtins.get_str()

    def builtin_list_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_list(holding)

    def builtin_dict_to_pyobject(self, textual):
        keys = self.transform(textual[2])
        values = self.transform(textual[3])
        return rope.base.builtins.get_dict(keys, values)

    def builtin_tuple_to_pyobject(self, textual):
        objects = [self.transform(holding) for holding in textual[2:]]
        return rope.base.builtins.get_tuple(*objects)

    def builtin_set_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_set(holding)

    def builtin_iter_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_iterator(holding)

    def builtin_generator_to_pyobject(self, textual):
        holding = self.transform(textual[2])
        return rope.base.builtins.get_generator(holding)

    def builtin_file_to_pyobject(self, textual):
        return rope.base.builtins.get_file()

    def builtin_function_to_pyobject(self, textual):
        if textual[2] in rope.base.builtins.builtins:
            return rope.base.builtins.builtins[textual[2]].get_object()

    def unknown_to_pyobject(self, textual):
        return None

    def none_to_pyobject(self, textual):
        return None

    def _module_to_pyobject(self, textual):
        path = textual[1]
        return self._get_pymodule(path)

    def _hierarchical_defined_to_pyobject(self, textual):
        path = textual[1]
        names = textual[2].split(".")
        pymodule = self._get_pymodule(path)
        pyobject = pymodule
        for name in names:
            if pyobject is None:
                return None
            if isinstance(pyobject, rope.base.pyobjects.PyDefinedObject):
                try:
                    pyobject = pyobject.get_scope()[name].get_object()
                except exceptions.NameNotFoundError:
                    return None
            else:
                return None
        return pyobject

    def defined_to_pyobject(self, textual):
        if len(textual) == 2 or textual[2] == "":
            return self._module_to_pyobject(textual)
        else:
            return self._hierarchical_defined_to_pyobject(textual)

    def instance_to_pyobject(self, textual):
        type = self.transform(textual[1])
        if type is not None:
            return rope.base.pyobjects.PyObject(type)

    def _get_pymodule(self, path):
        resource = self.path_to_resource(path)
        if resource is not None:
            return self.project.get_pymodule(resource)

    def path_to_resource(self, path):
        try:
            root = self.project.address
            if not os.path.isabs(path):
                return self.project.get_resource(path)
            if path == root or path.startswith(root + os.sep):
                # INFO: This is a project file; should not be absolute
                return None
            import rope.base.project

            return rope.base.project.get_no_project().get_resource(path)
        except exceptions.ResourceNotFoundError:
            return None


class DOITextualToPyObject(TextualToPyObject):
    """For transforming textual form to `PyObject`

    The textual form DOI uses is different from rope's standard
    textual form.  The reason is that we cannot find the needed
    information by analyzing live objects.  This class can be
    used to transform DOI textual form to `PyObject` and later
    we can convert it to standard textual form using
    `TextualToPyObject` class.

    """

    def _function_to_pyobject(self, textual):
        path = textual[1]
        lineno = int(textual[2])
        pymodule = self._get_pymodule(path)
        if pymodule is not None:
            scope = pymodule.get_scope()
            inner_scope = scope.get_inner_scope_for_line(lineno)
            return inner_scope.pyobject

    def _class_to_pyobject(self, textual):
        path, name = textual[1:]
        pymodule = self._get_pymodule(path)
        if pymodule is None:
            return None
        module_scope = pymodule.get_scope()
        suspected = None
        if name in module_scope.get_names():
            suspected = module_scope[name].get_object()
        if suspected is not None and isinstance(suspected, rope.base.pyobjects.PyClass):
            return suspected
        else:
            lineno = self._find_occurrence(name, pymodule.get_resource().read())
            if lineno is not None:
                inner_scope = module_scope.get_inner_scope_for_line(lineno)
                return inner_scope.pyobject

    def defined_to_pyobject(self, textual):
        if len(textual) == 2:
            return self._module_to_pyobject(textual)
        else:
            if textual[2].isdigit():
                result = self._function_to_pyobject(textual)
            else:
                result = self._class_to_pyobject(textual)
            if not isinstance(result, rope.base.pyobjects.PyModule):
                return result

    def _find_occurrence(self, name, source):
        pattern = re.compile(r"^\s*class\s*" + name + r"\b")
        lines = source.split("\n")
        for i in range(len(lines)):
            if pattern.match(lines[i]):
                return i + 1

    def path_to_resource(self, path):
        import rope.base.libutils

        relpath = rope.base.libutils.path_relative_to_project_root(self.project, path)
        if relpath is not None:
            path = relpath
        return super().path_to_resource(path)
