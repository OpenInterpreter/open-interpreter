from operator import itemgetter
from typing import Optional, Tuple

import rope.base.builtins
import rope.base.pynames
import rope.base.pyobjects
from rope.base import (
    arguments,
    ast,
    exceptions,
    nameanalyze,
    pyobjects,
    pyobjectsdef,
    worder,
)

BadIdentifierError = exceptions.BadIdentifierError


def eval_location(pymodule, offset):
    """Find the pyname at the offset"""
    return eval_location2(pymodule, offset)[1]


def eval_location2(pymodule, offset):
    """Find the primary and pyname at offset"""
    pyname_finder = ScopeNameFinder(pymodule)
    return pyname_finder.get_primary_and_pyname_at(offset)


def eval_node(scope, node):
    """Evaluate a `ast.AST` node and return a PyName

    Return `None` if the expression cannot be evaluated.
    """
    return eval_node2(scope, node)[1]


def eval_node2(scope, node):
    evaluator = StatementEvaluator(scope)
    evaluator.visit(node)
    return evaluator.old_result, evaluator.result


def eval_str(holding_scope, name):
    return eval_str2(holding_scope, name)[1]


def eval_str2(holding_scope, name):
    try:
        # parenthesizing for handling cases like 'a_var.\nattr'
        node = ast.parse("(%s)" % name)
    except SyntaxError:
        raise BadIdentifierError("Not a resolvable python identifier selected.")
    return eval_node2(holding_scope, node)


class ScopeNameFinder:
    def __init__(self, pymodule):
        self.module_scope = pymodule.get_scope()
        self.lines = pymodule.lines
        self.worder = worder.Worder(pymodule.source_code, True)

    def _is_defined_in_class_body(self, holding_scope, offset, lineno):
        if (
            lineno == holding_scope.get_start()
            and holding_scope.parent is not None
            and holding_scope.parent.get_kind() == "Class"
            and self.worder.is_a_class_or_function_name_in_header(offset)
        ):
            return True
        if (
            lineno != holding_scope.get_start()
            and holding_scope.get_kind() == "Class"
            and self.worder.is_name_assigned_in_class_body(offset)
        ):
            return True
        return False

    def _is_function_name_in_function_header(self, scope, offset, lineno):
        return (
            scope.get_start() <= lineno <= scope.get_body_start()
            and scope.get_kind() == "Function"
            and self.worder.is_a_class_or_function_name_in_header(offset)
        )

    def get_pyname_at(self, offset):
        return self.get_primary_and_pyname_at(offset)[1]

    def get_primary_and_pyname_at(
        self,
        offset: int,
    ) -> Tuple[Optional[rope.base.pynames.PyName], Optional[rope.base.pynames.PyName]]:
        lineno = self.lines.get_line_number(offset)
        holding_scope = self.module_scope.get_inner_scope_for_offset(offset)
        # function keyword parameter
        if self.worder.is_function_keyword_parameter(offset):
            keyword_name = self.worder.get_word_at(offset)
            pyobject = self.get_enclosing_function(offset)
            if isinstance(pyobject, pyobjectsdef.PyFunction):
                parameter_name = pyobject.get_parameters().get(keyword_name, None)
                return (None, parameter_name)
            elif isinstance(pyobject, pyobjects.AbstractFunction):
                parameter_name = rope.base.pynames.ParameterName()
                return (None, parameter_name)
        # class body
        if self._is_defined_in_class_body(holding_scope, offset, lineno):
            class_scope = holding_scope
            if lineno == holding_scope.get_start():
                class_scope = holding_scope.parent
            name = self.worder.get_primary_at(offset).strip()
            try:
                return (None, class_scope.pyobject[name])
            except rope.base.exceptions.AttributeNotFoundError:
                return (None, None)
        # function header
        if self._is_function_name_in_function_header(holding_scope, offset, lineno):
            name = self.worder.get_primary_at(offset).strip()
            return (None, holding_scope.parent[name])
        # module in a from statement or an imported name that is aliased
        if self.worder.is_from_statement_module(
            offset
        ) or self.worder.is_import_statement_aliased_module(offset):
            module = self.worder.get_primary_at(offset)
            module_pyname = self._find_module(module)
            return (None, module_pyname)
        if self.worder.is_from_aliased(offset):
            name = self.worder.get_from_aliased(offset)
        else:
            name = self.worder.get_primary_at(offset)
        return eval_str2(holding_scope, name)

    def get_enclosing_function(self, offset):
        function_parens = self.worder.find_parens_start_from_inside(offset)
        try:
            function_pyname = self.get_pyname_at(function_parens - 1)
        except BadIdentifierError:
            function_pyname = None
        if function_pyname is not None:
            pyobject = function_pyname.get_object()
            if isinstance(pyobject, pyobjects.AbstractFunction):
                return pyobject
            elif (
                isinstance(pyobject, pyobjects.AbstractClass) and "__init__" in pyobject
            ):
                return pyobject["__init__"].get_object()
            elif "__call__" in pyobject:
                return pyobject["__call__"].get_object()
        return None

    def _find_module(self, module_name):
        dots = 0
        while module_name[dots] == ".":
            dots += 1
        return rope.base.pynames.ImportedModule(
            self.module_scope.pyobject, module_name[dots:], dots
        )


