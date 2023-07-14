import rope.base.builtins
import rope.base.codeanalyze
import rope.base.evaluate
import rope.base.libutils
import rope.base.oi.soi
import rope.base.pyscopes
from rope.base import (
    arguments,
    ast,
    exceptions,
    fscommands,
    nameanalyze,
    pynamesdef,
    pyobjects,
    utils,
)


class PyFunction(pyobjects.PyFunction):
    def __init__(self, pycore, ast_node, parent):
        rope.base.pyobjects.AbstractFunction.__init__(self)
        rope.base.pyobjects.PyDefinedObject.__init__(self, pycore, ast_node, parent)
        self.arguments = self.ast_node.args
        self.parameter_pyobjects = pynamesdef._Inferred(
            self._infer_parameters, self.get_module()._get_concluded_data()
        )
        self.returned = pynamesdef._Inferred(self._infer_returned)
        self.parameter_pynames = None

    def _create_structural_attributes(self):
        return {}

    def _create_concluded_attributes(self):
        return {}

    def _create_scope(self):
        return rope.base.pyscopes.FunctionScope(self.pycore, self, _FunctionVisitor)

    def _infer_parameters(self):
        pyobjects = rope.base.oi.soi.infer_parameter_objects(self)
        self._handle_special_args(pyobjects)
        return pyobjects

    def _infer_returned(self, args=None):
        return rope.base.oi.soi.infer_returned_object(self, args)

    def _handle_special_args(self, pyobjects):
        if len(pyobjects) == len(self.arguments.args):
            if self.arguments.vararg:
                pyobjects.append(rope.base.builtins.get_list())
            if self.arguments.kwarg:
                pyobjects.append(rope.base.builtins.get_dict())

    def _set_parameter_pyobjects(self, pyobjects):
        if pyobjects is not None:
            self._handle_special_args(pyobjects)
        self.parameter_pyobjects.set(pyobjects)

    def get_parameters(self):
        if self.parameter_pynames is None:
            result = {}
            for index, name in enumerate(self.get_param_names()):
                # TODO: handle tuple parameters
                result[name] = pynamesdef.ParameterName(self, index)
            self.parameter_pynames = result
        return self.parameter_pynames

    def get_parameter(self, index):
        if index < len(self.parameter_pyobjects.get()):
            return self.parameter_pyobjects.get()[index]

    def get_returned_object(self, args):
        return self.returned.get(args)

    def get_name(self):
        return self.get_ast().name

    def get_param_names(self, special_args=True):
        # TODO: handle tuple parameters
        result = [node.arg for node in self.arguments.args if isinstance(node, ast.arg)]
        if special_args:
            if self.arguments.vararg:
                result.append(self.arguments.vararg.arg)
            if self.arguments.kwarg:
                result.append(self.arguments.kwarg.arg)
        return result

    def get_kind(self):
        """Get function type

        It returns one of 'function', 'method', 'staticmethod' or
        'classmethod' strs.

        """
        scope = self.parent.get_scope()
        if isinstance(self.parent, PyClass):
            for decorator in self.decorators:
                pyname = rope.base.evaluate.eval_node(scope, decorator)
                if pyname == rope.base.builtins.builtins["staticmethod"]:
                    return "staticmethod"
                if pyname == rope.base.builtins.builtins["classmethod"]:
                    return "classmethod"
            return "method"
        return "function"

    @property
    def decorators(self):
        try:
            return self.ast_node.decorator_list
        except AttributeError:
            return getattr(self.ast_node, "decorators", None)


class PyComprehension(pyobjects.PyComprehension):
    def __init__(self, pycore, ast_node, parent):
        self.visitor_class = _ComprehensionVisitor
        rope.base.pyobjects.PyObject.__init__(self, type_="Comp")
        rope.base.pyobjects.PyDefinedObject.__init__(self, pycore, ast_node, parent)

    def _create_scope(self):
        return rope.base.pyscopes.ComprehensionScope(
            self.pycore, self, _ComprehensionVisitor
        )

    def get_kind(self):
        return "Comprehension"


