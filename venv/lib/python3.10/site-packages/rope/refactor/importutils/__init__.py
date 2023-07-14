"""A package for handling imports

This package provides tools for modifying module imports after
refactorings or as a separate task.

"""
import rope.base.codeanalyze
import rope.base.evaluate
from rope.base import libutils
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import occurrences, rename
from rope.refactor.importutils import actions, module_imports
from rope.refactor.importutils.importinfo import FromImport, NormalImport


class ImportOrganizer:
    """Perform some import-related commands

    Each method returns a `rope.base.change.Change` object.

    """

    def __init__(self, project):
        self.project = project
        self.import_tools = ImportTools(self.project)

    def organize_imports(self, resource, offset=None):
        return self._perform_command_on_import_tools(
            self.import_tools.organize_imports, resource, offset
        )

    def expand_star_imports(self, resource, offset=None):
        return self._perform_command_on_import_tools(
            self.import_tools.expand_stars, resource, offset
        )

    def froms_to_imports(self, resource, offset=None):
        return self._perform_command_on_import_tools(
            self.import_tools.froms_to_imports, resource, offset
        )

    def relatives_to_absolutes(self, resource, offset=None):
        return self._perform_command_on_import_tools(
            self.import_tools.relatives_to_absolutes, resource, offset
        )

    def handle_long_imports(self, resource, offset=None):
        return self._perform_command_on_import_tools(
            self.import_tools.handle_long_imports, resource, offset
        )

    def _perform_command_on_import_tools(self, method, resource, offset):
        pymodule = self.project.get_pymodule(resource)
        before_performing = pymodule.source_code
        import_filter = None
        if offset is not None:
            import_filter = self._line_filter(pymodule.lines.get_line_number(offset))
        result = method(pymodule, import_filter=import_filter)
        if result is not None and result != before_performing:
            changes = ChangeSet(
                method.__name__.replace("_", " ") + " in <%s>" % resource.path
            )
            changes.add_change(ChangeContents(resource, result))
            return changes

    def _line_filter(self, lineno):
        def import_filter(import_stmt):
            return import_stmt.start_line <= lineno < import_stmt.end_line

        return import_filter


