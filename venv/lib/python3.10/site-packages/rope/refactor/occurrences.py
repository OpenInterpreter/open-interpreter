"""Find occurrences of a name in a project.

This module consists of a `Finder` that finds all occurrences of a name
in a project. The `Finder.find_occurrences()` method is a generator that
yields `Occurrence` instances for each occurrence of the name. To create
a `Finder` object, use the `create_finder()` function:

    finder = occurrences.create_finder(project, 'foo', pyname)
    for occurrence in finder.find_occurrences():
        pass

It's possible to filter the occurrences. They can be specified when
calling the `create_finder()` function.

  * `only_calls`: If True, return only those instances where the name is
    a function that's being called.

  * `imports`: If False, don't return instances that are in import
    statements.

  * `unsure`: If a predicate function, return instances where we don't
    know what the name references. It also filters based on the
    predicate function.

  * `docs`: If True, it will search for occurrences in regions normally
    ignored. E.g., strings and comments.

  * `in_hierarchy`: If True, it will find occurrences if the name is in
    the class's hierarchy.

  * `instance`: Used only when you want implicit interfaces to be
    considered.

  * `keywords`: If False, don't return instances that are the names of keyword
    arguments
"""


import contextlib
import re

from rope.base import (
    ast,
    codeanalyze,
    evaluate,
    exceptions,
    pynames,
    pyobjects,
    utils,
    worder,
)


class Finder:
    """For finding occurrences of a name

    The constructor takes a `filters` argument.  It should be a list
    of functions that take a single argument.  For each possible
    occurrence, these functions are called in order with the an
    instance of `Occurrence`:

      * If it returns `None` other filters are tried.
      * If it returns `True`, the occurrence will be a match.
      * If it returns `False`, the occurrence will be skipped.
      * If all of the filters return `None`, it is skipped also.

    """

    def __init__(self, project, name, filters=None, docs=False):
        if filters is None:
            filters = [lambda o: True]
        self.project = project
        self.name = name
        self.docs = docs
        self.filters = filters
        self._textual_finder = _TextualFinder(name, docs=docs)

    def find_occurrences(self, resource=None, pymodule=None):
        """Generate `Occurrence` instances"""
        tools = _OccurrenceToolsCreator(
            self.project, resource=resource, pymodule=pymodule, docs=self.docs
        )
        for offset in self._textual_finder.find_offsets(tools.source_code):
            occurrence = Occurrence(tools, offset)
            for filter in self.filters:
                result = filter(occurrence)
                if result is None:
                    continue
                if result:
                    yield occurrence
                break


def create_finder(
    project,
    name,
    pyname,
    only_calls=False,
    imports=True,
    unsure=None,
    docs=False,
    instance=None,
    in_hierarchy=False,
    keywords=True,
):
    """A factory for `Finder`

    Based on the arguments it creates a list of filters.  `instance`
    argument is needed only when you want implicit interfaces to be
    considered.

    """
    pynames_ = {pyname}
    filters = []
    if only_calls:
        filters.append(CallsFilter())
    if not imports:
        filters.append(NoImportsFilter())
    if not keywords:
        filters.append(NoKeywordsFilter())
    if isinstance(instance, pynames.ParameterName):
        for pyobject in instance.get_objects():
            try:
                pynames_.add(pyobject[name])
            except exceptions.AttributeNotFoundError:
                pass
    for pyname in pynames_:
        filters.append(PyNameFilter(pyname))
        if in_hierarchy:
            filters.append(InHierarchyFilter(pyname))
    if unsure:
        filters.append(UnsureFilter(unsure))
    return Finder(project, name, filters=filters, docs=docs)


class Occurrence:
    def __init__(self, tools, offset):
        self.tools = tools
        self.offset = offset
        self.resource = tools.resource

    @utils.saveit
    def get_word_range(self):
        return self.tools.word_finder.get_word_range(self.offset)

    @utils.saveit
    def get_primary_range(self):
        return self.tools.word_finder.get_primary_range(self.offset)

    @utils.saveit
    def get_pyname(self):
        with contextlib.suppress(exceptions.BadIdentifierError):
            return self.tools.name_finder.get_pyname_at(self.offset)

    @utils.saveit
    def get_primary_and_pyname(self):
        with contextlib.suppress(exceptions.BadIdentifierError):
            return self.tools.name_finder.get_primary_and_pyname_at(self.offset)

    @utils.saveit
    def is_in_import_statement(self):
        return self.tools.word_finder.is_from_statement(
            self.offset
        ) or self.tools.word_finder.is_import_statement(self.offset)

    def is_called(self):
        return self.tools.word_finder.is_a_function_being_called(self.offset)

    def is_defined(self):
        return self.tools.word_finder.is_a_class_or_function_name_in_header(self.offset)

    def is_a_fixed_primary(self):
        return self.tools.word_finder.is_a_class_or_function_name_in_header(
            self.offset
        ) or self.tools.word_finder.is_a_name_after_from_import(self.offset)

    def is_written(self):
        return self.tools.word_finder.is_assigned_here(self.offset)

    def is_unsure(self):
        return unsure_pyname(self.get_pyname())

    def is_function_keyword_parameter(self):
        return self.tools.word_finder.is_function_keyword_parameter(self.offset)

    @property
    @utils.saveit
    def lineno(self):
        offset = self.get_word_range()[0]
        return self.tools.pymodule.lines.get_line_number(offset)


def same_pyname(expected, pyname):
    """Check whether `expected` and `pyname` are the same"""
    if expected is None or pyname is None:
        return False
    if expected == pyname:
        return True
    if not isinstance(
        expected,
        (pynames.ImportedModule, pynames.ImportedName),
    ) and not isinstance(
        pyname,
        (pynames.ImportedModule, pynames.ImportedName),
    ):
        return False
    return (
        expected.get_definition_location() == pyname.get_definition_location()
        and expected.get_object() == pyname.get_object()
    )


