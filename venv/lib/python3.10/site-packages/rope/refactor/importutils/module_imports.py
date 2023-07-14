from typing import List, Union

from rope.base import ast, exceptions, pynames, pynamesdef, utils
from rope.refactor.importutils import actions, importinfo


class ModuleImports:
    def __init__(self, project, pymodule, import_filter=None):
        self.project = project
        self.pymodule = pymodule
        self.separating_lines = 0
        self.filter = import_filter
        self.sorted = False

    @property
    @utils.saveit
    def imports(self):
        finder = _GlobalImportFinder(self.pymodule)
        result = finder.find_import_statements()
        self.separating_lines = finder.get_separating_line_count()
        if self.filter is not None:
            for import_stmt in result:
                if not self.filter(import_stmt):
                    import_stmt.readonly = True
        return result

    def _get_unbound_names(self, defined_pyobject):
        visitor = _GlobalUnboundNameFinder(self.pymodule, defined_pyobject)
        visitor.visit(self.pymodule.get_ast())
        return visitor.unbound

    def _get_all_star_list(self, pymodule):
        def _resolve_name(
            name: Union[pynamesdef.AssignedName, pynames.ImportedName]
        ) -> List:
            while isinstance(name, pynames.ImportedName):
                try:
                    name = name.imported_module.get_object().get_attribute(
                        name.imported_name,
                    )
                except exceptions.AttributeNotFoundError:
                    return []
            assert isinstance(name, pynamesdef.AssignedName)
            return name.assignments

        result = set()
        try:
            all_star_list = pymodule.get_attribute("__all__")
        except exceptions.AttributeNotFoundError:
            return result

        assignments = [
            assignment.ast_node for assignment in _resolve_name(all_star_list)
        ]

        # FIXME: Need a better way to recursively infer possible values.
        #        Currently pyobjects can recursively infer type, but not values.
        # Do a very basic 1-level value inference

        while assignments:
            assignment = assignments.pop()
            if isinstance(assignment, ast.List):
                stack = list(assignment.elts)
                while stack:
                    el = stack.pop()
                    if isinstance(el, ast.IfExp):
                        stack.append(el.body)
                        stack.append(el.orelse)
                    elif isinstance(el, ast.Starred):
                        assignments.append(el.value)
                    else:
                        if isinstance(el, ast.Str):
                            result.add(el.s)
                        elif isinstance(el, ast.Name):
                            try:
                                name = pymodule.get_attribute(el.id)
                            except exceptions.AttributeNotFoundError:
                                continue
                            else:
                                for av in _resolve_name(name):
                                    if isinstance(av.ast_node, ast.Str):
                                        result.add(av.ast_node.s)
            elif isinstance(assignment, ast.Name):
                try:
                    name = pymodule.get_attribute(assignment.id)
                except exceptions.AttributeNotFoundError:
                    continue
                else:
                    assignments.extend(
                        assignment.ast_node for assignment in _resolve_name(name)
                    )
            elif isinstance(assignment, ast.BinOp):
                assignments.append(assignment.left)
                assignments.append(assignment.right)
        return result

    def remove_unused_imports(self):
        can_select = _OneTimeSelector(
            self._get_unbound_names(self.pymodule)
            | self._get_all_star_list(self.pymodule)
            | {"__all__"}
        )
        visitor = actions.RemovingVisitor(
            self.project, self._current_folder(), can_select
        )
        for import_statement in self.imports:
            import_statement.accept(visitor)

    def get_used_imports(self, defined_pyobject):
        result = []
        can_select = _OneTimeSelector(self._get_unbound_names(defined_pyobject))
        visitor = actions.FilteringVisitor(
            self.project, self._current_folder(), can_select
        )
        for import_statement in self.imports:
            new_import = import_statement.accept(visitor)
            if new_import is not None and not new_import.is_empty():
                result.append(new_import)
        return result

    def get_changed_source(self):
        if not self.project.prefs.get("pull_imports_to_top") and not self.sorted:
            return "".join(self._rewrite_imports(self.imports))

        # Make sure we forward a removed import's preceding blank
        # lines count to the following import statement.
        prev_stmt = None
        for stmt in self.imports:
            if prev_stmt is not None and prev_stmt.import_info.is_empty():
                stmt.blank_lines = max(prev_stmt.blank_lines, stmt.blank_lines)
            prev_stmt = stmt
        # The new list of imports.
        imports = [stmt for stmt in self.imports if not stmt.import_info.is_empty()]

        after_removing = self._remove_imports(self.imports)
        first_non_blank = self._first_non_blank_line(after_removing, 0)
        first_import = self._first_import_line() - 1
        result = []
        # Writing module docs
        result.extend(after_removing[first_non_blank:first_import])
        # Writing imports
        sorted_imports = sorted(imports, key=self._get_location)
        for stmt in sorted_imports:
            if stmt != sorted_imports[0]:
                result.append("\n" * stmt.blank_lines)
            result.append(stmt.get_import_statement() + "\n")
        if sorted_imports and first_non_blank < len(after_removing):
            result.append("\n" * self.separating_lines)

        # Writing the body
        first_after_imports = self._first_non_blank_line(after_removing, first_import)
        result.extend(after_removing[first_after_imports:])
        return "".join(result)

    def _get_import_location(self, stmt):
        start = stmt.get_new_start()
        if start is None:
            start = stmt.get_old_location()[0]
        return start

    def _get_location(self, stmt):
        if stmt.get_new_start() is not None:
            return stmt.get_new_start()
        else:
            return stmt.get_old_location()[0]

    def _remove_imports(self, imports):
        lines = self.pymodule.source_code.splitlines(True)
        after_removing = []
        first_import_line = self._first_import_line()
        last_index = 0
        for stmt in imports:
            start, end = stmt.get_old_location()
            blank_lines = 0
            if start != first_import_line:
                blank_lines = _count_blank_lines(
                    lines.__getitem__, start - 2, last_index - 1, -1
                )
            after_removing.extend(lines[last_index : start - 1 - blank_lines])
            last_index = end - 1
        after_removing.extend(lines[last_index:])
        return after_removing

    def _rewrite_imports(self, imports):
        lines = self.pymodule.source_code.splitlines(True)
        after_rewriting = []
        last_index = 0
        for stmt in imports:
            start, end = stmt.get_old_location()
            after_rewriting.extend(lines[last_index : start - 1])
            if not stmt.import_info.is_empty():
                after_rewriting.append(stmt.get_import_statement() + "\n")
            last_index = end - 1
        after_rewriting.extend(lines[last_index:])
        return after_rewriting

    def _first_non_blank_line(self, lines, lineno):
        return lineno + _count_blank_lines(lines.__getitem__, lineno, len(lines))

    def add_import(self, import_info):
        visitor = actions.AddingVisitor(self.project, [import_info])
        for import_statement in self.imports:
            if import_statement.accept(visitor):
                break
        else:
            lineno = self._get_new_import_lineno()
            blanks = self._get_new_import_blanks()
            self.imports.append(
                importinfo.ImportStatement(
                    import_info, lineno, lineno, blank_lines=blanks
                )
            )

    def _get_new_import_blanks(self):
        return 0

    def _get_new_import_lineno(self):
        if self.imports:
            return self.imports[-1].end_line
        return 1

    def filter_names(self, can_select):
        visitor = actions.RemovingVisitor(
            self.project, self._current_folder(), can_select
        )
        for import_statement in self.imports:
            import_statement.accept(visitor)

    def expand_stars(self):
        can_select = _OneTimeSelector(self._get_unbound_names(self.pymodule))
        visitor = actions.ExpandStarsVisitor(
            self.project, self._current_folder(), can_select
        )
        for import_statement in self.imports:
            import_statement.accept(visitor)

    def remove_duplicates(self):
        added_imports = []
        for import_stmt in self.imports:
            visitor = actions.AddingVisitor(self.project, [import_stmt.import_info])
            for added_import in added_imports:
                if added_import.accept(visitor):
                    import_stmt.empty_import()
            else:
                added_imports.append(import_stmt)

    def force_single_imports(self):
        """force a single import per statement"""
        for import_stmt in self.imports[:]:
            import_info = import_stmt.import_info
            if import_info.is_empty() or import_stmt.readonly:
                continue
            if len(import_info.names_and_aliases) > 1:
                for name_and_alias in import_info.names_and_aliases:
                    if hasattr(import_info, "module_name"):
                        new_import = importinfo.FromImport(
                            import_info.module_name, import_info.level, [name_and_alias]
                        )
                    else:
                        new_import = importinfo.NormalImport([name_and_alias])
                    self.add_import(new_import)
                import_stmt.empty_import()

    def get_relative_to_absolute_list(self):
        visitor = actions.RelativeToAbsoluteVisitor(
            self.project, self._current_folder()
        )
        for import_stmt in self.imports:
            if not import_stmt.readonly:
                import_stmt.accept(visitor)
        return visitor.to_be_absolute

    def get_self_import_fix_and_rename_list(self):
        visitor = actions.SelfImportVisitor(
            self.project, self._current_folder(), self.pymodule.get_resource()
        )
        for import_stmt in self.imports:
            if not import_stmt.readonly:
                import_stmt.accept(visitor)
        return visitor.to_be_fixed, visitor.to_be_renamed

    def _current_folder(self):
        return self.pymodule.get_resource().parent

    def sort_imports(self):
        if self.project.prefs.get("sort_imports_alphabetically"):
            sort_kwargs = dict(key=self._get_import_name)
        else:
            sort_kwargs = dict(key=self._key_imports)

        # IDEA: Sort from import list
        visitor = actions.SortingVisitor(self.project, self._current_folder())
        for import_statement in self.imports:
            import_statement.accept(visitor)
        in_projects = sorted(visitor.in_project, **sort_kwargs)
        third_party = sorted(visitor.third_party, **sort_kwargs)
        standards = sorted(visitor.standard, **sort_kwargs)
        future = sorted(visitor.future, **sort_kwargs)
        last_index = self._first_import_line()
        last_index = self._move_imports(future, last_index, 0)
        last_index = self._move_imports(standards, last_index, 1)
        last_index = self._move_imports(third_party, last_index, 1)
        last_index = self._move_imports(in_projects, last_index, 1)
        self.separating_lines = 2
        self.sorted = True

    def _first_import_line(self):
        nodes = self.pymodule.get_ast().body
        lineno = 0
        if self.pymodule.get_doc() is not None:
            lineno = 1
        if len(nodes) > lineno:
            if isinstance(nodes[lineno], ast.Import) or isinstance(
                nodes[lineno], ast.ImportFrom
            ):
                return nodes[lineno].lineno
            first_line = get_first_decorator_or_function_start_line(nodes[lineno])
            lineno = self.pymodule.logical_lines.logical_line_in(first_line)[0]
        else:
            lineno = self.pymodule.lines.length()

        return lineno - _count_blank_lines(
            self.pymodule.lines.get_line, lineno - 1, 1, -1
        )

    def _get_import_name(self, import_stmt):
        import_info = import_stmt.import_info
        if hasattr(import_info, "module_name"):
            return "{}.{}".format(
                import_info.module_name,
                import_info.names_and_aliases[0][0],
            )
        else:
            return import_info.names_and_aliases[0][0]

    def _key_imports(self, stm1):
        str1 = stm1.get_import_statement()
        return str1.startswith("from "), str1

        # str1 = stmt1.get_import_statement()
        # str2 = stmt2.get_import_statement()
        # if str1.startswith('from ') and not str2.startswith('from '):
        #    return 1
        # if not str1.startswith('from ') and str2.startswith('from '):
        #    return -1
        # return cmp(str1, str2)

    def _move_imports(self, imports, index, blank_lines):
        if imports:
            imports[0].move(index, blank_lines)
            index += 1
            if len(imports) > 1:
                for stmt in imports[1:]:
                    stmt.move(index)
                    index += 1
        return index

    def handle_long_imports(self, maxdots, maxlength):
        visitor = actions.LongImportVisitor(
            self._current_folder(), self.project, maxdots, maxlength
        )
        for import_statement in self.imports:
            if not import_statement.readonly:
                import_statement.accept(visitor)
        for import_info in visitor.new_imports:
            self.add_import(import_info)
        return visitor.to_be_renamed

    def remove_pyname(self, pyname):
        """Removes pyname when imported in ``from mod import x``"""
        visitor = actions.RemovePyNameVisitor(
            self.project, self.pymodule, pyname, self._current_folder()
        )
        for import_stmt in self.imports:
            import_stmt.accept(visitor)


