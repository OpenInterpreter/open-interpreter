# Known Bugs when inlining a function/method
# The values passed to function are inlined using _inlined_variable.
# This may cause two problems, illustrated in the examples below
#
# def foo(var1):
#    var1 = var1*10
#    return var1
#
#  If a call to foo(20) is inlined, the result of inlined function is 20,
#  but it should be 200.
#
# def foo(var1):
#    var2 = var1*10
#    return var2
#
# 2- If a call to foo(10+10) is inlined the result of inlined function is 110
#  but it should be 200.

import re
from typing import List

import rope.base.builtins  # Use fully qualified names for clarity.
from rope.base import (
    codeanalyze,
    evaluate,
    exceptions,
    libutils,
    pynames,
    pyobjects,
    taskhandle,
    utils,
    worder,
)
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import (
    change_signature,
    functionutils,
    importutils,
    move,
    occurrences,
    rename,
    sourceutils,
)


def unique_prefix():
    n = 0
    while True:
        yield "__" + str(n) + "__"
        n += 1


def create_inline(project, resource, offset):
    """Create a refactoring object for inlining

    Based on `resource` and `offset` it returns an instance of
    `InlineMethod`, `InlineVariable` or `InlineParameter`.

    """
    pyname = _get_pyname(project, resource, offset)
    message = (
        "Inline refactoring should be performed on "
        "a method, local variable or parameter."
    )
    if pyname is None:
        raise exceptions.RefactoringError(message)
    if isinstance(pyname, pynames.ImportedName):
        pyname = pyname._get_imported_pyname()
    if isinstance(pyname, pynames.AssignedName):
        return InlineVariable(project, resource, offset)
    if isinstance(pyname, pynames.ParameterName):
        return InlineParameter(project, resource, offset)
    if isinstance(pyname.get_object(), pyobjects.PyFunction):
        return InlineMethod(project, resource, offset)
    else:
        raise exceptions.RefactoringError(message)


class _Inliner:
    def __init__(self, project, resource, offset):
        self.project = project
        self.pyname = _get_pyname(project, resource, offset)
        range_finder = worder.Worder(resource.read(), True)
        self.region = range_finder.get_primary_range(offset)
        self.name = range_finder.get_word_at(offset)
        self.offset = offset
        self.original = resource

    def get_changes(self, *args, **kwds):
        pass

    def get_kind(self):
        """Return either 'variable', 'method' or 'parameter'"""


