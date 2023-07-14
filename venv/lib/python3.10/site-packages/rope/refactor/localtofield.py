from rope.base import evaluate, exceptions, pynames, worder
from rope.refactor.rename import Rename


class LocalToField:
    def __init__(self, project, resource, offset):
        self.project = project
        self.resource = resource
        self.offset = offset

    def get_changes(self):
        name = worder.get_name_at(self.resource, self.offset)
        this_pymodule = self.project.get_pymodule(self.resource)
        pyname = evaluate.eval_location(this_pymodule, self.offset)
        if not self._is_a_method_local(pyname):
            raise exceptions.RefactoringError(
                "Convert local variable to field should be performed on "
                "a local variable of a method."
            )

        pymodule, lineno = pyname.get_definition_location()
        function_scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
        # Not checking redefinition
        # self._check_redefinition(name, function_scope)

        new_name = self._get_field_name(function_scope.pyobject, name)
        changes = Rename(self.project, self.resource, self.offset).get_changes(
            new_name, resources=[self.resource]
        )
        return changes

    def _check_redefinition(self, name, function_scope):
        class_scope = function_scope.parent
        if name in class_scope.pyobject:
            raise exceptions.RefactoringError("The field %s already exists" % name)

    def _get_field_name(self, pyfunction, name):
        self_name = pyfunction.get_param_names()[0]
        new_name = self_name + "." + name
        return new_name

    def _is_a_method_local(self, pyname):
        pymodule, lineno = pyname.get_definition_location()
        holding_scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
        parent = holding_scope.parent
        return (
            isinstance(pyname, pynames.AssignedName)
            and pyname in holding_scope.get_names().values()
            and holding_scope.get_kind() == "Function"
            and parent is not None
            and parent.get_kind() == "Class"
        )