def get_first_decorator_or_function_start_line(node):
    decorators = getattr(node, "decorator_list", [])
    first_line = min([decorator.lineno for decorator in decorators] + [node.lineno])
    return first_line


def _count_blank_lines(get_line, start, end, step=1):
    count = 0
    for idx in range(start, end, step):
        if get_line(idx).strip() == "":
            count += 1
        else:
            break
    return count


class _OneTimeSelector:
    def __init__(self, names):
        self.names = names
        self.selected_names = set()

    def __call__(self, imported_primary):
        if self._can_name_be_added(imported_primary):
            for name in self._get_dotted_tokens(imported_primary):
                self.selected_names.add(name)
            return True
        return False

    def _get_dotted_tokens(self, imported_primary):
        tokens = imported_primary.split(".")
        for i in range(len(tokens)):
            yield ".".join(tokens[: i + 1])

    def _can_name_be_added(self, imported_primary):
        for name in self._get_dotted_tokens(imported_primary):
            if name in self.names and name not in self.selected_names:
                return True
        return False


class _UnboundNameFinder(ast.RopeNodeVisitor):
    def __init__(self, pyobject):
        self.pyobject = pyobject

    def _visit_child_scope(self, node):
        pyobject = (
            self.pyobject.get_module()
            .get_scope()
            .get_inner_scope_for_line(node.lineno)
            .pyobject
        )
        visitor = _LocalUnboundNameFinder(pyobject, self)
        for child in ast.iter_child_nodes(node):
            visitor.visit(child)

    def _FunctionDef(self, node):
        self._visit_child_scope(node)

    def _ClassDef(self, node):
        self._visit_child_scope(node)

    def _Name(self, node):
        if self._get_root()._is_node_interesting(node) and not self.is_bound(node.id):
            self.add_unbound(node.id)

    def _Attribute(self, node):
        result = []
        while isinstance(node, ast.Attribute):
            result.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            result.append(node.id)
            primary = ".".join(reversed(result))
            if self._get_root()._is_node_interesting(node) and not self.is_bound(
                primary
            ):
                self.add_unbound(primary)
        else:
            self.visit(node)

    def _get_root(self):
        pass

    def is_bound(self, name, propagated=False):
        pass

    def add_unbound(self, name):
        pass


