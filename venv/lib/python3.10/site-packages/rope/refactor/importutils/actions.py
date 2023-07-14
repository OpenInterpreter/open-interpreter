from rope.base import exceptions, libutils, pyobjects, stdmods
from rope.refactor import occurrences
from rope.refactor.importutils import importinfo


class ImportInfoVisitor:
    def dispatch(self, import_):
        try:
            method_name = "visit" + import_.import_info.__class__.__name__
            method = getattr(self, method_name)
            return method(import_, import_.import_info)
        except exceptions.ModuleNotFoundError:
            pass

    def visitEmptyImport(self, import_stmt, import_info):
        pass

    def visitNormalImport(self, import_stmt, import_info):
        pass

    def visitFromImport(self, import_stmt, import_info):
        pass


class RelativeToAbsoluteVisitor(ImportInfoVisitor):
    def __init__(self, project, current_folder):
        self.to_be_absolute = []
        self.project = project
        self.folder = current_folder
        self.context = importinfo.ImportContext(project, current_folder)

    def visitNormalImport(self, import_stmt, import_info):
        self.to_be_absolute.extend(self._get_relative_to_absolute_list(import_info))
        new_pairs = []
        for name, alias in import_info.names_and_aliases:
            resource = self.project.find_module(name, folder=self.folder)
            if resource is None:
                new_pairs.append((name, alias))
                continue
            absolute_name = libutils.modname(resource)
            new_pairs.append((absolute_name, alias))
        if not import_info._are_name_and_alias_lists_equal(
            new_pairs, import_info.names_and_aliases
        ):
            import_stmt.import_info = importinfo.NormalImport(new_pairs)

    def _get_relative_to_absolute_list(self, import_info):
        result = []
        for name, alias in import_info.names_and_aliases:
            if alias is not None:
                continue
            resource = self.project.find_module(name, folder=self.folder)
            if resource is None:
                continue
            absolute_name = libutils.modname(resource)
            if absolute_name != name:
                result.append((name, absolute_name))
        return result

    def visitFromImport(self, import_stmt, import_info):
        resource = import_info.get_imported_resource(self.context)
        if resource is None:
            return None
        absolute_name = libutils.modname(resource)
        if import_info.module_name != absolute_name:
            import_stmt.import_info = importinfo.FromImport(
                absolute_name, 0, import_info.names_and_aliases
            )


class FilteringVisitor(ImportInfoVisitor):
    def __init__(self, project, folder, can_select):
        self.to_be_absolute = []
        self.project = project
        self.can_select = self._transform_can_select(can_select)
        self.context = importinfo.ImportContext(project, folder)

    def _transform_can_select(self, can_select):
        def can_select_name_and_alias(name, alias):
            imported = name
            if alias is not None:
                imported = alias
            return can_select(imported)

        return can_select_name_and_alias

    def visitNormalImport(self, import_stmt, import_info):
        new_pairs = [
            (name, alias)
            for name, alias in import_info.names_and_aliases
            if self.can_select(name, alias)
        ]
        return importinfo.NormalImport(new_pairs)

    def visitFromImport(self, import_stmt, import_info):
        if _is_future(import_info):
            return import_info
        new_pairs = []
        if import_info.is_star_import():
            for name in import_info.get_imported_names(self.context):
                if self.can_select(name, None):
                    new_pairs.append(import_info.names_and_aliases[0])
                    break
        else:
            for name, alias in import_info.names_and_aliases:
                if self.can_select(name, alias):
                    new_pairs.append((name, alias))
        return importinfo.FromImport(
            import_info.module_name, import_info.level, new_pairs
        )


class RemovingVisitor(ImportInfoVisitor):
    def __init__(self, project, folder, can_select):
        self.to_be_absolute = []
        self.project = project
        self.filtering = FilteringVisitor(project, folder, can_select)

    def dispatch(self, import_):
        result = self.filtering.dispatch(import_)
        if result is not None:
            import_.import_info = result