class StatementEvaluator(ast.RopeNodeVisitor):
    def __init__(self, scope):
        self.scope = scope
        self.result = None
        self.old_result = None

    def _Name(self, node):
        self.result = self.scope.lookup(node.id)

    def _Attribute(self, node):
        pyname = eval_node(self.scope, node.value)
        if pyname is None:
            pyname = rope.base.pynames.UnboundName()
        self.old_result = pyname
        if pyname.get_object() != rope.base.pyobjects.get_unknown():
            try:
                self.result = pyname.get_object()[node.attr]
            except exceptions.AttributeNotFoundError:
                self.result = None

    def _Call(self, node):
        primary, pyobject = self._get_primary_and_object_for_node(node.func)
        if pyobject is None:
            return

        def _get_returned(pyobject):
            args = arguments.create_arguments(primary, pyobject, node, self.scope)
            return pyobject.get_returned_object(args)

        if isinstance(pyobject, rope.base.pyobjects.AbstractClass):
            result = None
            if "__new__" in pyobject:
                new_function = pyobject["__new__"].get_object()
                result = _get_returned(new_function)
            if result is None or result == rope.base.pyobjects.get_unknown():
                result = rope.base.pyobjects.PyObject(pyobject)
            self.result = rope.base.pynames.UnboundName(pyobject=result)
            return

        pyfunction = None
        if isinstance(pyobject, rope.base.pyobjects.AbstractFunction):
            pyfunction = pyobject
        elif "__call__" in pyobject:
            pyfunction = pyobject["__call__"].get_object()
        if pyfunction is not None:
            self.result = rope.base.pynames.UnboundName(
                pyobject=_get_returned(pyfunction)
            )

    def _Str(self, node):
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_str()
        )

    def _Num(self, node):
        type_name = type(node.n).__name__
        self.result = self._get_builtin_name(type_name)

    def _Constant(self, node):
        type_name = type(node.n).__name__
        try:
            self.result = self._get_builtin_name(type_name)
        except exceptions.AttributeNotFoundError:
            # XXX: Right way to fix this is to add missing NoneType to builtins?
            pass

    def _get_builtin_name(self, type_name):
        pytype = rope.base.builtins.builtins[type_name].get_object()
        return rope.base.pynames.UnboundName(rope.base.pyobjects.PyObject(pytype))

    def _BinOp(self, node):
        self.result = rope.base.pynames.UnboundName(
            self._get_object_for_node(node.left)
        )

    def _BoolOp(self, node):
        pyobject = self._get_object_for_node(node.values[0])
        if pyobject is None:
            pyobject = self._get_object_for_node(node.values[1])
        self.result = rope.base.pynames.UnboundName(pyobject)

    def _Repr(self, node):
        self.result = self._get_builtin_name("str")

    def _UnaryOp(self, node):
        self.result = rope.base.pynames.UnboundName(
            self._get_object_for_node(node.operand)
        )

    def _Compare(self, node):
        self.result = self._get_builtin_name("bool")

    def _Dict(self, node):
        keys = None
        values = None
        if node.keys and node.keys[0]:
            keys, values = next(
                iter(filter(itemgetter(0), zip(node.keys, node.values))), (None, None)
            )
            if keys:
                keys = self._get_object_for_node(keys)
            if values:
                values = self._get_object_for_node(values)
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_dict(keys, values)
        )

    def _List(self, node):
        holding = None
        if node.elts:
            holding = self._get_object_for_node(node.elts[0])
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_list(holding)
        )

    def _ListComp(self, node):
        pyobject = self._what_does_comprehension_hold(node)
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_list(pyobject)
        )

    def _GeneratorExp(self, node):
        pyobject = self._what_does_comprehension_hold(node)
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_iterator(pyobject)
        )

    def _what_does_comprehension_hold(self, node):
        scope = self._make_comprehension_scope(node)
        pyname = eval_node(scope, node.elt)
        return pyname.get_object() if pyname is not None else None

    def _make_comprehension_scope(self, node):
        scope = self.scope
        module = scope.pyobject.get_module()
        names = {}
        for comp in node.generators:
            new_names = _get_evaluated_names(
                comp.target, comp.iter, module, ".__iter__().next()", node.lineno
            )
            names.update(new_names)
        return rope.base.pyscopes.TemporaryScope(scope.pycore, scope, names)

    def _Tuple(self, node):
        objects = []
        if len(node.elts) < 4:
            for stmt in node.elts:
                pyobject = self._get_object_for_node(stmt)
                objects.append(pyobject)
        else:
            objects.append(self._get_object_for_node(node.elts[0]))
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.get_tuple(*objects)
        )

    def _get_object_for_node(self, stmt):
        pyname = eval_node(self.scope, stmt)
        pyobject = None
        if pyname is not None:
            pyobject = pyname.get_object()
        return pyobject

    def _get_primary_and_object_for_node(self, stmt):
        primary, pyname = eval_node2(self.scope, stmt)
        pyobject = None
        if pyname is not None:
            pyobject = pyname.get_object()
        return primary, pyobject

    def _Subscript(self, node):
        if isinstance(node.slice, ast.Index):
            self._call_function(node.value, "__getitem__", [node.slice.value])
        elif isinstance(node.slice, ast.Slice):
            self._call_function(node.value, "__getitem__", [node.slice])
        elif isinstance(node.slice, ast.expr):
            self._call_function(node.value, "__getitem__", [node.value])

    def _Slice(self, node):
        self.result = self._get_builtin_name("slice")

    def _call_function(self, node, function_name, other_args=None):
        pyname = eval_node(self.scope, node)
        if pyname is not None:
            pyobject = pyname.get_object()
        else:
            return
        if function_name in pyobject:
            called = pyobject[function_name].get_object()
            if not called or not isinstance(called, pyobjects.AbstractFunction):
                return
            args = [node]
            if other_args:
                args += other_args
            arguments_ = arguments.Arguments(args, self.scope)
            self.result = rope.base.pynames.UnboundName(
                pyobject=called.get_returned_object(arguments_)
            )

    def _Lambda(self, node):
        self.result = rope.base.pynames.UnboundName(
            pyobject=rope.base.builtins.Lambda(node, self.scope)
        )


def _get_evaluated_names(targets, assigned, module, evaluation, lineno):
    result = {}
    for name, levels in nameanalyze.get_name_levels(targets):
        assignment = rope.base.pynames.AssignmentValue(assigned, levels, evaluation)
        # XXX: this module should not access `rope.base.pynamesdef`!
        pyname = rope.base.pynamesdef.AssignedName(lineno, module)
        pyname.assignments.append(assignment)
        result[name] = pyname
    return result
