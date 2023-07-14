import contextlib

import rope.base.oi.soi
import rope.base.pyobjects
from rope.base import pynames, utils


class DefinedName(pynames.DefinedName):
    pass


class AssignedName(pynames.AssignedName):
    def __init__(self, lineno=None, module=None, pyobject=None):
        self.lineno = lineno
        self.module = module
        self.assignments = []
        self.pyobject = _Inferred(
            self._get_inferred, pynames._get_concluded_data(module)
        )
        self.pyobject.set(pyobject)

    @utils.prevent_recursion(lambda: None)
    def _get_inferred(self):
        if self.module is not None:
            return rope.base.oi.soi.infer_assigned_object(self)

    def get_object(self):
        return self.pyobject.get()

    def get_definition_location(self):
        """Returns a (module, lineno) tuple"""
        if self.lineno is None and self.assignments:
            with contextlib.suppress(AttributeError):
                self.lineno = self.assignments[0].get_lineno()
        return (self.module, self.lineno)

    def invalidate(self):
        """Forget the `PyObject` this `PyName` holds"""
        self.pyobject.set(None)


class UnboundName(pynames.UnboundName):
    pass


class ParameterName(pynames.ParameterName):
    def __init__(self, pyfunction, index):
        self.pyfunction = pyfunction
        self.index = index

    def get_object(self):
        result = self.pyfunction.get_parameter(self.index)
        if result is None:
            result = rope.base.pyobjects.get_unknown()
        return result

    def get_objects(self):
        """Returns the list of objects passed as this parameter"""
        return rope.base.oi.soi.get_passed_objects(self.pyfunction, self.index)

    def get_definition_location(self):
        return (self.pyfunction.get_module(), self.pyfunction.get_ast().lineno)


class AssignmentValue(pynames.AssignmentValue):
    pass


class EvaluatedName(pynames.EvaluatedName):
    pass


class ImportedModule(pynames.ImportedModule):
    pass


class ImportedName(pynames.ImportedName):
    pass


_Inferred = pynames._Inferred
