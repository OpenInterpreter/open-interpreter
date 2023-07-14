import copy

import rope.base.exceptions
from rope.base import codeanalyze, evaluate, pyobjects, taskhandle, utils, worder
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import functionutils, occurrences


class ChangeSignature:
    def __init__(self, project, resource, offset):
        self.project = project
        self.resource = resource
        self.offset = offset
        self._set_name_and_pyname()
        if (
            self.pyname is None
            or self.pyname.get_object() is None
            or not isinstance(self.pyname.get_object(), pyobjects.PyFunction)
        ):
            raise rope.base.exceptions.RefactoringError(
                "Change method signature should be performed on functions"
            )

    def _set_name_and_pyname(self):
        self.name = worder.get_name_at(self.resource, self.offset)
        this_pymodule = self.project.get_pymodule(self.resource)
        self.primary, self.pyname = evaluate.eval_location2(this_pymodule, self.offset)
        if self.pyname is None:
            return
        pyobject = self.pyname.get_object()
        if isinstance(pyobject, pyobjects.PyClass) and "__init__" in pyobject:
            self.pyname = pyobject["__init__"]
            self.name = "__init__"
        pyobject = self.pyname.get_object()
        self.others = None
        if (
            self.name == "__init__"
            and isinstance(pyobject, pyobjects.PyFunction)
            and isinstance(pyobject.parent, pyobjects.PyClass)
        ):
            pyclass = pyobject.parent
            self.others = (pyclass.get_name(), pyclass.parent[pyclass.get_name()])

    def _change_calls(
        self,
        call_changer,
        in_hierarchy=None,
        resources=None,
        handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        if resources is None:
            resources = self.project.get_python_files()
        changes = ChangeSet("Changing signature of <%s>" % self.name)
        job_set = handle.create_jobset("Collecting Changes", len(resources))
        finder = occurrences.create_finder(
            self.project,
            self.name,
            self.pyname,
            instance=self.primary,
            in_hierarchy=in_hierarchy and self.is_method(),
        )
        if self.others:
            name, pyname = self.others
            constructor_finder = occurrences.create_finder(
                self.project, name, pyname, only_calls=True
            )
            finder = _MultipleFinders([finder, constructor_finder])
        for file in resources:
            job_set.started_job(file.path)
            change_calls = _ChangeCallsInModule(
                self.project, finder, file, call_changer
            )
            changed_file = change_calls.get_changed_module()
            if changed_file is not None:
                changes.add_change(ChangeContents(file, changed_file))
            job_set.finished_job()
        return changes

    def get_args(self):
        """Get function arguments.

        Return a list of ``(name, default)`` tuples for all but star
        and double star arguments.  For arguments that don't have a
        default, `None` will be used.
        """
        return self._definfo().args_with_defaults

    def is_method(self):
        pyfunction = self.pyname.get_object()
        return isinstance(pyfunction.parent, pyobjects.PyClass)

    @utils.deprecated("Use `ChangeSignature.get_args()` instead")
    def get_definition_info(self):
        return self._definfo()

    def _definfo(self):
        return functionutils.DefinitionInfo.read(self.pyname.get_object())

    @utils.deprecated()
    def normalize(self):
        changer = _FunctionChangers(
            self.pyname.get_object(), self.get_definition_info(), [ArgumentNormalizer()]
        )
        return self._change_calls(changer)

    @utils.deprecated()
    def remove(self, index):
        changer = _FunctionChangers(
            self.pyname.get_object(),
            self.get_definition_info(),
            [ArgumentRemover(index)],
        )
        return self._change_calls(changer)

    @utils.deprecated()
    def add(self, index, name, default=None, value=None):
        changer = _FunctionChangers(
            self.pyname.get_object(),
            self.get_definition_info(),
            [ArgumentAdder(index, name, default, value)],
        )
        return self._change_calls(changer)

    @utils.deprecated()
    def inline_default(self, index):
        changer = _FunctionChangers(
            self.pyname.get_object(),
            self.get_definition_info(),
            [ArgumentDefaultInliner(index)],
        )
        return self._change_calls(changer)

    @utils.deprecated()
    def reorder(self, new_ordering):
        changer = _FunctionChangers(
            self.pyname.get_object(),
            self.get_definition_info(),
            [ArgumentReorderer(new_ordering)],
        )
        return self._change_calls(changer)

    def get_changes(
        self,
        changers,
        in_hierarchy=False,
        resources=None,
        task_handle=taskhandle.DEFAULT_TASK_HANDLE,
    ):
        """Get changes caused by this refactoring

        `changers` is a list of `_ArgumentChanger`.  If `in_hierarchy`
        is `True` the changers are applied to all matching methods in
        the class hierarchy.
        `resources` can be a list of `rope.base.resource.File` that
        should be searched for occurrences; if `None` all python files
        in the project are searched.

        """
        function_changer = _FunctionChangers(
            self.pyname.get_object(), self._definfo(), changers
        )
        return self._change_calls(
            function_changer, in_hierarchy, resources, task_handle
        )


class _FunctionChangers:
    def __init__(self, pyfunction, definition_info, changers=None):
        self.pyfunction = pyfunction
        self.definition_info = definition_info
        self.changers = changers
        self.changed_definition_infos = self._get_changed_definition_infos()

    def _get_changed_definition_infos(self):
        definition_info = self.definition_info
        result = [definition_info]
        for changer in self.changers:
            definition_info = copy.deepcopy(definition_info)
            changer.change_definition_info(definition_info)
            result.append(definition_info)
        return result

    def change_definition(self, call):
        return self.changed_definition_infos[-1].to_string()

    def change_call(self, primary, pyname, call):
        call_info = functionutils.CallInfo.read(
            primary, pyname, self.definition_info, call
        )
        mapping = functionutils.ArgumentMapping(self.definition_info, call_info)

        for definition_info, changer in zip(
            self.changed_definition_infos, self.changers
        ):
            changer.change_argument_mapping(definition_info, mapping)

        return mapping.to_call_info(self.changed_definition_infos[-1]).to_string()


class _ArgumentChanger:
    def change_definition_info(self, definition_info):
        pass

    def change_argument_mapping(self, definition_info, argument_mapping):
        pass


class ArgumentNormalizer(_ArgumentChanger):
    pass


class ArgumentRemover(_ArgumentChanger):
    def __init__(self, index):
        self.index = index

    def change_definition_info(self, call_info):
        if self.index < len(call_info.args_with_defaults):
            del call_info.args_with_defaults[self.index]
        elif (
            self.index == len(call_info.args_with_defaults)
            and call_info.args_arg is not None
        ):
            call_info.args_arg = None
        elif (
            self.index == len(call_info.args_with_defaults)
            and call_info.args_arg is None
            and call_info.keywords_arg is not None
        ) or (
            self.index == len(call_info.args_with_defaults) + 1
            and call_info.args_arg is not None
            and call_info.keywords_arg is not None
        ):
            call_info.keywords_arg = None

    def change_argument_mapping(self, definition_info, mapping):
        if self.index < len(definition_info.args_with_defaults):
            name = definition_info.args_with_defaults[0]
            if name in mapping.param_dict:
                del mapping.param_dict[name]


class ArgumentAdder(_ArgumentChanger):
    def __init__(self, index, name, default=None, value=None):
        self.index = index
        self.name = name
        self.default = default
        self.value = value

    def change_definition_info(self, definition_info):
        for pair in definition_info.args_with_defaults:
            if pair[0] == self.name:
                raise rope.base.exceptions.RefactoringError(
                    "Adding duplicate parameter: <%s>." % self.name
                )
        definition_info.args_with_defaults.insert(self.index, (self.name, self.default))

    def change_argument_mapping(self, definition_info, mapping):
        if self.value is not None:
            mapping.param_dict[self.name] = self.value


class ArgumentDefaultInliner(_ArgumentChanger):
    def __init__(self, index):
        self.index = index
        self.remove = False

    def change_definition_info(self, definition_info):
        if self.remove:
            definition_info.args_with_defaults[self.index] = (
                definition_info.args_with_defaults[self.index][0],
                None,
            )

    def change_argument_mapping(self, definition_info, mapping):
        default = definition_info.args_with_defaults[self.index][1]
        name = definition_info.args_with_defaults[self.index][0]
        if default is not None and name not in mapping.param_dict:
            mapping.param_dict[name] = default


class ArgumentReorderer(_ArgumentChanger):
    def __init__(self, new_order, autodef=None):
        """Construct an `ArgumentReorderer`

        Note that the `new_order` is a list containing the new
        position of parameters; not the position each parameter
        is going to be moved to. (changed in ``0.5m4``)

        For example changing ``f(a, b, c)`` to ``f(c, a, b)``
        requires passing ``[2, 0, 1]`` and *not* ``[1, 2, 0]``.

        The `autodef` (automatic default) argument, forces rope to use
        it as a default if a default is needed after the change.  That
        happens when an argument without default is moved after
        another that has a default value.  Note that `autodef` should
        be a string or `None`; the latter disables adding automatic
        default.

        """
        self.new_order = new_order
        self.autodef = autodef

    def change_definition_info(self, definition_info):
        new_args = list(definition_info.args_with_defaults)
        for new_index, index in enumerate(self.new_order):
            new_args[new_index] = definition_info.args_with_defaults[index]
        seen_default = False
        for index, (arg, default) in enumerate(list(new_args)):
            if default is not None:
                seen_default = True
            if seen_default and default is None and self.autodef is not None:
                new_args[index] = (arg, self.autodef)
        definition_info.args_with_defaults = new_args


class _ChangeCallsInModule:
    def __init__(self, project, occurrence_finder, resource, call_changer):
        self.project = project
        self.occurrence_finder = occurrence_finder
        self.resource = resource
        self.call_changer = call_changer

    def get_changed_module(self):
        word_finder = worder.Worder(self.source)
        change_collector = codeanalyze.ChangeCollector(self.source)
        for occurrence in self.occurrence_finder.find_occurrences(self.resource):
            if not occurrence.is_called() and not occurrence.is_defined():
                continue
            start, end = occurrence.get_primary_range()
            begin_parens, end_parens = word_finder.get_word_parens_range(end - 1)
            if occurrence.is_called():
                primary, pyname = occurrence.get_primary_and_pyname()
                changed_call = self.call_changer.change_call(
                    primary, pyname, self.source[start:end_parens]
                )
            else:
                changed_call = self.call_changer.change_definition(
                    self.source[start:end_parens]
                )
            if changed_call is not None:
                change_collector.add_change(start, end_parens, changed_call)
        return change_collector.get_changed()

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


class _MultipleFinders:
    def __init__(self, finders):
        self.finders = finders

    def find_occurrences(self, resource=None, pymodule=None):
        all_occurrences = []
        for finder in self.finders:
            all_occurrences.extend(finder.find_occurrences(resource, pymodule))
        all_occurrences.sort(key=lambda x: x.get_primary_range())
        return all_occurrences
