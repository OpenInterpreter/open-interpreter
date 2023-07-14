import keyword
import sys
import warnings

from rope.base import (
    builtins,
    evaluate,
    exceptions,
    libutils,
    pynames,
    pynamesdef,
    pyobjects,
    pyobjectsdef,
    pyscopes,
    worder,
)
from rope.contrib import fixsyntax
from rope.refactor import functionutils


def code_assist(
    project,
    source_code,
    offset,
    resource=None,
    templates=None,
    maxfixes=1,
    later_locals=True,
):
    """Return python code completions as a list of `CodeAssistProposal`

    `resource` is a `rope.base.resources.Resource` object.  If
    provided, relative imports are handled.

    `maxfixes` is the maximum number of errors to fix if the code has
    errors in it.

    If `later_locals` is `False` names defined in this scope and after
    this line is ignored.

    """
    if templates is not None:
        warnings.warn(
            "Codeassist no longer supports templates", DeprecationWarning, stacklevel=2
        )
    assist = _PythonCodeAssist(
        project,
        source_code,
        offset,
        resource=resource,
        maxfixes=maxfixes,
        later_locals=later_locals,
    )
    return assist()


def starting_offset(source_code, offset):
    """Return the offset in which the completion should be inserted

    Usually code assist proposals should be inserted like::

        completion = proposal.name
        result = (source_code[:starting_offset] +
                  completion + source_code[offset:])

    Where starting_offset is the offset returned by this function.

    """
    word_finder = worder.Worder(source_code, True)
    expression, starting, starting_offset = word_finder.get_splitted_primary_before(
        offset
    )
    return starting_offset


def get_doc(project, source_code, offset, resource=None, maxfixes=1):
    """Get the pydoc"""
    fixer = fixsyntax.FixSyntax(project, source_code, resource, maxfixes)
    pyname = fixer.pyname_at(offset)
    if pyname is None:
        return None
    pyobject = pyname.get_object()
    return PyDocExtractor().get_doc(pyobject)


def get_calltip(
    project,
    source_code,
    offset,
    resource=None,
    maxfixes=1,
    ignore_unknown=False,
    remove_self=False,
):
    """Get the calltip of a function

    The format of the returned string is
    ``module_name.holding_scope_names.function_name(arguments)``.  For
    classes `__init__()` and for normal objects `__call__()` function
    is used.

    Note that the offset is on the function itself *not* after the its
    open parenthesis.  (Actually it used to be the other way but it
    was easily confused when string literals were involved.  So I
    decided it is better for it not to try to be too clever when it
    cannot be clever enough).  You can use a simple search like::

        offset = source_code.rindex('(', 0, offset) - 1

    to handle simple situations.

    If `ignore_unknown` is `True`, `None` is returned for functions
    without source-code like builtins and extensions.

    If `remove_self` is `True`, the first parameter whose name is self
    will be removed for methods.
    """
    fixer = fixsyntax.FixSyntax(project, source_code, resource, maxfixes)
    pyname = fixer.pyname_at(offset)
    if pyname is None:
        return None
    pyobject = pyname.get_object()
    return PyDocExtractor().get_calltip(pyobject, ignore_unknown, remove_self)


def get_definition_location(project, source_code, offset, resource=None, maxfixes=1):
    """Return the definition location of the python name at `offset`

    Return a (`rope.base.resources.Resource`, lineno) tuple.  If no
    `resource` is given and the definition is inside the same module,
    the first element of the returned tuple would be `None`.  If the
    location cannot be determined ``(None, None)`` is returned.

    """
    fixer = fixsyntax.FixSyntax(project, source_code, resource, maxfixes)
    pyname = fixer.pyname_at(offset)
    if pyname is not None:
        module, lineno = pyname.get_definition_location()
        if module is not None:
            return module.get_module().get_resource(), lineno
    return (None, None)


