import rope.base.evaluate
from rope.base import ast


class Arguments:
    """A class for evaluating parameters passed to a function

    You can use the `create_arguments` factory.  It handles implicit
    first arguments.

    """

    def __init__(self, args, scope):
        self.args = args
        self.scope = scope
        self.instance = None

    def get_arguments(self, parameters):
        result = []
        for pyname in self.get_pynames(parameters):
            if pyname is None:
                result.append(None)
            else:
                result.append(pyname.get_object())
        return result

    def get_pynames(self, parameters):
        result = [None] * max(len(parameters), len(self.args))
        for index, arg in enumerate(self.args):
            if isinstance(arg, ast.keyword) and arg.arg in parameters:
                result[parameters.index(arg.arg)] = self._evaluate(arg.value)
            else:
                result[index] = self._evaluate(arg)
        return result

    def get_instance_pyname(self):
        if self.args:
            return self._evaluate(self.args[0])

    def _evaluate(self, ast_node):
        return rope.base.evaluate.eval_node(self.scope, ast_node)


def create_arguments(primary, pyfunction, call_node, scope):
    """A factory for creating `Arguments`"""
    args = list(call_node.args)
    args.extend(call_node.keywords)
    called = call_node.func
    # XXX: Handle constructors
    if _is_method_call(primary, pyfunction) and isinstance(called, ast.Attribute):
        args.insert(0, called.value)
    return Arguments(args, scope)


class ObjectArguments:
    def __init__(self, pynames):
        self.pynames = pynames

    def get_arguments(self, parameters):
        result = []
        for pyname in self.pynames:
            if pyname is None:
                result.append(None)
            else:
                result.append(pyname.get_object())
        return result

    def get_pynames(self, parameters):
        return self.pynames

    def get_instance_pyname(self):
        return self.pynames[0]


class MixedArguments:
    def __init__(self, pyname, arguments, scope):
        """`arguments` is an instance of `Arguments`"""
        self.pyname = pyname
        self.args = arguments

    def get_pynames(self, parameters):
        return [self.pyname] + self.args.get_pynames(parameters[1:])

    def get_arguments(self, parameters):
        result = []
        for pyname in self.get_pynames(parameters):
            if pyname is None:
                result.append(None)
            else:
                result.append(pyname.get_object())
        return result

    def get_instance_pyname(self):
        return self.pyname


def _is_method_call(primary, pyfunction):
    if primary is None:
        return False
    pyobject = primary.get_object()
    if (
        isinstance(pyobject.get_type(), rope.base.pyobjects.PyClass)
        and isinstance(pyfunction, rope.base.pyobjects.PyFunction)
        and isinstance(pyfunction.parent, rope.base.pyobjects.PyClass)
    ):
        return True
    if isinstance(
        pyobject.get_type(), rope.base.pyobjects.AbstractClass
    ) and isinstance(pyfunction, rope.base.builtins.BuiltinFunction):
        return True
    return False