class ImportTools:
    def __init__(self, project):
        self.project = project

    def get_import(self, resource):
        """The import statement for `resource`"""
        module_name = libutils.modname(resource)
        return NormalImport(((module_name, None),))

    def get_from_import(self, resource, name):
        """The from import statement for `name` in `resource`"""
        module_name = libutils.modname(resource)
        names = []
        if isinstance(name, list):
            names = [(imported, None) for imported in name]
        else:
            names = [
                (name, None),
            ]
        return FromImport(module_name, 0, tuple(names))

    def module_imports(self, module, imports_filter=None):
        return module_imports.ModuleImports(self.project, module, imports_filter)

    def froms_to_imports(self, pymodule, import_filter=None):
        pymodule = self._clean_up_imports(pymodule, import_filter)
        module_imports = self.module_imports(pymodule, import_filter)
        for import_stmt in module_imports.imports:
            if import_stmt.readonly or not self._is_transformable_to_normal(
                import_stmt.import_info
            ):
                continue
            pymodule = self._from_to_normal(pymodule, import_stmt)

        # Adding normal imports in place of froms
        module_imports = self.module_imports(pymodule, import_filter)
        for import_stmt in module_imports.imports:
            if not import_stmt.readonly and self._is_transformable_to_normal(
                import_stmt.import_info
            ):
                import_stmt.import_info = NormalImport(
                    ((import_stmt.import_info.module_name, None),)
                )
        module_imports.remove_duplicates()
        return module_imports.get_changed_source()

    def expand_stars(self, pymodule, import_filter=None):
        module_imports = self.module_imports(pymodule, import_filter)
        module_imports.expand_stars()
        return module_imports.get_changed_source()

    def _from_to_normal(self, pymodule, import_stmt):
        resource = pymodule.get_resource()
        from_import = import_stmt.import_info
        module_name = from_import.module_name
        for name, alias in from_import.names_and_aliases:
            imported = name
            if alias is not None:
                imported = alias
            occurrence_finder = occurrences.create_finder(
                self.project,
                imported,
                pymodule[imported],
                imports=False,
                keywords=False,
            )
            source = rename.rename_in_module(
                occurrence_finder,
                module_name + "." + name,
                pymodule=pymodule,
                replace_primary=True,
            )
            if source is not None:
                pymodule = libutils.get_string_module(self.project, source, resource)
        return pymodule

    def _clean_up_imports(self, pymodule, import_filter):
        resource = pymodule.get_resource()
        module_with_imports = self.module_imports(pymodule, import_filter)
        module_with_imports.expand_stars()
        source = module_with_imports.get_changed_source()
        if source is not None:
            pymodule = libutils.get_string_module(self.project, source, resource)
        source = self.relatives_to_absolutes(pymodule)
        if source is not None:
            pymodule = libutils.get_string_module(self.project, source, resource)

        module_with_imports = self.module_imports(pymodule, import_filter)
        module_with_imports.remove_duplicates()
        module_with_imports.remove_unused_imports()
        source = module_with_imports.get_changed_source()
        if source is not None:
            pymodule = libutils.get_string_module(self.project, source, resource)
        return pymodule

    def relatives_to_absolutes(self, pymodule, import_filter=None):
        module_imports = self.module_imports(pymodule, import_filter)
        to_be_absolute_list = module_imports.get_relative_to_absolute_list()
        for name, absolute_name in to_be_absolute_list:
            pymodule = self._rename_in_module(pymodule, name, absolute_name)
        module_imports = self.module_imports(pymodule, import_filter)
        module_imports.get_relative_to_absolute_list()
        source = module_imports.get_changed_source()
        if source is None:
            source = pymodule.source_code
        return source

    def _is_transformable_to_normal(self, import_info):
        return isinstance(import_info, FromImport)

    def organize_imports(
        self,
        pymodule,
        unused=True,
        duplicates=True,
        selfs=True,
        sort=True,
        import_filter=None,
    ):
        if unused or duplicates:
            module_imports = self.module_imports(pymodule, import_filter)
            if unused:
                module_imports.remove_unused_imports()
            if self.project.prefs.get("split_imports"):
                module_imports.force_single_imports()
            if duplicates:
                module_imports.remove_duplicates()
            source = module_imports.get_changed_source()
            if source is not None:
                pymodule = libutils.get_string_module(
                    self.project, source, pymodule.get_resource()
                )
        if selfs:
            pymodule = self._remove_self_imports(pymodule, import_filter)
        if sort:
            return self.sort_imports(pymodule, import_filter)
        else:
            return pymodule.source_code

    def _remove_self_imports(self, pymodule, import_filter=None):
        module_imports = self.module_imports(pymodule, import_filter)
        (
            to_be_fixed,
            to_be_renamed,
        ) = module_imports.get_self_import_fix_and_rename_list()
        for name in to_be_fixed:
            try:
                pymodule = self._rename_in_module(pymodule, name, "", till_dot=True)
            except ValueError:
                # There is a self import with direct access to it
                return pymodule
        for name, new_name in to_be_renamed:
            pymodule = self._rename_in_module(pymodule, name, new_name)
        module_imports = self.module_imports(pymodule, import_filter)
        module_imports.get_self_import_fix_and_rename_list()
        source = module_imports.get_changed_source()
        if source is not None:
            pymodule = libutils.get_string_module(
                self.project, source, pymodule.get_resource()
            )
        return pymodule

    def _rename_in_module(self, pymodule, name, new_name, till_dot=False):
        old_name = name.split(".")[-1]
        old_pyname = rope.base.evaluate.eval_str(pymodule.get_scope(), name)
        occurrence_finder = occurrences.create_finder(
            self.project, old_name, old_pyname, imports=False
        )
        changes = rope.base.codeanalyze.ChangeCollector(pymodule.source_code)
        for occurrence in occurrence_finder.find_occurrences(pymodule=pymodule):
            start, end = occurrence.get_primary_range()
            if till_dot:
                new_end = pymodule.source_code.index(".", end) + 1
                space = pymodule.source_code[end : new_end - 1].strip()
                if not space == "":
                    for c in space:
                        if not c.isspace() and c not in "\\":
                            raise ValueError()
                end = new_end
            changes.add_change(start, end, new_name)
        source = changes.get_changed()
        if source is not None:
            pymodule = libutils.get_string_module(
                self.project, source, pymodule.get_resource()
            )
        return pymodule

    def sort_imports(self, pymodule, import_filter=None):
        module_imports = self.module_imports(pymodule, import_filter)
        module_imports.sort_imports()
        return module_imports.get_changed_source()

    def handle_long_imports(
        self, pymodule, maxdots=2, maxlength=27, import_filter=None
    ):
        # IDEA: `maxdots` and `maxlength` can be specified in project config
        # adding new from imports
        module_imports = self.module_imports(pymodule, import_filter)
        to_be_fixed = module_imports.handle_long_imports(maxdots, maxlength)
        # performing the renaming
        pymodule = libutils.get_string_module(
            self.project,
            module_imports.get_changed_source(),
            resource=pymodule.get_resource(),
        )
        for name in to_be_fixed:
            pymodule = self._rename_in_module(pymodule, name, name.split(".")[-1])
        # organizing imports
        return self.organize_imports(
            pymodule, selfs=False, sort=False, import_filter=import_filter
        )


def get_imports(project, pydefined):
    """A shortcut for getting the `ImportInfo` used in a scope"""
    pymodule = pydefined.get_module()
    module = module_imports.ModuleImports(project, pymodule)
    if pymodule == pydefined:
        return [stmt.import_info for stmt in module.imports]
    return module.get_used_imports(pydefined)


def get_module_imports(project, pymodule):
    """A shortcut for creating a `module_imports.ModuleImports` object"""
    return module_imports.ModuleImports(project, pymodule)


def add_import(project, pymodule, module_name, name=None):
    imports = get_module_imports(project, pymodule)
    candidates = []
    names = []
    selected_import = None
    # from mod import name
    if name is not None:
        from_import = FromImport(module_name, 0, [(name, None)])
        names.append(name)
        candidates.append(from_import)
    # from pkg import mod
    if "." in module_name:
        pkg, mod = module_name.rsplit(".", 1)
        from_import = FromImport(pkg, 0, [(mod, None)])
        if project.prefs.get("prefer_module_from_imports"):
            selected_import = from_import
        candidates.append(from_import)
        if name:
            names.append(mod + "." + name)
        else:
            names.append(mod)
    # import mod
    normal_import = NormalImport([(module_name, None)])
    if name:
        names.append(module_name + "." + name)
    else:
        names.append(module_name)

    candidates.append(normal_import)

    visitor = actions.AddingVisitor(project, candidates)
    if selected_import is None:
        selected_import = normal_import
    for import_statement in imports.imports:
        if import_statement.accept(visitor):
            selected_import = visitor.import_info
            break
    imports.add_import(selected_import)
    imported_name = names[candidates.index(selected_import)]
    return imports.get_changed_source(), imported_name