def find_occurrences(*args, **kwds):
    import rope.contrib.findit

    warnings.warn(
        "Use `rope.contrib.findit.find_occurrences()` instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return rope.contrib.findit.find_occurrences(*args, **kwds)


def get_canonical_path(project, resource, offset):
    """Get the canonical path to an object.

    Given the offset of the object, this returns a list of
    (name, name_type) tuples representing the canonical path to the
    object. For example, the 'x' in the following code:

        class Foo(object):
            def bar(self):
                class Qux(object):
                    def mux(self, x):
                        pass

    we will return:

        [('Foo', 'CLASS'), ('bar', 'FUNCTION'), ('Qux', 'CLASS'),
         ('mux', 'FUNCTION'), ('x', 'PARAMETER')]

    `resource` is a `rope.base.resources.Resource` object.

    `offset` is the offset of the pyname you want the path to.

    """
    # Retrieve the PyName.
    pymod = project.get_pymodule(resource)
    pyname = evaluate.eval_location(pymod, offset)

    # Now get the location of the definition and its containing scope.
    defmod, lineno = pyname.get_definition_location()
    if not defmod:
        return None
    scope = defmod.get_scope().get_inner_scope_for_line(lineno)

    # Start with the name of the object we're interested in.
    names = []
    if isinstance(pyname, pynamesdef.ParameterName):
        names = [(worder.get_name_at(pymod.get_resource(), offset), "PARAMETER")]
    elif isinstance(pyname, pynamesdef.AssignedName):
        names = [(worder.get_name_at(pymod.get_resource(), offset), "VARIABLE")]

    # Collect scope names.
    while scope.parent:
        if isinstance(scope, pyscopes.FunctionScope):
            scope_type = "FUNCTION"
        elif isinstance(scope, pyscopes.ClassScope):
            scope_type = "CLASS"
        else:
            scope_type = None
        names.append((scope.pyobject.get_name(), scope_type))
        scope = scope.parent

    names.append((defmod.get_resource().real_path, "MODULE"))
    names.reverse()
    return names


class CompletionProposal:
    """A completion proposal

    The `scope` instance variable shows where proposed name came from
    and can be 'global', 'local', 'builtin', 'attribute', 'keyword',
    'imported', 'parameter_keyword'.

    The `type` instance variable shows the approximate type of the
    proposed object and can be 'instance', 'class', 'function', 'module',
    and `None`.

    All possible relations between proposal's `scope` and `type` are shown
    in the table below (different scopes in rows and types in columns):

                      | instance | class | function | module | None
                local |    +     |   +   |    +     |   +    |
               global |    +     |   +   |    +     |   +    |
              builtin |    +     |   +   |    +     |        |
            attribute |    +     |   +   |    +     |   +    |
             imported |    +     |   +   |    +     |   +    |
              keyword |          |       |          |        |  +
    parameter_keyword |          |       |          |        |  +

    """

    def __init__(self, name, scope, pyname=None):
        self.name = name
        self.pyname = pyname
        self.scope = self._get_scope(scope)

    def __str__(self):
        return f"{self.name} ({self.scope}, {self.type})"

    def __repr__(self):
        return str(self)

    @property
    def parameters(self):
        """The names of the parameters the function takes.

        Returns None if this completion is not a function.
        """
        pyname = self.pyname
        if isinstance(pyname, pynames.ImportedName):
            pyname = pyname._get_imported_pyname()
        if isinstance(pyname, pynames.DefinedName):
            pyobject = pyname.get_object()
            if isinstance(pyobject, pyobjects.AbstractFunction):
                return pyobject.get_param_names()

    @property
    def type(self):
        pyname = self.pyname
        if isinstance(pyname, builtins.BuiltinName):
            pyobject = pyname.get_object()
            if isinstance(pyobject, builtins.BuiltinFunction):
                return "function"
            elif isinstance(pyobject, builtins.BuiltinClass):
                return "class"
            elif isinstance(pyobject, builtins.BuiltinObject) or isinstance(
                pyobject, builtins.BuiltinName
            ):
                return "instance"
        elif isinstance(pyname, pynames.ImportedModule):
            return "module"
        elif isinstance(pyname, pynames.ImportedName) or isinstance(
            pyname, pynames.DefinedName
        ):
            pyobject = pyname.get_object()
            if isinstance(pyobject, pyobjects.AbstractFunction):
                return "function"
            if isinstance(pyobject, pyobjects.AbstractClass):
                return "class"
        return "instance"

    def _get_scope(self, scope):
        if isinstance(self.pyname, builtins.BuiltinName):
            return "builtin"
        if isinstance(self.pyname, pynames.ImportedModule) or isinstance(
            self.pyname, pynames.ImportedName
        ):
            return "imported"
        return scope

    def get_doc(self):
        """Get the proposed object's docstring.

        Returns None if it can not be get.
        """
        if not self.pyname:
            return None
        pyobject = self.pyname.get_object()
        if not hasattr(pyobject, "get_doc"):
            return None
        return self.pyname.get_object().get_doc()

    @property
    def kind(self):
        warnings.warn(
            "the proposal's `kind` property is deprecated, " "use `scope` instead"
        )
        return self.scope


# leaved for backward compatibility
CodeAssistProposal = CompletionProposal


class NamedParamProposal(CompletionProposal):
    """A parameter keyword completion proposal

    Holds reference to ``_function`` -- the function which
    parameter ``name`` belongs to. This allows to determine
    default value for this parameter.
    """

    def __init__(self, name, function):
        self.argname = name
        name = "%s=" % name
        super().__init__(name, "parameter_keyword")
        self._function = function

    def get_default(self):
        """Get a string representation of a param's default value.

        Returns None if there is no default value for this param.
        """
        definfo = functionutils.DefinitionInfo.read(self._function)
        for arg, default in definfo.args_with_defaults:
            if self.argname == arg:
                return default
        return None


def sorted_proposals(proposals, scopepref=None, typepref=None):
    """Sort a list of proposals

    Return a sorted list of the given `CodeAssistProposal`.

    `scopepref` can be a list of proposal scopes.  Defaults to
    ``['parameter_keyword', 'local', 'global', 'imported',
    'attribute', 'builtin', 'keyword']``.

    `typepref` can be a list of proposal types.  Defaults to
    ``['class', 'function', 'instance', 'module', None]``.
    (`None` stands for completions with no type like keywords.)
    """
    sorter = _ProposalSorter(proposals, scopepref, typepref)
    return sorter.get_sorted_proposal_list()


def starting_expression(source_code, offset):
    """Return the expression to complete"""
    word_finder = worder.Worder(source_code, True)
    expression, starting, starting_offset = word_finder.get_splitted_primary_before(
        offset
    )
    if expression:
        return expression + "." + starting
    return starting


def default_templates():
    warnings.warn(
        "default_templates() is deprecated.", DeprecationWarning, stacklevel=2
    )
    return {}


class _PythonCodeAssist:
    def __init__(
        self, project, source_code, offset, resource=None, maxfixes=1, later_locals=True
    ):
        self.project = project
        self.code = source_code
        self.resource = resource
        self.maxfixes = maxfixes
        self.later_locals = later_locals
        self.word_finder = worder.Worder(source_code, True)
        (
            self.expression,
            self.starting,
            self.offset,
        ) = self.word_finder.get_splitted_primary_before(offset)

    keywords = keyword.kwlist

    def _find_starting_offset(self, source_code, offset):
        current_offset = offset - 1
        while current_offset >= 0 and (
            source_code[current_offset].isalnum() or source_code[current_offset] in "_"
        ):
            current_offset -= 1
        return current_offset + 1

    def _matching_keywords(self, starting):
        return [
            CompletionProposal(kw, "keyword")
            for kw in self.keywords
            if kw.startswith(starting)
        ]

    def __call__(self):
        if self.offset > len(self.code):
            return []
        completions = list(self._code_completions().values())
        if self.expression.strip() == "" and self.starting.strip() != "":
            completions.extend(self._matching_keywords(self.starting))
        return completions

    def _dotted_completions(self, module_scope, holding_scope):
        result = {}
        found_pyname = evaluate.eval_str(holding_scope, self.expression)
        if found_pyname is not None:
            element = found_pyname.get_object()
            compl_scope = "attribute"
            if isinstance(element, (pyobjectsdef.PyModule, pyobjectsdef.PyPackage)):
                compl_scope = "imported"
            for name, pyname in element.get_attributes().items():
                if name.startswith(self.starting):
                    result[name] = CompletionProposal(name, compl_scope, pyname)
        return result

    def _undotted_completions(self, scope, result, lineno=None):
        if scope.parent is not None:
            self._undotted_completions(scope.parent, result)
        if lineno is None:
            names = scope.get_propagated_names()
        else:
            names = scope.get_names()
        for name, pyname in names.items():
            if name.startswith(self.starting):
                compl_scope = "local"
                if scope.get_kind() == "Module":
                    compl_scope = "global"
                if (
                    lineno is None
                    or self.later_locals
                    or not self._is_defined_after(scope, pyname, lineno)
                ):
                    result[name] = CompletionProposal(name, compl_scope, pyname)

    def _from_import_completions(self, pymodule):
        module_name = self.word_finder.get_from_module(self.offset)
        if module_name is None:
            return {}
        pymodule = self._find_module(pymodule, module_name)
        result = {}
        for name in pymodule:
            if name.startswith(self.starting):
                result[name] = CompletionProposal(
                    name, scope="global", pyname=pymodule[name]
                )
        return result

    def _find_module(self, pymodule, module_name):
        dots = 0
        while module_name[dots] == ".":
            dots += 1
        pyname = pynames.ImportedModule(pymodule, module_name[dots:], dots)
        return pyname.get_object()

    def _is_defined_after(self, scope, pyname, lineno):
        location = pyname.get_definition_location()
        if location is not None and location[1] is not None:
            if (
                location[0] == scope.pyobject.get_module()
                and lineno <= location[1] <= scope.get_end()
            ):
                return True

    def _code_completions(self):
        lineno = self.code.count("\n", 0, self.offset) + 1
        fixer = fixsyntax.FixSyntax(
            self.project, self.code, self.resource, self.maxfixes
        )
        pymodule = fixer.get_pymodule()
        module_scope = pymodule.get_scope()
        code = pymodule.source_code
        lines = code.split("\n")
        result = {}
        start = fixsyntax._logical_start(lines, lineno)
        indents = fixsyntax._get_line_indents(lines[start - 1])
        inner_scope = module_scope.get_inner_scope_for_line(start, indents)
        if self.word_finder.is_a_name_after_from_import(self.offset):
            return self._from_import_completions(pymodule)
        if self.expression.strip() != "":
            result.update(self._dotted_completions(module_scope, inner_scope))
        else:
            result.update(self._keyword_parameters(module_scope.pyobject, inner_scope))
            self._undotted_completions(inner_scope, result, lineno=lineno)
        return result

    def _keyword_parameters(self, pymodule, scope):
        offset = self.offset
        if offset == 0:
            return {}
        word_finder = worder.Worder(self.code, True)
        if word_finder.is_on_function_call_keyword(offset - 1):
            function_parens = word_finder.find_parens_start_from_inside(offset - 1)
            primary = word_finder.get_primary_at(function_parens - 1)
            try:
                function_pyname = evaluate.eval_str(scope, primary)
            except exceptions.BadIdentifierError:
                return {}
            if function_pyname is not None:
                pyobject = function_pyname.get_object()
                if isinstance(pyobject, pyobjects.AbstractFunction):
                    pass
                elif (
                    isinstance(pyobject, pyobjects.AbstractClass)
                    and "__init__" in pyobject
                ):
                    pyobject = pyobject["__init__"].get_object()
                elif "__call__" in pyobject:
                    pyobject = pyobject["__call__"].get_object()
                if isinstance(pyobject, pyobjects.AbstractFunction):
                    param_names = []
                    param_names.extend(pyobject.get_param_names(special_args=False))
                    result = {}
                    for name in param_names:
                        if name.startswith(self.starting):
                            result[name + "="] = NamedParamProposal(name, pyobject)
                    return result
        return {}


class _ProposalSorter:
    """Sort a list of code assist proposals"""

    def __init__(self, code_assist_proposals, scopepref=None, typepref=None):
        self.proposals = code_assist_proposals
        if scopepref is None:
            scopepref = [
                "parameter_keyword",
                "local",
                "global",
                "imported",
                "attribute",
                "builtin",
                "keyword",
            ]
        self.scopepref = scopepref
        if typepref is None:
            typepref = ["class", "function", "instance", "module", None]
        self.typerank = {type: index for index, type in enumerate(typepref)}

    def get_sorted_proposal_list(self):
        """Return a list of `CodeAssistProposal`"""
        proposals = {}
        for proposal in self.proposals:
            proposals.setdefault(proposal.scope, []).append(proposal)
        result = []
        for scope in self.scopepref:
            scope_proposals = proposals.get(scope, [])
            scope_proposals = [
                proposal
                for proposal in scope_proposals
                if proposal.type in self.typerank
            ]
            scope_proposals.sort(key=self._proposal_key)
            result.extend(scope_proposals)
        return result

    def _proposal_key(self, proposal1):
        def _underline_count(name):
            return sum(1 for c in name if c == "_")

        return (
            self.typerank.get(proposal1.type, 100),
            _underline_count(proposal1.name),
            proposal1.name,
        )
        # if proposal1.type != proposal2.type:
        #    return cmp(self.typerank.get(proposal1.type, 100),
        #               self.typerank.get(proposal2.type, 100))
        # return self._compare_underlined_names(proposal1.name,
        #                                      proposal2.name)


class PyDocExtractor:
    def get_doc(self, pyobject):
        if isinstance(pyobject, pyobjects.AbstractFunction):
            return self._get_function_docstring(pyobject)
        elif isinstance(pyobject, pyobjects.AbstractClass):
            return self._get_class_docstring(pyobject)
        elif isinstance(pyobject, pyobjects.AbstractModule):
            return self._trim_docstring(pyobject.get_doc())
        return None

    def get_calltip(self, pyobject, ignore_unknown=False, remove_self=False):
        try:
            if isinstance(pyobject, pyobjects.AbstractClass):
                pyobject = pyobject["__init__"].get_object()
            if not isinstance(pyobject, pyobjects.AbstractFunction):
                pyobject = pyobject["__call__"].get_object()
        except exceptions.AttributeNotFoundError:
            return None
        if ignore_unknown and not isinstance(pyobject, pyobjects.PyFunction):
            return
        if isinstance(pyobject, pyobjects.AbstractFunction):
            result = self._get_function_signature(pyobject, add_module=True)
            if remove_self and self._is_method(pyobject):
                return result.replace("(self)", "()").replace("(self, ", "(")
            return result

    def _get_class_docstring(self, pyclass):
        def _get_class_header(pyclass):
            class_name = pyclass.get_name()

            supers = [super.get_name() for super in pyclass.get_superclasses()]
            super_classes = ", ".join(supers)

            return f"class {class_name}({super_classes}):\n\n"

        contents = self._trim_docstring(pyclass.get_doc(), 2)
        doc = _get_class_header(pyclass)
        doc += contents

        if "__init__" in pyclass:
            init = pyclass["__init__"].get_object()
            if isinstance(init, pyobjects.AbstractFunction):
                doc += "\n\n" + self._get_single_function_docstring(init)
        return doc

    def _get_function_docstring(self, pyfunction):
        functions = [pyfunction]
        if self._is_method(pyfunction):
            functions.extend(
                self._get_super_methods(pyfunction.parent, pyfunction.get_name())
            )
        return "\n\n".join(
            [self._get_single_function_docstring(function) for function in functions]
        )

    def _is_method(self, pyfunction):
        return isinstance(pyfunction, pyobjects.PyFunction) and isinstance(
            pyfunction.parent, pyobjects.PyClass
        )

    def _get_single_function_docstring(self, pyfunction):
        signature = self._get_function_signature(pyfunction)
        docs = self._trim_docstring(pyfunction.get_doc(), indents=2)
        return signature + ":\n\n" + docs

    def _get_super_methods(self, pyclass, name):
        result = []
        for super_class in pyclass.get_superclasses():
            if name in super_class:
                function = super_class[name].get_object()
                if isinstance(function, pyobjects.AbstractFunction):
                    result.append(function)
            result.extend(self._get_super_methods(super_class, name))
        return result

    def _get_function_signature(self, pyfunction, add_module=False):
        location = self._location(pyfunction, add_module)
        if isinstance(pyfunction, pyobjects.PyFunction):
            info = functionutils.DefinitionInfo.read(pyfunction)
            return location + info.to_string()
        else:
            return "{}({})".format(
                location + pyfunction.get_name(),
                ", ".join(pyfunction.get_param_names()),
            )

    def _location(self, pyobject, add_module=False):
        location = []
        parent = pyobject.parent
        while parent and not isinstance(parent, pyobjects.AbstractModule):
            location.append(parent.get_name())
            location.append(".")
            parent = parent.parent
        if add_module:
            if isinstance(pyobject, pyobjects.PyFunction):
                location.insert(0, self._get_module(pyobject))
            if isinstance(parent, builtins.BuiltinModule):
                location.insert(0, parent.get_name() + ".")
        return "".join(location)

    def _get_module(self, pyfunction):
        module = pyfunction.get_module()
        if module is not None:
            resource = module.get_resource()
            if resource is not None:
                return libutils.modname(resource) + "."
        return ""

    def _trim_docstring(self, docstring, indents=0):
        """The sample code from :PEP:`257`"""
        if not docstring:
            return ""
        # Convert tabs to spaces (following normal Python rules)
        # and split into a list of lines:
        lines = docstring.expandtabs().splitlines()
        # Determine minimum indentation (first line doesn't count):
        indent = sys.maxsize
        for line in lines[1:]:
            stripped = line.lstrip()
            if stripped:
                indent = min(indent, len(line) - len(stripped))
        # Remove indentation (first line is special):
        trimmed = [lines[0].strip()]
        if indent < sys.maxsize:
            for line in lines[1:]:
                trimmed.append(line[indent:].rstrip())
        # Strip off trailing and leading blank lines:
        while trimmed and not trimmed[-1]:
            trimmed.pop()
        while trimmed and not trimmed[0]:
            trimmed.pop(0)
        # Return a single string:
        return "\n".join(" " * indents + line for line in trimmed)


# Deprecated classes


class TemplateProposal(CodeAssistProposal):
    def __init__(self, name, template):
        warnings.warn(
            "TemplateProposal is deprecated.", DeprecationWarning, stacklevel=2
        )
        super().__init__(name, "template")
        self.template = template


class Template:
    def __init__(self, template):
        self.template = template
        warnings.warn("Template is deprecated.", DeprecationWarning, stacklevel=2)

    def variables(self):
        return []

    def substitute(self, mapping):
        return self.template

    def get_cursor_location(self, mapping):
        return len(self.template)