def unsure_pyname(pyname, unbound=True):
    """Return `True` if we don't know what this name references"""
    if pyname is None:
        return True
    if unbound and not isinstance(pyname, pynames.UnboundName):
        return False
    if pyname.get_object() == pyobjects.get_unknown():
        return True


class PyNameFilter:
    """For finding occurrences of a name."""

    def __init__(self, pyname):
        self.pyname = pyname

    def __call__(self, occurrence):
        if same_pyname(self.pyname, occurrence.get_pyname()):
            return True


class InHierarchyFilter:
    """Finds the occurrence if the name is in the class's hierarchy."""

    def __init__(self, pyname, implementations_only=False):
        self.pyname = pyname
        self.impl_only = implementations_only
        self.pyclass = self._get_containing_class(pyname)
        if self.pyclass is not None:
            self.name = pyname.get_object().get_name()
            self.roots = self._get_root_classes(self.pyclass, self.name)
        else:
            self.roots = None

    def __call__(self, occurrence):
        if self.roots is None:
            return
        pyclass = self._get_containing_class(occurrence.get_pyname())
        if pyclass is not None:
            roots = self._get_root_classes(pyclass, self.name)
            if self.roots.intersection(roots):
                return True

    def _get_containing_class(self, pyname):
        if isinstance(pyname, pynames.DefinedName):
            scope = pyname.get_object().get_scope()
            parent = scope.parent
            if parent is not None and parent.get_kind() == "Class":
                return parent.pyobject

    def _get_root_classes(self, pyclass, name):
        if self.impl_only and pyclass == self.pyclass:
            return {pyclass}
        result = set()
        for superclass in pyclass.get_superclasses():
            if name in superclass:
                result.update(self._get_root_classes(superclass, name))
        if not result:
            return {pyclass}
        return result


class UnsureFilter:
    """Occurrences where we don't knoow what the name references."""

    def __init__(self, unsure):
        self.unsure = unsure

    def __call__(self, occurrence):
        if occurrence.is_unsure() and self.unsure(occurrence):
            return True


class NoImportsFilter:
    """Don't include import statements as occurrences."""

    def __call__(self, occurrence):
        if occurrence.is_in_import_statement():
            return False


class CallsFilter:
    """Filter out non-call occurrences."""

    def __call__(self, occurrence):
        if not occurrence.is_called():
            return False


class NoKeywordsFilter:
    """Filter out keyword parameters."""

    def __call__(self, occurrence):
        if occurrence.is_function_keyword_parameter():
            return False


class _TextualFinder:
    def __init__(self, name, docs=False):
        self.name = name
        self.docs = docs
        self.comment_pattern = _TextualFinder.any("comment", [r"#[^\n]*"])
        self.string_pattern = _TextualFinder.any(
            "string", [codeanalyze.get_string_pattern()]
        )
        self.f_string_pattern = _TextualFinder.any(
            "fstring", [codeanalyze.get_formatted_string_pattern()]
        )
        self.pattern = self._get_occurrence_pattern(self.name)

    def find_offsets(self, source):
        if not self._fast_file_query(source):
            return
        if self.docs:
            searcher = self._normal_search
        else:
            searcher = self._re_search
        yield from searcher(source)

    def _re_search(self, source):
        for match in self.pattern.finditer(source):
            if match.groupdict()["occurrence"]:
                yield match.start("occurrence")
            elif match.groupdict()["fstring"]:
                f_string = match.groupdict()["fstring"]
                for occurrence_node in self._search_in_f_string(f_string):
                    yield match.start("fstring") + occurrence_node.col_offset

    def _search_in_f_string(self, f_string):
        tree = ast.parse(f_string)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == self.name:
                yield node

    def _normal_search(self, source):
        current = 0
        while True:
            try:
                found = source.index(self.name, current)
                current = found + len(self.name)
                if (found == 0 or not self._is_id_char(source[found - 1])) and (
                    current == len(source) or not self._is_id_char(source[current])
                ):
                    yield found
            except ValueError:
                break

    def _is_id_char(self, c):
        return c.isalnum() or c == "_"

    def _fast_file_query(self, source):
        return self.name in source

    def _get_source(self, resource, pymodule):
        if resource is not None:
            return resource.read()
        else:
            return pymodule.source_code

    def _get_occurrence_pattern(self, name):
        occurrence_pattern = _TextualFinder.any("occurrence", ["\\b" + name + "\\b"])
        pattern = re.compile(
            occurrence_pattern
            + "|"
            + self.comment_pattern
            + "|"
            + self.string_pattern
            + "|"
            + self.f_string_pattern
        )
        return pattern

    @staticmethod
    def any(name, list_):
        return "(?P<%s>" % name + "|".join(list_) + ")"


class _OccurrenceToolsCreator:
    def __init__(self, project, resource=None, pymodule=None, docs=False):
        self.project = project
        self.__resource = resource
        self.__pymodule = pymodule
        self.docs = docs

    @property
    @utils.saveit
    def name_finder(self):
        return evaluate.ScopeNameFinder(self.pymodule)

    @property
    @utils.saveit
    def source_code(self):
        return self.pymodule.source_code

    @property
    @utils.saveit
    def word_finder(self):
        return worder.Worder(self.source_code, self.docs)

    @property
    @utils.saveit
    def resource(self):
        if self.__resource is not None:
            return self.__resource
        if self.__pymodule is not None:
            return self.__pymodule.resource

    @property
    @utils.saveit
    def pymodule(self):
        if self.__pymodule is not None:
            return self.__pymodule
        return self.project.get_pymodule(self.resource)