class InlineMethod(_Inliner):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.pyfunction = self.pyname.get_object()
        self.pymodule = self.pyfunction.get_module()
        self.resource = self.pyfunction.get_module().get_resource()
        self.occurrence_finder = occurrences.create_finder(
            self.project, self.name, self.pyname
        )
        self.normal_generator = _DefinitionGenerator(self.project, self.pyfunction)
        self._init_imports()

    def _init_imports(self):
        body = sourceutils.get_body(self.pyfunction)
        body, imports = move.moving_code_with_imports(self.project, self.resource, body)
        self.imports = imports
        self.others_generator = _DefinitionGenerator(
            self.project, self.pyfunction, body=body
        )

    def _get_scope_range(self):
        scope = self.pyfunction.get_scope()
        lines = self.pymodule.lines
        start_line = scope.get_start()
        if self.pyfunction.decorators:
            decorators = self.pyfunction.decorators
            if hasattr(decorators[0], "lineno"):
                start_line = decorators[0].lineno
        start_offset = lines.get_line_start(start_line)
        end_offset = min(
            lines.get_line_end(scope.end) + 1, len(self.pymodule.source_code)
        )
        return (start_offset, end_offset)

    def get_changes(
        self,
        remove=True,
        only_current=False,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get the changes this refactoring makes

        If `remove` is `False` the definition will not be removed.  If
        `only_current` is `True`, the the current occurrence will be
        inlined, only.
        """
        changes = ChangeSet("Inline method <%s>" % self.name)
        if resources is None:
            resources = self.project.get_python_files()
        if only_current:
            resources = [self.original]
            if remove:
                resources.append(self.resource)
        job_set = task_handle.create_jobset("Collecting Changes", len(resources))
        for file in resources:
            job_set.started_job(file.path)
            if file == self.resource:
                changes.add_change(
                    self._defining_file_changes(
                        changes, remove=remove, only_current=only_current
                    )
                )
            else:
                aim = None
                if only_current and self.original == file:
                    aim = self.offset
                handle = _InlineFunctionCallsForModuleHandle(
                    self.project, file, self.others_generator, aim
                )
                result = move.ModuleSkipRenamer(
                    self.occurrence_finder, file, handle
                ).get_changed_module()
                if result is not None:
                    result = _add_imports(self.project, result, file, self.imports)
                    if remove:
                        result = _remove_from(self.project, self.pyname, result, file)
                    changes.add_change(ChangeContents(file, result))
            job_set.finished_job()
        return changes

    def _get_removed_range(self):
        scope = self.pyfunction.get_scope()
        lines = self.pymodule.lines
        start, end = self._get_scope_range()
        end_line = scope.get_end()
        for i in range(end_line + 1, lines.length()):
            if lines.get_line(i).strip() == "":
                end_line = i
            else:
                break
        end = min(lines.get_line_end(end_line) + 1, len(self.pymodule.source_code))
        return (start, end)

    def _defining_file_changes(self, changes, remove, only_current):
        start_offset, end_offset = self._get_removed_range()
        aim = None
        if only_current:
            if self.resource == self.original:
                aim = self.offset
            else:
                # we don't want to change any of them
                aim = len(self.resource.read()) + 100
        handle = _InlineFunctionCallsForModuleHandle(
            self.project, self.resource, self.normal_generator, aim_offset=aim
        )
        replacement = None
        if remove:
            replacement = self._get_method_replacement()
        result = move.ModuleSkipRenamer(
            self.occurrence_finder,
            self.resource,
            handle,
            start_offset,
            end_offset,
            replacement,
        ).get_changed_module()
        return ChangeContents(self.resource, result)

    def _get_method_replacement(self):
        if self._is_the_last_method_of_a_class():
            indents = sourceutils.get_indents(
                self.pymodule.lines, self.pyfunction.get_scope().get_start()
            )
            return " " * indents + "pass\n"
        return ""

    def _is_the_last_method_of_a_class(self):
        pyclass = self.pyfunction.parent
        if not isinstance(pyclass, pyobjects.PyClass):
            return False
        class_start, class_end = sourceutils.get_body_region(pyclass)
        source = self.pymodule.source_code
        func_start, func_end = self._get_scope_range()
        return (
            source[class_start:func_start].strip() == ""
            and source[func_end:class_end].strip() == ""
        )

    def get_kind(self):
        return "method"


class InlineVariable(_Inliner):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.pymodule = self.pyname.get_definition_location()[0]
        self.resource = self.pymodule.get_resource()
        self._check_exceptional_conditions()
        self._init_imports()

    def _check_exceptional_conditions(self):
        if len(self.pyname.assignments) != 1:
            raise exceptions.RefactoringError(
                "Local variable should be assigned once for inlining."
            )

    def get_changes(
        self,
        remove=True,
        only_current=False,
        resources=None,
        docs=False,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        if resources is None:
            if rename._is_local(self.pyname):
                resources = [self.resource]
            else:
                resources = self.project.get_python_files()
        if only_current:
            resources = [self.original]
            if remove and self.original != self.resource:
                resources.append(self.resource)
        changes = ChangeSet("Inline variable <%s>" % self.name)
        jobset = task_handle.create_jobset("Calculating changes", len(resources))

        for resource in resources:
            jobset.started_job(resource.path)
            if resource == self.resource:
                source = self._change_main_module(remove, only_current, docs)
                changes.add_change(ChangeContents(self.resource, source))
            else:
                result = self._change_module(resource, remove, only_current)
                if result is not None:
                    result = _add_imports(self.project, result, resource, self.imports)
                    changes.add_change(ChangeContents(resource, result))
            jobset.finished_job()
        return changes

    def _change_main_module(self, remove, only_current, docs):
        region = None
        if only_current and self.original == self.resource:
            region = self.region
        return _inline_variable(
            self.project,
            self.pymodule,
            self.pyname,
            self.name,
            remove=remove,
            region=region,
            docs=docs,
        )

    def _init_imports(self):
        vardef = _getvardef(self.pymodule, self.pyname)
        self.imported, self.imports = move.moving_code_with_imports(
            self.project, self.resource, vardef
        )

    def _change_module(self, resource, remove, only_current):
        filters = [occurrences.NoImportsFilter(), occurrences.PyNameFilter(self.pyname)]
        if only_current and resource == self.original:

            def check_aim(occurrence):
                start, end = occurrence.get_primary_range()
                if self.offset < start or end < self.offset:
                    return False

            filters.insert(0, check_aim)
        finder = occurrences.Finder(self.project, self.name, filters=filters)
        changed = rename.rename_in_module(
            finder, self.imported, resource=resource, replace_primary=True
        )
        if changed and remove:
            changed = _remove_from(self.project, self.pyname, changed, resource)
        return changed

    def get_kind(self):
        return "variable"


class InlineParameter(_Inliner):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        resource, offset = self._function_location()
        index = self.pyname.index
        self.changers = [change_signature.ArgumentDefaultInliner(index)]
        self.signature = change_signature.ChangeSignature(
            self.project, resource, offset
        )

    def _function_location(self):
        pymodule, lineno = self.pyname.get_definition_location()
        resource = pymodule.get_resource()
        start = pymodule.lines.get_line_start(lineno)
        word_finder = worder.Worder(pymodule.source_code)
        offset = word_finder.find_function_offset(start)
        return resource, offset

    def get_changes(self, **kwds):
        """Get the changes needed by this refactoring

        See `rope.refactor.change_signature.ChangeSignature.get_changes()`
        for arguments.
        """
        return self.signature.get_changes(self.changers, **kwds)

    def get_kind(self):
        return "parameter"


def _join_lines(lines: List[str]) -> str:
    return "\n".join(lines)


class _ComplexExpressionVisitor:
    def __init__(self):
        self.is_complex_expression = False

    def _Set(self, node):
        self.is_complex_expression = True

    def _List(self, node):
        self.is_complex_expression = True

    def _Tuple(self, node):
        self.is_complex_expression = True

    def _Dict(self, node):
        self.is_complex_expression = True


class _DefinitionGenerator:
    unique_prefix = unique_prefix()

    def __init__(self, project, pyfunction, body=None):
        self.project = project
        self.pyfunction = pyfunction
        self.pymodule = pyfunction.get_module()
        self.resource = self.pymodule.get_resource()
        self.definition_info = self._get_definition_info()
        self.definition_params = self._get_definition_params()
        self._calculated_definitions = {}
        if body is not None:
            self.body = body
        else:
            self.body = sourceutils.get_body(self.pyfunction)

    def _get_definition_info(self):
        return functionutils.DefinitionInfo.read(self.pyfunction)

    def _get_definition_params(self):
        definition_info = self.definition_info
        paramdict = dict([pair for pair in definition_info.args_with_defaults])
        if (
            definition_info.args_arg is not None
            or definition_info.keywords_arg is not None
        ):
            raise exceptions.RefactoringError(
                "Cannot inline functions with list and keyword arguments."
            )
        if self.pyfunction.get_kind() == "classmethod":
            paramdict[
                definition_info.args_with_defaults[0][0]
            ] = self.pyfunction.parent.get_name()
        return paramdict

    def get_function_name(self):
        return self.pyfunction.get_name()

    def get_definition(self, primary, pyname, call, host_vars=None, returns=False):
        # caching already calculated definitions
        if host_vars is None:
            host_vars = []
        return self._calculate_definition(primary, pyname, call, host_vars, returns)

    def _calculate_header(self, primary, pyname, call):
        # A header is created which initializes parameters
        # to the values passed to the function.
        call_info = functionutils.CallInfo.read(
            primary, pyname, self.definition_info, call
        )
        paramdict = self.definition_params
        mapping = functionutils.ArgumentMapping(self.definition_info, call_info)
        for param_name, value in mapping.param_dict.items():
            paramdict[param_name] = value
        header = ""
        to_be_inlined = []
        for name, value in paramdict.items():
            if name != value and value is not None:
                header += name + " = " + value.replace("\n", " ") + "\n"
                to_be_inlined.append(name)
        return header, to_be_inlined

    def _calculate_definition(self, primary, pyname, call, host_vars, returns):

        header, to_be_inlined = self._calculate_header(primary, pyname, call)

        source = header + self.body
        mod = libutils.get_string_module(self.project, source)
        name_dict = mod.get_scope().get_names()
        all_names = [
            x
            for x in name_dict
            if not isinstance(name_dict[x], rope.base.builtins.BuiltinName)
        ]

        # If there is a name conflict, all variable names
        # inside the inlined function are renamed
        if set(all_names).intersection(set(host_vars)):

            prefix = next(_DefinitionGenerator.unique_prefix)
            guest = libutils.get_string_module(self.project, source, self.resource)

            to_be_inlined = [prefix + item for item in to_be_inlined]
            for item in all_names:
                pyname = guest[item]
                occurrence_finder = occurrences.create_finder(
                    self.project, item, pyname
                )
                source = rename.rename_in_module(
                    occurrence_finder, prefix + item, pymodule=guest
                )
                guest = libutils.get_string_module(self.project, source, self.resource)

        # parameters not reassigned inside the functions are now inlined.
        for name in to_be_inlined:
            pymodule = libutils.get_string_module(self.project, source, self.resource)
            pyname = pymodule[name]
            source = _inline_variable(self.project, pymodule, pyname, name)

        return self._replace_returns_with(source, returns)

    def _replace_returns_with(self, source, returns):
        result = []
        returned = None
        last_changed = 0
        for match in _DefinitionGenerator._get_return_pattern().finditer(source):
            for key, value in match.groupdict().items():
                if value and key == "return":
                    result.append(source[last_changed : match.start("return")])
                    if returns:
                        self._check_nothing_after_return(source, match.end("return"))
                        beg_idx = match.end("return")
                        returned = _join_lines(
                            source[beg_idx : len(source)].lstrip().splitlines(),
                        )
                        last_changed = len(source)
                    else:
                        current = match.end("return")
                        while current < len(source) and source[current] in " \t":
                            current += 1
                        last_changed = current
                        if current == len(source) or source[current] == "\n":
                            result.append("pass")
        result.append(source[last_changed:])
        return "".join(result), returned

    def _check_nothing_after_return(self, source, offset):
        lines = codeanalyze.SourceLinesAdapter(source)
        lineno = lines.get_line_number(offset)
        logical_lines = codeanalyze.LogicalLineFinder(lines)
        lineno = logical_lines.logical_line_in(lineno)[1]
        if source[lines.get_line_end(lineno) : len(source)].strip() != "":
            raise exceptions.RefactoringError(
                "Cannot inline functions with statements " + "after return statement."
            )

    @classmethod
    def _get_return_pattern(cls):
        if not hasattr(cls, "_return_pattern"):

            def named_pattern(name, list_):
                return "(?P<%s>" % name + "|".join(list_) + ")"

            comment_pattern = named_pattern("comment", [r"#[^\n]*"])
            string_pattern = named_pattern("string", [codeanalyze.get_string_pattern()])
            return_pattern = r"\b(?P<return>return)\b"
            cls._return_pattern = re.compile(
                comment_pattern + "|" + string_pattern + "|" + return_pattern
            )
        return cls._return_pattern


class _InlineFunctionCallsForModuleHandle:
    def __init__(self, project, resource, definition_generator, aim_offset=None):
        """Inlines occurrences

        If `aim` is not `None` only the occurrences that intersect
        `aim` offset will be inlined.

        """
        self.project = project
        self.generator = definition_generator
        self.resource = resource
        self.aim = aim_offset

    def occurred_inside_skip(self, change_collector, occurrence):
        if not occurrence.is_defined():
            raise exceptions.RefactoringError(
                "Cannot inline functions that reference themselves"
            )

    def occurred_outside_skip(self, change_collector, occurrence):
        start, end = occurrence.get_primary_range()
        # we remove out of date imports later
        if occurrence.is_in_import_statement():
            return
        # the function is referenced outside an import statement
        if not occurrence.is_called():
            raise exceptions.RefactoringError(
                "Reference to inlining function other than function call"
                " in <file: %s, offset: %d>" % (self.resource.path, start)
            )
        if self.aim is not None and (self.aim < start or self.aim > end):
            return
        end_parens = self._find_end_parens(self.source, end - 1)
        lineno = self.lines.get_line_number(start)
        start_line, end_line = self.pymodule.logical_lines.logical_line_in(lineno)
        line_start = self.lines.get_line_start(start_line)
        line_end = self.lines.get_line_end(end_line)

        returns = (
            self.source[line_start:start].strip() != ""
            or self.source[end_parens:line_end].strip() != ""
        )
        indents = sourceutils.get_indents(self.lines, start_line)
        primary, pyname = occurrence.get_primary_and_pyname()

        host = self.pymodule
        scope = host.scope.get_inner_scope_for_line(lineno)
        definition, returned = self.generator.get_definition(
            primary,
            pyname,
            self.source[start:end_parens],
            scope.get_names(),
            returns=returns,
        )

        end = min(line_end + 1, len(self.source))
        change_collector.add_change(
            line_start, end, sourceutils.fix_indentation(definition, indents)
        )
        if returns:
            name = returned
            if name is None:
                name = "None"
            change_collector.add_change(
                line_end,
                end,
                self.source[line_start:start] + name + self.source[end_parens:end],
            )

    def _find_end_parens(self, source, offset):
        finder = worder.Worder(source)
        return finder.get_word_parens_range(offset)[1]

    @property
    @utils.saveit
    def pymodule(self):
        return self.project.get_pymodule(self.resource)

    @property
    @utils.saveit
    def source(self):
        if self.resource is not None:
            return self.resource.read()
        else:
            return self.pymodule.source_code

    @property
    @utils.saveit
    def lines(self):
        return self.pymodule.lines


def _inline_variable(
    project, pymodule, pyname, name, remove=True, region=None, docs=False
):
    definition = _getvardef(pymodule, pyname)
    start, end = _assigned_lineno(pymodule, pyname)

    occurrence_finder = occurrences.create_finder(project, name, pyname, docs=docs)
    changed_source = rename.rename_in_module(
        occurrence_finder,
        definition,
        pymodule=pymodule,
        replace_primary=True,
        writes=False,
        region=region,
    )
    if changed_source is None:
        changed_source = pymodule.source_code
    if remove:
        lines = codeanalyze.SourceLinesAdapter(changed_source)
        source = (
            changed_source[: lines.get_line_start(start)]
            + changed_source[lines.get_line_end(end) + 1 :]
        )
    else:
        source = changed_source
    return source


def _getvardef(pymodule, pyname):
    assignment = pyname.assignments[0]
    lines = pymodule.lines
    start, end = _assigned_lineno(pymodule, pyname)
    definition_with_assignment = _join_lines(
        [lines.get_line(n) for n in range(start, end + 1)],
    )
    if assignment.levels:
        raise exceptions.RefactoringError("Cannot inline tuple assignments.")
    definition = definition_with_assignment[
        definition_with_assignment.index("=") + 1 :
    ].strip()
    return definition


def _assigned_lineno(pymodule, pyname):
    definition_line = pyname.assignments[0].ast_node.lineno
    return pymodule.logical_lines.logical_line_in(definition_line)


def _add_imports(project, source, resource, imports):
    if not imports:
        return source
    pymodule = libutils.get_string_module(project, source, resource)
    module_import = importutils.get_module_imports(project, pymodule)
    for import_info in imports:
        module_import.add_import(import_info)
    source = module_import.get_changed_source()
    pymodule = libutils.get_string_module(project, source, resource)
    import_tools = importutils.ImportTools(project)
    return import_tools.organize_imports(pymodule, unused=False, sort=False)


def _get_pyname(project, resource, offset):
    pymodule = project.get_pymodule(resource)
    pyname = evaluate.eval_location(pymodule, offset)
    if isinstance(pyname, pynames.ImportedName):
        pyname = pyname._get_imported_pyname()
    return pyname


def _remove_from(project, pyname, source, resource):
    pymodule = libutils.get_string_module(project, source, resource)
    module_import = importutils.get_module_imports(project, pymodule)
    module_import.remove_pyname(pyname)
    return module_import.get_changed_source()