class _GlobalUnboundNameFinder(_UnboundNameFinder):
    def __init__(self, pymodule, wanted_pyobject):
        super().__init__(pymodule)
        self.unbound = set()
        self.names = set()
        for name, pyname in pymodule._get_structural_attributes().items():
            if not isinstance(pyname, (pynames.ImportedName, pynames.ImportedModule)):
                self.names.add(name)
        wanted_scope = wanted_pyobject.get_scope()
        self.start = wanted_scope.get_start()
        self.end = wanted_scope.get_end() + 1

    def _get_root(self):
        return self

    def is_bound(self, primary, propagated=False):
        name = primary.split(".")[0]
        return name in self.names

    def add_unbound(self, name):
        names = name.split(".")
        for i in range(len(names)):
            self.unbound.add(".".join(names[: i + 1]))

    def _is_node_interesting(self, node):
        return self.start <= node.lineno < self.end


class _LocalUnboundNameFinder(_UnboundNameFinder):
    def __init__(self, pyobject, parent):
        super().__init__(pyobject)
        self.parent = parent

    def _get_root(self):
        return self.parent._get_root()

    def is_bound(self, primary, propagated=False):
        name = primary.split(".")[0]
        if propagated:
            names = self.pyobject.get_scope().get_propagated_names()
        else:
            names = self.pyobject.get_scope().get_names()
        return name in names or self.parent.is_bound(name, propagated=True)

    def add_unbound(self, name):
        self.parent.add_unbound(name)


