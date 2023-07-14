from __future__ import annotations

from typing import TYPE_CHECKING

from rope.base import (
    change,
    codeanalyze,
    evaluate,
    exceptions,
    libutils,
    pynames,
    pyobjects,
    worder,
)
from rope.refactor import functionutils, importutils, sourceutils, suites

if TYPE_CHECKING:
    from typing import Literal, Optional

    from rope.base.project import Project
    from rope.base.resources import Resource

    GenerateKind = Literal[
        "variable",
        "function",
        "class",
        "module",
        "package",
    ]


def create_generate(
    kind: GenerateKind,
    project: Project,
    resource: Resource,
    offset: int,
    goal_resource: Optional[Resource] = None,
):

    """A factory for creating `Generate` objects

    Used in https://github.com/python-rope/ropemode but not in Rope itself.
    """
    d = {
        "class": GenerateClass,
        "function": GenerateFunction,
        "module": GenerateModule,
        "package": GeneratePackage,
        "variable": GenerateVariable,
    }
    generate = d[kind]
    return generate(project, resource, offset, goal_resource=goal_resource)


def create_module(project, name, sourcefolder=None):
    """Creates a module and returns a `rope.base.resources.File`"""
    if sourcefolder is None:
        sourcefolder = project.root
    packages = name.split(".")
    parent = sourcefolder
    for package in packages[:-1]:
        parent = parent.get_child(package)
    return parent.create_file(packages[-1] + ".py")


def create_package(project, name, sourcefolder=None):
    """Creates a package and returns a `rope.base.resources.Folder`"""
    if sourcefolder is None:
        sourcefolder = project.root
    packages = name.split(".")
    parent = sourcefolder
    for package in packages[:-1]:
        parent = parent.get_child(package)
    made_packages = parent.create_folder(packages[-1])
    made_packages.create_file("__init__.py")
    return made_packages


class _Generate:
    def __init__(self, project, resource, offset, goal_resource=None):
        self.project = project
        self.resource = resource
        self.goal_resource = goal_resource
        self.info = self._generate_info(project, resource, offset)
        self.name = self.info.get_name()
        self._check_exceptional_conditions()

    def _generate_info(self, project, resource, offset):
        return _GenerationInfo(project.pycore, resource, offset, self.goal_resource)

    def _check_exceptional_conditions(self):
        if self.info.element_already_exists():
            raise exceptions.RefactoringError(
                "Element <%s> already exists." % self.name
            )
        if not self.info.primary_is_found():
            raise exceptions.RefactoringError(
                "Cannot determine the scope <%s> should be defined in." % self.name
            )

    def get_changes(self):
        changes = change.ChangeSet(f"Generate {self._get_element_kind()} <{self.name}>")
        indents = self.info.get_scope_indents()
        blanks = self.info.get_blank_lines()
        base_definition = sourceutils.fix_indentation(self._get_element(), indents)
        definition = "\n" * blanks[0] + base_definition + "\n" * blanks[1]

        resource = self.info.get_insertion_resource()
        start, end = self.info.get_insertion_offsets()

        collector = codeanalyze.ChangeCollector(resource.read())
        collector.add_change(start, end, definition)
        changes.add_change(change.ChangeContents(resource, collector.get_changed()))
        if self.goal_resource:
            relative_import = _add_relative_import_to_module(
                self.project, self.resource, self.goal_resource, self.name
            )
            changes.add_change(relative_import)
        return changes

    def get_location(self):
        return (self.info.get_insertion_resource(), self.info.get_insertion_lineno())

    def _get_element_kind(self):
        raise NotImplementedError()

    def _get_element(self):
        raise NotImplementedError()


class GenerateFunction(_Generate):
    def _generate_info(self, project, resource, offset):
        return _FunctionGenerationInfo(project.pycore, resource, offset)

    def _get_element(self):
        decorator = ""
        args = []
        if self.info.is_static_method():
            decorator = "@staticmethod\n"
        if (
            self.info.is_method()
            or self.info.is_constructor()
            or self.info.is_instance()
        ):
            args.append("self")
        args.extend(self.info.get_passed_args())
        definition = "{}def {}({}):\n    pass\n".format(
            decorator,
            self.name,
            ", ".join(args),
        )
        return definition

    def _get_element_kind(self):
        return "Function"


class GenerateVariable(_Generate):
    def _get_element(self):
        return "%s = None\n" % self.name

    def _get_element_kind(self):
        return "Variable"