class PyClass(pyobjects.PyClass):
    def __init__(self, pycore, ast_node, parent):
        self.visitor_class = _ClassVisitor
        rope.base.pyobjects.AbstractClass.__init__(self)
        rope.base.pyobjects.PyDefinedObject.__init__(self, pycore, ast_node, parent)
        self.parent = parent
        self._superclasses = self.get_module()._get_concluded_data()

    def get_superclasses(self):
        if self._superclasses.get() is None:
            self._superclasses.set(self._get_bases())
        return self._superclasses.get()

    def get_name(self):
        return self.get_ast().name

    def _create_concluded_attributes(self):
        result = {}
        for base in reversed(self.get_superclasses()):
            result.update(base.get_attributes())
        return result

    def _get_bases(self):
        result = []
        for base_name in self.ast_node.bases:
            base = rope.base.evaluate.eval_node(self.parent.get_scope(), base_name)
            if (
                base is not None
                and base.get_object().get_type()
                == rope.base.pyobjects.get_base_type("Type")
            ):
                result.append(base.get_object())
        return result

    def _create_scope(self):
        return rope.base.pyscopes.ClassScope(self.pycore, self)


class PyModule(pyobjects.PyModule):
    def __init__(self, pycore, source=None, resource=None, force_errors=False):
        ignore = pycore.project.prefs.get("ignore_syntax_errors", False)
        syntax_errors = force_errors or not ignore
        self.has_errors = False
        try:
            source, node = self._init_source(pycore, source, resource)
        except exceptions.ModuleSyntaxError:
            self.has_errors = True
            if syntax_errors:
                raise
            else:
                source = "\n"
                node = ast.parse("\n")
        self.source_code = source
        self.star_imports = []
        self.visitor_class = _GlobalVisitor
        self.coding = fscommands.read_str_coding(self.source_code)
        super().__init__(pycore, node, resource)

    def _init_source(self, pycore, source_code, resource):
        filename = "string"
        if resource:
            filename = resource.path
        try:
            if source_code is None:
                source_bytes = resource.read_bytes()
                source_code, _ = fscommands.file_data_to_unicode(source_bytes)
            else:
                if isinstance(source_code, str):
                    source_bytes = fscommands.unicode_to_file_data(source_code)
                else:
                    source_bytes = source_code
            ast_node = ast.parse(source_bytes, filename=filename)
        except SyntaxError as e:
            raise exceptions.ModuleSyntaxError(filename, e.lineno, e.msg)
        except UnicodeDecodeError as e:
            raise exceptions.ModuleSyntaxError(filename, 1, "%s" % (e.reason))
        return source_code, ast_node

    @utils.prevent_recursion(lambda: {})
    def _create_concluded_attributes(self):
        result = {}
        for star_import in self.star_imports:
            result.update(star_import.get_names())
        return result

    def _create_scope(self):
        return rope.base.pyscopes.GlobalScope(self.pycore, self)

    @property
    @utils.saveit
    def lines(self):
        """A `SourceLinesAdapter`"""
        return rope.base.codeanalyze.SourceLinesAdapter(self.source_code)

    @property
    @utils.saveit
    def logical_lines(self):
        """A `LogicalLinesFinder`"""
        return rope.base.codeanalyze.CachingLogicalLineFinder(self.lines)

    def get_name(self):
        return rope.base.libutils.modname(self.resource) if self.resource else ""