class _GlobalImportFinder:
    def __init__(self, pymodule):
        self.current_folder = None
        if pymodule.get_resource():
            self.current_folder = pymodule.get_resource().parent
            self.pymodule = pymodule
        self.imports = []
        self.pymodule = pymodule
        self.lines = self.pymodule.lines

    def visit_import(self, node, end_line):
        start_line = node.lineno
        import_statement = importinfo.ImportStatement(
            importinfo.NormalImport(self._get_names(node.names)),
            start_line,
            end_line,
            self._get_text(start_line, end_line),
            blank_lines=self._count_empty_lines_before(start_line),
        )
        self.imports.append(import_statement)

    def _count_empty_lines_before(self, lineno):
        return _count_blank_lines(self.lines.get_line, lineno - 1, 0, -1)

    def _count_empty_lines_after(self, lineno):
        return _count_blank_lines(self.lines.get_line, lineno + 1, self.lines.length())

    def get_separating_line_count(self):
        if not self.imports:
            return 0
        return self._count_empty_lines_after(self.imports[-1].end_line - 1)

    def _get_text(self, start_line, end_line):
        result = [self.lines.get_line(index) for index in range(start_line, end_line)]
        return "\n".join(result)

    def visit_from(self, node, end_line):
        level = 0
        if node.level:
            level = node.level
        import_info = importinfo.FromImport(
            node.module or "",
            level,
            self._get_names(node.names),
        )
        start_line = node.lineno
        self.imports.append(
            importinfo.ImportStatement(
                import_info,
                node.lineno,
                end_line,
                self._get_text(start_line, end_line),
                blank_lines=self._count_empty_lines_before(start_line),
            )
        )

    def _get_names(self, alias_names):
        return [(alias.name, alias.asname) for alias in alias_names]

    def find_import_statements(self):
        nodes = self.pymodule.get_ast().body
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                lines = self.pymodule.logical_lines
                end_line = lines.logical_line_in(node.lineno)[1] + 1
            if isinstance(node, ast.Import):
                self.visit_import(node, end_line)
            if isinstance(node, ast.ImportFrom):
                self.visit_from(node, end_line)
        return self.imports