class GenerateClass(_Generate):
    def _get_element(self):
        return "class %s(object):\n    pass\n" % self.name

    def _get_element_kind(self):
        return "Class"


class GenerateModule(_Generate):
    def get_changes(self):
        package = self.info.get_package()
        changes = change.ChangeSet("Generate Module <%s>" % self.name)
        new_resource = self.project.get_file(f"{package.path}/{self.name}.py")
        if new_resource.exists():
            raise exceptions.RefactoringError(
                "Module <%s> already exists" % new_resource.path
            )
        changes.add_change(change.CreateResource(new_resource))
        changes.add_change(
            _add_import_to_module(self.project, self.resource, new_resource)
        )
        return changes

    def get_location(self):
        package = self.info.get_package()
        return (package.get_child("%s.py" % self.name), 1)


class GeneratePackage(_Generate):
    def get_changes(self):
        package = self.info.get_package()
        changes = change.ChangeSet("Generate Package <%s>" % self.name)
        new_resource = self.project.get_folder(f"{package.path}/{self.name}")
        if new_resource.exists():
            raise exceptions.RefactoringError(
                "Package <%s> already exists" % new_resource.path
            )
        changes.add_change(change.CreateResource(new_resource))
        changes.add_change(
            _add_import_to_module(self.project, self.resource, new_resource)
        )
        child = self.project.get_folder(package.path + "/" + self.name)
        changes.add_change(change.CreateFile(child, "__init__.py"))
        return changes

    def get_location(self):
        package = self.info.get_package()
        child = package.get_child(self.name)
        return (child.get_child("__init__.py"), 1)


def _add_import_to_module(project, resource, imported):
    pymodule = project.get_pymodule(resource)
    import_tools = importutils.ImportTools(project)
    module_imports = import_tools.module_imports(pymodule)
    module_name = libutils.modname(imported)
    new_import = importutils.NormalImport(((module_name, None),))
    module_imports.add_import(new_import)
    return change.ChangeContents(resource, module_imports.get_changed_source())


def _add_relative_import_to_module(project, resource, imported, name):
    pymodule = project.get_pymodule(resource)
    import_tools = importutils.ImportTools(project)
    module_imports = import_tools.module_imports(pymodule)
    new_import = import_tools.get_from_import(imported, name)
    module_imports.add_import(new_import)
    return change.ChangeContents(resource, module_imports.get_changed_source())