class PyPackage(pyobjects.PyPackage):
    def __init__(self, pycore, resource=None, force_errors=False):
        self.resource = resource
        init_dot_py = self._get_init_dot_py()
        if init_dot_py is not None:
            ast_node = pycore.project.get_pymodule(
                init_dot_py, force_errors=force_errors
            ).get_ast()
        else:
            ast_node = ast.parse("\n")
        super().__init__(pycore, ast_node, resource)

    def _create_structural_attributes(self):
        result = {}
        modname = rope.base.libutils.modname(self.resource)
        extension_submodules = self.pycore._builtin_submodules(modname)
        for name, module in extension_submodules.items():
            result[name] = rope.base.builtins.BuiltinName(module)
        if self.resource is None:
            return result
        for name, resource in self._get_child_resources().items():
            result[name] = pynamesdef.ImportedModule(self, resource=resource)
        return result

    def _create_concluded_attributes(self):
        result = {}
        init_dot_py = self._get_init_dot_py()
        if init_dot_py:
            init_object = self.pycore.project.get_pymodule(init_dot_py)
            result.update(init_object.get_attributes())
        return result

    def _get_child_resources(self):
        result = {}
        for child in self.resource.get_children():
            if child.is_folder():
                result[child.name] = child
            elif child.name.endswith(".py") and child.name != "__init__.py":
                name = child.name[:-3]
                result[name] = child
        return result

    def _get_init_dot_py(self):
        if self.resource is not None and self.resource.has_child("__init__.py"):
            return self.resource.get_child("__init__.py")
        else:
            return None

    def _create_scope(self):
        return self.get_module().get_scope()

    def get_module(self):
        init_dot_py = self._get_init_dot_py()
        if init_dot_py:
            return self.pycore.project.get_pymodule(init_dot_py)
        return self

    def get_name(self):
        return rope.base.libutils.modname(self.resource) if self.resource else ""


class _AnnAssignVisitor(ast.RopeNodeVisitor):
    def __init__(self, scope_visitor):
        self.scope_visitor = scope_visitor
        self.assigned_ast = None
        self.type_hint = None

    def _AnnAssign(self, node):
        self.assigned_ast = node.value
        self.type_hint = node.annotation

        self.visit(node.target)

    def _assigned(self, name, assignment=None):
        self.scope_visitor._assigned(name, assignment)

    def _Name(self, node):
        assignment = pynamesdef.AssignmentValue(
            self.assigned_ast, assign_type=True, type_hint=self.type_hint
        )
        self._assigned(node.id, assignment)

    def _Tuple(self, node):
        names = nameanalyze.get_name_levels(node)
        for name, levels in names:
            assignment = None
            if self.assigned_ast is not None:
                assignment = pynamesdef.AssignmentValue(self.assigned_ast, levels)
            self._assigned(name, assignment)

    def _Annotation(self, node):
        pass

    def _Attribute(self, node):
        pass

    def _Subscript(self, node):
        pass

    def _Slice(self, node):
        pass


class _ExpressionVisitor(ast.RopeNodeVisitor):
    def __init__(self, scope_visitor):
        self.scope_visitor = scope_visitor

    def _assigned(self, name, assignment=None):
        self.scope_visitor._assigned(name, assignment)

    def _GeneratorExp(self, node):
        list_comp = PyComprehension(
            self.scope_visitor.pycore, node, self.scope_visitor.owner_object
        )
        self.scope_visitor.defineds.append(list_comp)

    def _SetComp(self, node):
        self._GeneratorExp(node)

    def _ListComp(self, node):
        self._GeneratorExp(node)

    def _DictComp(self, node):
        self._GeneratorExp(node)

    def _NamedExpr(self, node):
        _AssignVisitor(self).visit(node.target)
        self.visit(node.value)


class _AssignVisitor(ast.RopeNodeVisitor):
    def __init__(self, scope_visitor):
        self.scope_visitor = scope_visitor
        self.assigned_ast = None

    def _Assign(self, node):
        self.assigned_ast = node.value
        for child_node in node.targets:
            self.visit(child_node)
        _ExpressionVisitor(self.scope_visitor).visit(node.value)

    def _assigned(self, name, assignment=None):
        self.scope_visitor._assigned(name, assignment)

    def _Name(self, node):
        assignment = None
        if self.assigned_ast is not None:
            assignment = pynamesdef.AssignmentValue(self.assigned_ast)
        self._assigned(node.id, assignment)

    def _Tuple(self, node):
        names = nameanalyze.get_name_levels(node)
        for name, levels in names:
            assignment = None
            if self.assigned_ast is not None:
                assignment = pynamesdef.AssignmentValue(self.assigned_ast, levels)
            self._assigned(name, assignment)

    def _Attribute(self, node):
        pass

    def _Subscript(self, node):
        pass

    def _Slice(self, node):
        pass


