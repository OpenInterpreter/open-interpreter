from __future__ import annotations

import typing

import rope.base.pyobjects
from rope.base import exceptions, utils

if typing.TYPE_CHECKING:
    from typing import Union

    from rope.base import pyobjectsdef


class PyName:
    """References to `PyObject` inside python programs"""

    def get_object(self):
        """Return the `PyObject` object referenced by this `PyName`"""

    def get_definition_location(self):
        """Return a (module, lineno) tuple"""


class DefinedName(PyName):
    def __init__(self, pyobject):
        self.pyobject = pyobject

    def get_object(self):
        return self.pyobject

    def get_definition_location(self):
        lineno = utils.guess_def_lineno(
            self.pyobject.get_module(), self.pyobject.get_ast()
        )
        return (self.pyobject.get_module(), lineno)


class AssignedName(PyName):
    pass


class UnboundName(PyName):
    def __init__(self, pyobject=None):
        self.pyobject = pyobject
        if self.pyobject is None:
            self.pyobject = rope.base.pyobjects.get_unknown()

    def get_object(self):
        return self.pyobject

    def get_definition_location(self):
        return (None, None)


class AssignmentValue:
    """An assigned expression"""

    def __init__(
        self, ast_node, levels=None, evaluation="", assign_type=False, type_hint=None
    ):
        """The `level` is `None` for simple assignments and is
        a list of numbers for tuple assignments for example in::

           a, (b, c) = x

        The levels for for `a` is ``[0]``, for `b` is ``[1, 0]`` and for
        `c` is ``[1, 1]``.

        """
        self.ast_node = ast_node
        if levels is None:
            self.levels = []
        else:
            self.levels = levels
        self.evaluation = evaluation
        self.assign_type = assign_type
        self.type_hint = type_hint

    def get_lineno(self):
        return self.ast_node.lineno


class EvaluatedName(PyName):
    """A name whose object will be evaluated later"""

    def __init__(self, callback, module=None, lineno=None):
        self.module = module
        self.lineno = lineno
        self.callback = callback
        self.pyobject = _Inferred(callback, _get_concluded_data(module))

    def get_object(self):
        return self.pyobject.get()

    def get_definition_location(self):
        return (self.module, self.lineno)

    def invalidate(self):
        """Forget the `PyObject` this `PyName` holds"""
        self.pyobject.set(None)


class ParameterName(PyName):
    pass


class ImportedModule(PyName):
    def __init__(
        self,
        importing_module: Union[
            pyobjectsdef.PyModule,
            pyobjectsdef.PyPackage,
        ],
        module_name=None,
        level=0,
        resource=None,
    ):
        assert (
            module_name is not None or resource is not None
        ), "At least one of module_name or resource must be set"
        self.importing_module = importing_module
        self.module_name = module_name
        self.level = level
        self.resource = resource
        self.pymodule = _get_concluded_data(self.importing_module)

    def _current_folder(self):
        resource = self.importing_module.get_module().get_resource()
        if resource is None:
            return None
        return resource.parent

    def _get_pymodule(self):
        if self.pymodule.get() is None:
            pycore = self.importing_module.pycore
            if self.resource is not None:
                self.pymodule.set(pycore.project.get_pymodule(self.resource))
            else:
                try:
                    if self.level == 0:
                        pymodule = pycore.project.get_module(
                            self.module_name, self._current_folder()
                        )
                    else:
                        pymodule = pycore.project.get_relative_module(
                            self.module_name, self._current_folder(), self.level
                        )
                    self.pymodule.set(pymodule)
                except exceptions.ModuleNotFoundError:
                    pass
        return self.pymodule.get()

    def get_object(self):
        if self._get_pymodule() is None:
            return rope.base.pyobjects.get_unknown()
        return self._get_pymodule()

    def get_definition_location(self):
        pymodule = self._get_pymodule()
        if not isinstance(pymodule, rope.base.pyobjects.PyDefinedObject):
            return (None, None)
        return (pymodule.get_module(), 1)


class ImportedName(PyName):
    def __init__(self, imported_module, imported_name):
        self.imported_module = imported_module
        self.imported_name = imported_name

    def _get_imported_pyname(self):
        try:
            result = self.imported_module.get_object()[self.imported_name]
            if result != self:
                return result
        except exceptions.AttributeNotFoundError:
            pass
        return UnboundName()

    @utils.prevent_recursion(rope.base.pyobjects.get_unknown)
    def get_object(self):
        return self._get_imported_pyname().get_object()

    @utils.prevent_recursion(lambda: (None, None))
    def get_definition_location(self):
        return self._get_imported_pyname().get_definition_location()


def _get_concluded_data(module):
    if module is None:
        return rope.base.pyobjects._ConcludedData()
    return module._get_concluded_data()


def _circular_inference():
    raise rope.base.pyobjects.IsBeingInferredError("Circular Object Inference")


class _Inferred:
    def __init__(self, get_inferred, concluded=None):
        self.get_inferred = get_inferred
        self.concluded = concluded
        if self.concluded is None:
            self.temp = None

    @utils.prevent_recursion(_circular_inference)
    def get(self, *args, **kwds):
        if self.concluded is None or self.concluded.get() is None:
            self.set(self.get_inferred(*args, **kwds))
        if self._get() is None:
            self.set(rope.base.pyobjects.get_unknown())
        return self._get()

    def set(self, pyobject):
        if self.concluded is not None:
            self.concluded.set(pyobject)
        self.temp = pyobject

    def _get(self):
        if self.concluded is not None:
            return self.concluded.get()
        return self.temp