class _GenerationInfo:
    def __init__(self, pycore, resource, offset, goal_resource=None):
        self.pycore = pycore
        self.resource = resource
        self.offset = offset
        self.goal_resource = goal_resource
        self.source_pymodule = self.pycore.project.get_pymodule(resource)
        finder = evaluate.ScopeNameFinder(self.source_pymodule)
        self.primary, self.pyname = finder.get_primary_and_pyname_at(offset)
        self._init_fields()

    def _init_fields(self):
        self.source_scope = self._get_source_scope()
        self.goal_scope = self._get_goal_scope()
        self.goal_pymodule = self._get_goal_module(self.goal_scope)

    def _get_goal_scope(self):
        if self.primary is None:
            if self.goal_resource:
                return self.pycore.project.get_pymodule(self.goal_resource).get_scope()
            else:
                return self._get_source_scope()
        pyobject = self.primary.get_object()
        if isinstance(pyobject, pyobjects.PyDefinedObject):
            return pyobject.get_scope()
        elif isinstance(pyobject.get_type(), pyobjects.PyClass):
            return pyobject.get_type().get_scope()

    def _get_goal_module(self, scope):
        if scope is None:
            return
        while scope.parent is not None:
            scope = scope.parent
        return scope.pyobject

    def _get_source_scope(self):
        module_scope = self.source_pymodule.get_scope()
        lineno = self.source_pymodule.lines.get_line_number(self.offset)
        return module_scope.get_inner_scope_for_line(lineno)

    def get_insertion_lineno(self):
        lines = self.goal_pymodule.lines
        if self.goal_scope == self.source_scope:
            line_finder = self.goal_pymodule.logical_lines
            lineno = lines.get_line_number(self.offset)
            lineno = line_finder.logical_line_in(lineno)[0]
            root = suites.ast_suite_tree(self.goal_scope.pyobject.get_ast())
            suite = root.find_suite(lineno)
            indents = sourceutils.get_indents(lines, lineno)
            while self.get_scope_indents() < indents:
                lineno = suite.get_start()
                indents = sourceutils.get_indents(lines, lineno)
                suite = suite.parent
            return lineno
        else:
            return min(self.goal_scope.get_end() + 1, lines.length())

    def get_insertion_resource(self):
        return self.goal_pymodule.get_resource()

    def get_insertion_offsets(self):
        if self.goal_scope.get_kind() == "Class":
            start, end = sourceutils.get_body_region(self.goal_scope.pyobject)
            if self.goal_pymodule.source_code[start:end].strip() == "pass":
                return start, end
        lines = self.goal_pymodule.lines
        start = lines.get_line_start(self.get_insertion_lineno())
        return (start, start)

    def get_scope_indents(self):
        if self.goal_scope.get_kind() == "Module":
            return 0
        return (
            sourceutils.get_indents(
                self.goal_pymodule.lines, self.goal_scope.get_start()
            )
            + 4
        )

    def get_blank_lines(self):
        if self.goal_scope.get_kind() == "Module":
            base_blanks = 2
            if self.goal_pymodule.source_code.strip() == "":
                base_blanks = 0
        if self.goal_scope.get_kind() == "Class":
            base_blanks = 1
        if self.goal_scope.get_kind() == "Function":
            base_blanks = 0
        if self.goal_scope == self.source_scope:
            return (0, base_blanks)
        return (base_blanks, 0)

    def get_package(self):
        primary = self.primary
        if self.primary is None:
            return self.pycore.project.get_source_folders()[0]
        if isinstance(primary.get_object(), pyobjects.PyPackage):
            return primary.get_object().get_resource()
        raise exceptions.RefactoringError(
            "A module/package can be only created in a package."
        )

    def primary_is_found(self):
        return self.goal_scope is not None

    def element_already_exists(self):
        if self.pyname is None or isinstance(self.pyname, pynames.UnboundName):
            return False
        return self.get_name() in self.goal_scope.get_defined_names()

    def get_name(self):
        return worder.get_name_at(self.resource, self.offset)


class _FunctionGenerationInfo(_GenerationInfo):
    def _get_goal_scope(self):
        if self.is_constructor():
            return self.pyname.get_object().get_scope()
        if self.is_instance():
            return self.pyname.get_object().get_type().get_scope()
        if self.primary is None:
            return self._get_source_scope()
        pyobject = self.primary.get_object()
        if isinstance(pyobject, pyobjects.PyDefinedObject):
            return pyobject.get_scope()
        elif isinstance(pyobject.get_type(), pyobjects.PyClass):
            return pyobject.get_type().get_scope()

    def element_already_exists(self):
        if self.pyname is None or isinstance(self.pyname, pynames.UnboundName):
            return False
        return self.get_name() in self.goal_scope.get_defined_names()

    def is_static_method(self):
        return self.primary is not None and isinstance(
            self.primary.get_object(), pyobjects.PyClass
        )

    def is_method(self):
        return self.primary is not None and isinstance(
            self.primary.get_object().get_type(), pyobjects.PyClass
        )

    def is_constructor(self):
        return self.pyname is not None and isinstance(
            self.pyname.get_object(), pyobjects.PyClass
        )

    def is_instance(self):
        if self.pyname is None:
            return False
        pyobject = self.pyname.get_object()
        return isinstance(pyobject.get_type(), pyobjects.PyClass)

    def get_name(self):
        if self.is_constructor():
            return "__init__"
        if self.is_instance():
            return "__call__"
        return worder.get_name_at(self.resource, self.offset)

    def get_passed_args(self):
        result = []
        source = self.source_pymodule.source_code
        finder = worder.Worder(source)
        if finder.is_a_function_being_called(self.offset):
            start, end = finder.get_primary_range(self.offset)
            parens_start, parens_end = finder.get_word_parens_range(end - 1)
            call = source[start:parens_end]
            parser = functionutils._FunctionParser(call, False)
            args, keywords = parser.get_parameters()
            for arg in args:
                if self._is_id(arg):
                    result.append(arg)
                else:
                    result.append("arg%d" % len(result))
            for name, value in keywords:
                result.append(name)
        return result

    def _is_id(self, arg):
        def id_or_underline(c):
            return c.isalpha() or c == "_"

        for c in arg:
            if not id_or_underline(c) and not c.isdigit():
                return False
        return id_or_underline(arg[0])