class AddingVisitor(ImportInfoVisitor):
    """A class for adding imports

    Given a list of `ImportInfo`, it tries to add each import to the
    module and returns `True` and gives up when an import can be added
    to older ones.

    """

    def __init__(self, project, import_list):
        self.project = project
        self.import_list = import_list
        self.import_info = None

    def dispatch(self, import_):
        for import_info in self.import_list:
            self.import_info = import_info
            if ImportInfoVisitor.dispatch(self, import_):
                return True

    # TODO: Handle adding relative and absolute imports
    def visitNormalImport(self, import_stmt, import_info):
        if not isinstance(self.import_info, import_info.__class__):
            return False
        # Adding ``import x`` and ``import x.y`` that results ``import x.y``
        if (
            len(import_info.names_and_aliases)
            == len(self.import_info.names_and_aliases)
            == 1
        ):
            imported1 = import_info.names_and_aliases[0]
            imported2 = self.import_info.names_and_aliases[0]
            if imported1[1] == imported2[1] is None:
                if imported1[0].startswith(imported2[0] + "."):
                    return True
                if imported2[0].startswith(imported1[0] + "."):
                    import_stmt.import_info = self.import_info
                    return True
        # Multiple imports using a single import statement is discouraged
        # so we won't bother adding them.
        if self.import_info._are_name_and_alias_lists_equal(
            import_info.names_and_aliases, self.import_info.names_and_aliases
        ):
            return True

    def visitFromImport(self, import_stmt, import_info):
        if (
            isinstance(self.import_info, import_info.__class__)
            and import_info.module_name == self.import_info.module_name
            and import_info.level == self.import_info.level
        ):
            if import_info.is_star_import():
                return True
            if self.import_info.is_star_import():
                import_stmt.import_info = self.import_info
                return True
            if self.project.prefs.get("split_imports"):
                return (
                    self.import_info.names_and_aliases == import_info.names_and_aliases
                )
            new_pairs = list(import_info.names_and_aliases)
            for pair in self.import_info.names_and_aliases:
                if pair not in new_pairs:
                    new_pairs.append(pair)
            import_stmt.import_info = importinfo.FromImport(
                import_info.module_name, import_info.level, new_pairs
            )
            return True


class ExpandStarsVisitor(ImportInfoVisitor):
    def __init__(self, project, folder, can_select):
        self.project = project
        self.filtering = FilteringVisitor(project, folder, can_select)
        self.context = importinfo.ImportContext(project, folder)

    def visitNormalImport(self, import_stmt, import_info):
        self.filtering.dispatch(import_stmt)

    def visitFromImport(self, import_stmt, import_info):
        if import_info.is_star_import():
            new_pairs = [
                (name, None) for name in import_info.get_imported_names(self.context)
            ]
            new_import = importinfo.FromImport(
                import_info.module_name, import_info.level, new_pairs
            )
            import_stmt.import_info = self.filtering.visitFromImport(None, new_import)
        else:
            self.filtering.dispatch(import_stmt)


class SelfImportVisitor(ImportInfoVisitor):
    def __init__(self, project, current_folder, resource):
        self.project = project
        self.folder = current_folder
        self.resource = resource
        self.to_be_fixed = set()
        self.to_be_renamed = set()
        self.context = importinfo.ImportContext(project, current_folder)

    def visitNormalImport(self, import_stmt, import_info):
        new_pairs = []
        for name, alias in import_info.names_and_aliases:
            resource = self.project.find_module(name, folder=self.folder)
            if resource is not None and resource == self.resource:
                imported = name
                if alias is not None:
                    imported = alias
                self.to_be_fixed.add(imported)
            else:
                new_pairs.append((name, alias))
        if not import_info._are_name_and_alias_lists_equal(
            new_pairs, import_info.names_and_aliases
        ):
            import_stmt.import_info = importinfo.NormalImport(new_pairs)

    def visitFromImport(self, import_stmt, import_info):
        resource = import_info.get_imported_resource(self.context)
        if resource is None:
            return
        if resource == self.resource:
            self._importing_names_from_self(import_info, import_stmt)
            return
        pymodule = self.project.get_pymodule(resource)
        new_pairs = []
        for name, alias in import_info.names_and_aliases:
            try:
                result = pymodule[name].get_object()
                if (
                    isinstance(result, pyobjects.PyModule)
                    and result.get_resource() == self.resource
                ):
                    imported = name
                    if alias is not None:
                        imported = alias
                    self.to_be_fixed.add(imported)
                else:
                    new_pairs.append((name, alias))
            except exceptions.AttributeNotFoundError:
                new_pairs.append((name, alias))
        if not import_info._are_name_and_alias_lists_equal(
            new_pairs, import_info.names_and_aliases
        ):
            import_stmt.import_info = importinfo.FromImport(
                import_info.module_name, import_info.level, new_pairs
            )

    def _importing_names_from_self(self, import_info, import_stmt):
        if not import_info.is_star_import():
            for name, alias in import_info.names_and_aliases:
                if alias is not None:
                    self.to_be_renamed.add((alias, name))
        import_stmt.empty_import()