class _ScopeVisitor(_ExpressionVisitor):
    def __init__(self, pycore, owner_object):
        _ExpressionVisitor.__init__(self, scope_visitor=self)
        self.pycore = pycore
        self.owner_object = owner_object
        self.names = {}
        self.defineds = []

    def get_module(self):
        if self.owner_object is not None:
            return self.owner_object.get_module()
        else:
            return None

    def _ClassDef(self, node):
        pyclass = PyClass(self.pycore, node, self.owner_object)
        self.names[node.name] = pynamesdef.DefinedName(pyclass)
        self.defineds.append(pyclass)

    def _FunctionDef(self, node):
        pyfunction = PyFunction(self.pycore, node, self.owner_object)
        for decorator in pyfunction.decorators:
            if isinstance(decorator, ast.Name) and decorator.id == "property":
                if isinstance(self, _ClassVisitor):
                    type_ = rope.base.builtins.Property(pyfunction)
                    arg = pynamesdef.UnboundName(
                        rope.base.pyobjects.PyObject(self.owner_object)
                    )

                    def _eval(type_=type_, arg=arg):
                        return type_.get_property_object(
                            arguments.ObjectArguments([arg])
                        )

                    lineno = utils.guess_def_lineno(self.get_module(), node)

                    self.names[node.name] = pynamesdef.EvaluatedName(
                        _eval, module=self.get_module(), lineno=lineno
                    )
                    break
        else:
            self.names[node.name] = pynamesdef.DefinedName(pyfunction)
        self.defineds.append(pyfunction)

    def _AsyncFunctionDef(self, node):
        return self._FunctionDef(node)

    def _Assign(self, node):
        _AssignVisitor(self).visit(node)

    def _AnnAssign(self, node):
        _AnnAssignVisitor(self).visit(node)

    def _AugAssign(self, node):
        pass

    def _For(self, node):
        self._update_evaluated(node.target, node.iter, ".__iter__().next()")
        for child in node.body + node.orelse:
            self.visit(child)

    def _AsyncFor(self, node):
        return self._For(node)

    def _assigned(self, name, assignment):
        pyname = self.names.get(name, None)
        if pyname is None:
            pyname = pynamesdef.AssignedName(module=self.get_module())
        if isinstance(pyname, pynamesdef.AssignedName):
            if assignment is not None:
                pyname.assignments.append(assignment)
            self.names[name] = pyname

    def _update_evaluated(
        self, targets, assigned, evaluation="", eval_type=False, type_hint=None
    ):
        result = {}
        if isinstance(targets, str):
            assignment = pynamesdef.AssignmentValue(assigned, [], evaluation, eval_type)
            self._assigned(targets, assignment)
        else:
            names = nameanalyze.get_name_levels(targets)
            for name, levels in names:
                assignment = pynamesdef.AssignmentValue(
                    assigned, levels, evaluation, eval_type
                )
                self._assigned(name, assignment)
        return result

    def _With(self, node):
        for item in node.items:
            if item.optional_vars:
                self._update_evaluated(
                    item.optional_vars, item.context_expr, ".__enter__()"
                )
        for child in node.body:
            self.visit(child)

    def _AsyncWith(self, node):
        return self._With(node)

    def _excepthandler(self, node):
        node_name_type = str
        if node.name is not None and isinstance(node.name, node_name_type):
            type_node = node.type
            if isinstance(node.type, ast.Tuple) and type_node.elts:
                type_node = type_node.elts[0]
            self._update_evaluated(node.name, type_node, eval_type=True)

        for child in node.body:
            self.visit(child)

    def _ExceptHandler(self, node):
        self._excepthandler(node)

    def _Import(self, node):
        for import_pair in node.names:
            module_name = import_pair.name
            alias = import_pair.asname
            first_package = module_name.split(".")[0]
            if alias is not None:
                imported = pynamesdef.ImportedModule(self.get_module(), module_name)
                if not self._is_ignored_import(imported):
                    self.names[alias] = imported
            else:
                imported = pynamesdef.ImportedModule(self.get_module(), first_package)
                if not self._is_ignored_import(imported):
                    self.names[first_package] = imported

    def _ImportFrom(self, node):
        level = 0
        if node.level:
            level = node.level
        imported_module = pynamesdef.ImportedModule(
            self.get_module(),
            node.module or "",
            level,
        )
        if self._is_ignored_import(imported_module):
            return
        if len(node.names) == 1 and node.names[0].name == "*":
            if isinstance(self.owner_object, PyModule):
                self.owner_object.star_imports.append(StarImport(imported_module))
        else:
            for imported_name in node.names:
                imported = imported_name.name
                alias = imported_name.asname
                if alias is not None:
                    imported = alias
                self.names[imported] = pynamesdef.ImportedName(
                    imported_module, imported_name.name
                )

    def _is_ignored_import(self, imported_module):
        if not self.pycore.project.prefs.get("ignore_bad_imports", False):
            return False
        return not isinstance(
            imported_module.get_object(), rope.base.pyobjects.AbstractModule
        )

    def _Global(self, node):
        module = self.get_module()
        for name in node.names:
            if module is not None:
                try:
                    pyname = module[name]
                except exceptions.AttributeNotFoundError:
                    pyname = pynamesdef.AssignedName(node.lineno)
            self.names[name] = pyname


