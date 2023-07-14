import rope.base.ast
import rope.base.oi.soi
import rope.base.pynames
from rope.base import arguments, evaluate, nameanalyze, pyobjects


def analyze_module(pycore, pymodule, should_analyze, search_subscopes, followed_calls):
    """Analyze `pymodule` for static object inference

    Analyzes scopes for collecting object information.  The analysis
    starts from inner scopes.

    """
    _analyze_node(pycore, pymodule, should_analyze, search_subscopes, followed_calls)


def _analyze_node(pycore, pydefined, should_analyze, search_subscopes, followed_calls):
    if search_subscopes(pydefined):
        for scope in pydefined.get_scope().get_scopes():
            _analyze_node(
                pycore, scope.pyobject, should_analyze, search_subscopes, followed_calls
            )
    if should_analyze(pydefined):
        new_followed_calls = max(0, followed_calls - 1)
        return_true = lambda pydefined: True
        return_false = lambda pydefined: False

        def _follow(pyfunction):
            _analyze_node(
                pycore, pyfunction, return_true, return_false, new_followed_calls
            )

        visitor = SOAVisitor(pycore, pydefined, _follow if followed_calls else None)
        for child in rope.base.ast.iter_child_nodes(pydefined.get_ast()):
            visitor.visit(child)


class SOAVisitor(rope.base.ast.RopeNodeVisitor):
    def __init__(self, pycore, pydefined, follow_callback=None):
        self.pycore = pycore
        self.pymodule = pydefined.get_module()
        self.scope = pydefined.get_scope()
        self.follow = follow_callback

    def _FunctionDef(self, node):
        pass

    def _ClassDef(self, node):
        pass

    def _Call(self, node):
        for child in rope.base.ast.iter_child_nodes(node):
            self.visit(child)
        primary, pyname = evaluate.eval_node2(self.scope, node.func)
        if pyname is None:
            return
        pyfunction = pyname.get_object()
        if isinstance(pyfunction, pyobjects.AbstractFunction):
            args = arguments.create_arguments(primary, pyfunction, node, self.scope)
        elif isinstance(pyfunction, pyobjects.PyClass):
            pyclass = pyfunction
            if "__init__" in pyfunction:
                pyfunction = pyfunction["__init__"].get_object()
            pyname = rope.base.pynames.UnboundName(pyobjects.PyObject(pyclass))
            args = self._args_with_self(primary, pyname, pyfunction, node)
        elif "__call__" in pyfunction:
            pyfunction = pyfunction["__call__"].get_object()
            args = self._args_with_self(primary, pyname, pyfunction, node)
        else:
            return
        self._call(pyfunction, args)

    def _args_with_self(self, primary, self_pyname, pyfunction, node):
        base_args = arguments.create_arguments(primary, pyfunction, node, self.scope)
        return arguments.MixedArguments(self_pyname, base_args, self.scope)

    def _call(self, pyfunction, args):
        if isinstance(pyfunction, pyobjects.PyFunction):
            if self.follow is not None:
                before = self._parameter_objects(pyfunction)
            self.pycore.object_info.function_called(
                pyfunction, args.get_arguments(pyfunction.get_param_names())
            )
            pyfunction._set_parameter_pyobjects(None)
            if self.follow is not None:
                after = self._parameter_objects(pyfunction)
                if after != before:
                    self.follow(pyfunction)
        # XXX: Maybe we should not call every builtin function
        if isinstance(pyfunction, rope.base.builtins.BuiltinFunction):
            pyfunction.get_returned_object(args)

    def _parameter_objects(self, pyfunction):
        return [
            pyfunction.get_parameter(i)
            for i in range(len(pyfunction.get_param_names(False)))
        ]

    def _AnnAssign(self, node):
        for child in rope.base.ast.iter_child_nodes(node):
            self.visit(child)
        visitor = _SOAAssignVisitor()
        nodes = []

        visitor.visit(node.target)
        nodes.extend(visitor.nodes)

        self._evaluate_assign_value(node, nodes, type_hint=node.annotation)

    def _Assign(self, node):
        for child in rope.base.ast.iter_child_nodes(node):
            self.visit(child)
        visitor = _SOAAssignVisitor()
        nodes = []
        for child in node.targets:
            visitor.visit(child)
            nodes.extend(visitor.nodes)
        self._evaluate_assign_value(node, nodes)

    def _evaluate_assign_value(self, node, nodes, type_hint=False):
        for subscript, levels in nodes:
            instance = evaluate.eval_node(self.scope, subscript.value)
            args_pynames = [evaluate.eval_node(self.scope, subscript.slice)]
            value = rope.base.oi.soi._infer_assignment(
                rope.base.pynames.AssignmentValue(
                    node.value, levels, type_hint=type_hint
                ),
                self.pymodule,
            )
            args_pynames.append(rope.base.pynames.UnboundName(value))
            if instance is not None and value is not None:
                pyobject = instance.get_object()
                if "__setitem__" in pyobject:
                    pyfunction = pyobject["__setitem__"].get_object()
                    args = arguments.ObjectArguments([instance] + args_pynames)
                    self._call(pyfunction, args)
                # IDEA: handle `__setslice__`, too


class _SOAAssignVisitor(nameanalyze._NodeNameCollector):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def _added(self, node, levels):
        if isinstance(node, rope.base.ast.Subscript) and isinstance(
            node.slice, (rope.base.ast.Index, rope.base.ast.expr)
        ):
            self.nodes.append((node, levels))