class SortingVisitor(ImportInfoVisitor):
    def __init__(self, project, current_folder):
        self.project = project
        self.folder = current_folder
        self.standard = set()
        self.third_party = set()
        self.in_project = set()
        self.future = set()
        self.context = importinfo.ImportContext(project, current_folder)

    def visitNormalImport(self, import_stmt, import_info):
        if import_info.names_and_aliases:
            name, alias = import_info.names_and_aliases[0]
            resource = self.project.find_module(name, folder=self.folder)
            self._check_imported_resource(import_stmt, resource, name)

    def visitFromImport(self, import_stmt, import_info):
        resource = import_info.get_imported_resource(self.context)
        self._check_imported_resource(import_stmt, resource, import_info.module_name)

    def _check_imported_resource(self, import_stmt, resource, imported_name):
        info = import_stmt.import_info
        if resource is not None and resource.project == self.project:
            self.in_project.add(import_stmt)
        elif _is_future(info):
            self.future.add(import_stmt)
        elif imported_name.split(".")[0] in stdmods.standard_modules():
            self.standard.add(import_stmt)
        else:
            self.third_party.add(import_stmt)


class LongImportVisitor(ImportInfoVisitor):
    def __init__(self, current_folder, project, maxdots, maxlength):
        self.maxdots = maxdots
        self.maxlength = maxlength
        self.to_be_renamed = set()
        self.current_folder = current_folder
        self.project = project
        self.new_imports = []

    def visitNormalImport(self, import_stmt, import_info):
        for name, alias in import_info.names_and_aliases:
            if alias is None and self._is_long(name):
                self.to_be_renamed.add(name)
                last_dot = name.rindex(".")
                from_ = name[:last_dot]
                imported = name[last_dot + 1 :]
                self.new_imports.append(
                    importinfo.FromImport(from_, 0, ((imported, None),))
                )

    def _is_long(self, name):
        return name.count(".") > self.maxdots or (
            "." in name and len(name) > self.maxlength
        )


class RemovePyNameVisitor(ImportInfoVisitor):
    def __init__(self, project, pymodule, pyname, folder):
        self.pymodule = pymodule
        self.pyname = pyname
        self.context = importinfo.ImportContext(project, folder)

    def visitFromImport(self, import_stmt, import_info):
        new_pairs = []
        if not import_info.is_star_import():
            for name, alias in import_info.names_and_aliases:
                try:
                    pyname = self.pymodule[alias or name]
                    if occurrences.same_pyname(self.pyname, pyname):
                        continue
                except exceptions.AttributeNotFoundError:
                    pass
                new_pairs.append((name, alias))
        return importinfo.FromImport(
            import_info.module_name, import_info.level, new_pairs
        )

    def dispatch(self, import_):
        result = ImportInfoVisitor.dispatch(self, import_)
        if result is not None:
            import_.import_info = result


def _is_future(info):
    return isinstance(info, importinfo.FromImport) and info.module_name == "__future__"
