"""A module for inferring objects

For more information see the documentation in `rope.base.oi`
package.

"""
import rope.base.builtins  # Use full qualification for clarity.
from rope.base import arguments, evaluate, pynames, pyobjects, utils
from rope.base.oi.type_hinting.factory import get_type_hinting_factory

_ignore_inferred = utils.ignore_exception(pyobjects.IsBeingInferredError)


@_ignore_inferred
def infer_returned_object(pyfunction, args):
    """Infer the `PyObject` this `PyFunction` returns after calling"""
    object_info = pyfunction.pycore.object_info
    result = object_info.get_exact_returned(pyfunction, args)
    if result is not None:
        return result
    result = _infer_returned(pyfunction, args)
    if result is not None:
        if args and pyfunction.get_module().get_resource() is not None:
            params = args.get_arguments(pyfunction.get_param_names(special_args=False))
            object_info.function_called(pyfunction, params, result)
        return result
    result = object_info.get_returned(pyfunction, args)
    if result is not None:
        return result
    hint_return = get_type_hinting_factory(
        pyfunction.pycore.project
    ).make_return_provider()
    type_ = hint_return(pyfunction)
    if type_ is not None:
        return pyobjects.PyObject(type_)


@_ignore_inferred
def infer_parameter_objects(pyfunction):
    """Infer the `PyObject` of parameters of this `PyFunction`"""
    object_info = pyfunction.pycore.object_info
    result = object_info.get_parameter_objects(pyfunction)
    if result is None:
        result = _parameter_objects(pyfunction)
    _handle_first_parameter(pyfunction, result)
    return result


def _handle_first_parameter(pyobject, parameters):
    kind = pyobject.get_kind()
    if parameters is None or kind not in ["method", "classmethod"]:
        pass
    if not parameters:
        if not pyobject.get_param_names(special_args=False):
            return
        parameters.append(pyobjects.get_unknown())
    if kind == "method":
        parameters[0] = pyobjects.PyObject(pyobject.parent)
    if kind == "classmethod":
        parameters[0] = pyobject.parent


@_ignore_inferred
def infer_assigned_object(pyname):
    if not pyname.assignments:
        return
    for assignment in reversed(pyname.assignments):
        result = _infer_assignment(assignment, pyname.module)
        if (
            isinstance(result, rope.base.builtins.BuiltinUnknown)
            and result.get_name() == "NotImplementedType"
        ):
            break
        elif result == pyobjects.get_unknown():
            break
        elif result is not None:
            return result

    hint_assignment = get_type_hinting_factory(
        pyname.module.pycore.project
    ).make_assignment_provider()
    hinting_result = hint_assignment(pyname)
    if hinting_result is not None:
        return pyobjects.PyObject(hinting_result)
    return result


def get_passed_objects(pyfunction, parameter_index):
    object_info = pyfunction.pycore.object_info
    result = object_info.get_passed_objects(pyfunction, parameter_index)
    if not result:
        statically_inferred = _parameter_objects(pyfunction)
        if len(statically_inferred) > parameter_index:
            result.append(statically_inferred[parameter_index])
    return result


def _infer_returned(pyobject, args):
    if args:
        # HACK: Setting parameter objects manually
        # This is not thread safe and might cause problems if `args`
        # does not come from a good call site
        pyobject.get_scope().invalidate_data()
        pyobject._set_parameter_pyobjects(
            args.get_arguments(pyobject.get_param_names(special_args=False))
        )
    scope = pyobject.get_scope()
    if not scope._get_returned_asts():
        return
    maxtries = 3
    for returned_node in reversed(scope._get_returned_asts()[-maxtries:]):
        try:
            resulting_pyname = evaluate.eval_node(scope, returned_node)
            if resulting_pyname is None:
                continue
            pyobject = resulting_pyname.get_object()
            if pyobject == pyobjects.get_unknown():
                continue
            if not scope._is_generator():
                return pyobject
            else:
                return rope.base.builtins.get_generator(pyobject)
        except pyobjects.IsBeingInferredError:
            pass


def _parameter_objects(pyobject):
    result = []
    params = pyobject.get_param_names(special_args=False)
    hint_param = get_type_hinting_factory(pyobject.pycore.project).make_param_provider()
    for name in params:
        type_ = hint_param(pyobject, name)
        if type_ is not None:
            result.append(pyobjects.PyObject(type_))
        else:
            result.append(pyobjects.get_unknown())
    return result


# handling `rope.base.pynames.AssignmentValue`


@_ignore_inferred
def _infer_assignment(assignment, pymodule):
    result = _follow_pyname(assignment, pymodule)
    if result is None:
        return None
    pyname, pyobject = result
    pyobject = _follow_evaluations(assignment, pyname, pyobject)
    if pyobject is None:
        return None
    return _follow_levels(assignment, pyobject)


def _follow_levels(assignment, pyobject):
    for index in assignment.levels:
        if isinstance(pyobject.get_type(), rope.base.builtins.Tuple):
            holdings = pyobject.get_type().get_holding_objects()
            if holdings:
                pyobject = holdings[min(len(holdings) - 1, index)]
            else:
                pyobject = None
        elif isinstance(pyobject.get_type(), rope.base.builtins.List):
            pyobject = pyobject.get_type().holding
        else:
            pyobject = None
        if pyobject is None:
            break
    return pyobject


@_ignore_inferred
def _follow_pyname(assignment, pymodule, lineno=None):
    assign_node = assignment.type_hint or assignment.ast_node
    if lineno is None:
        lineno = _get_lineno_for_node(assign_node)
    holding_scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
    pyname = evaluate.eval_node(holding_scope, assign_node)
    if pyname is not None:
        result = pyname.get_object()
        if (
            isinstance(result.get_type(), rope.base.builtins.Property)
            and holding_scope.get_kind() == "Class"
        ):
            arg = pynames.UnboundName(pyobjects.PyObject(holding_scope.pyobject))
            return pyname, result.get_type().get_property_object(
                arguments.ObjectArguments([arg])
            )
        return pyname, result


@_ignore_inferred
def _follow_evaluations(assignment, pyname, pyobject):
    new_pyname = pyname
    tokens = assignment.evaluation.split(".")
    for token in tokens:
        call = token.endswith("()")
        if call:
            token = token[:-2]
        if token:
            pyname = new_pyname
            new_pyname = _get_attribute(pyobject, token)
            if new_pyname is not None:
                pyobject = new_pyname.get_object()
        if pyobject is not None and call:
            if isinstance(pyobject, pyobjects.AbstractFunction):
                args = arguments.ObjectArguments([pyname])
                pyobject = pyobject.get_returned_object(args)
            else:
                pyobject = None
        if pyobject is None:
            break
    if pyobject is not None and assignment.assign_type:
        return pyobjects.PyObject(pyobject)
    return pyobject


def _get_lineno_for_node(assign_node):
    if hasattr(assign_node, "lineno") and assign_node.lineno is not None:
        return assign_node.lineno
    return 1


def _get_attribute(pyobject, name):
    if pyobject is not None and name in pyobject:
        return pyobject[name]