class _ComprehensionVisitor(_ScopeVisitor):
    def _comprehension(self, node):
        self.visit(node.target)
        self.visit(node.iter)

    def _Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.names[node.id] = self._get_pyobject(node)

    def _get_pyobject(self, node):
        return pynamesdef.AssignedName(lineno=node.lineno, module=self.get_module())


class _GlobalVisitor(_ScopeVisitor):
    def __init__(self, pycore, owner_object):
        super().__init__(pycore, owner_object)


class _ClassVisitor(_ScopeVisitor):
    def __init__(self, pycore, owner_object):
        super().__init__(pycore, owner_object)

    def _FunctionDef(self, node):
        _ScopeVisitor._FunctionDef(self, node)
        if len(node.args.args) > 0:
            first = node.args.args[0]
            new_visitor = None
            if isinstance(first, ast.arg):
                new_visitor = _ClassInitVisitor(self, first.arg)
            if new_visitor is not None:
                for child in ast.iter_child_nodes(node):
                    new_visitor.visit(child)


class _FunctionVisitor(_ScopeVisitor):
    def __init__(self, pycore, owner_object):
        super().__init__(pycore, owner_object)
        self.returned_asts = []
        self.generator = False

    def _Return(self, node):
        if node.value is not None:
            self.returned_asts.append(node.value)

    def _Yield(self, node):
        if node.value is not None:
            self.returned_asts.append(node.value)
        self.generator = True


class _ClassInitVisitor(_AssignVisitor):
    def __init__(self, scope_visitor, self_name):
        super().__init__(scope_visitor)
        self.self_name = self_name

    def _Attribute(self, node):
        if not isinstance(node.ctx, ast.Store):
            return
        if isinstance(node.value, ast.Name) and node.value.id == self.self_name:
            if node.attr not in self.scope_visitor.names:
                self.scope_visitor.names[node.attr] = pynamesdef.AssignedName(
                    lineno=node.lineno, module=self.scope_visitor.get_module()
                )
            if self.assigned_ast is not None:
                pyname = self.scope_visitor.names[node.attr]
                if isinstance(pyname, pynamesdef.AssignedName):
                    pyname.assignments.append(
                        pynamesdef.AssignmentValue(self.assigned_ast)
                    )

    def _Tuple(self, node):
        if not isinstance(node.ctx, ast.Store):
            return
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def _Name(self, node):
        pass

    def _FunctionDef(self, node):
        pass

    def _ClassDef(self, node):
        pass

    def _For(self, node):
        pass

    def _With(self, node):
        pass


class StarImport:
    def __init__(self, imported_module):
        self.imported_module = imported_module

    def get_names(self):
        result = {}
        imported = self.imported_module.get_object()
        for name in imported:
            if not name.startswith("_"):
                result[name] = pynamesdef.ImportedName(self.imported_module, name)
        return result
