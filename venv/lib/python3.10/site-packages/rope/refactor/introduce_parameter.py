import rope.base.change  # Use fully qualified names for clarity.
from rope.base import codeanalyze, evaluate, exceptions, worder
from rope.refactor import functionutils, occurrences, sourceutils


class IntroduceParameter:
    """Introduce parameter refactoring

    This refactoring adds a new parameter to a function and replaces
    references to an expression in it with the new parameter.

    The parameter finding part is different from finding similar
    pieces in extract refactorings.  In this refactoring parameters
    are found based on the object they reference to.  For instance
    in::

      class A(object):
          var = None

      class B(object):
          a = A()

      b = B()
      a = b.a

      def f(a):
          x = b.a.var + a.var

    using this refactoring on ``a.var`` with ``p`` as the new
    parameter name, will result in::

      def f(p=a.var):
          x = p + p

    """

    def __init__(self, project, resource, offset):
        self.project = project
        self.resource = resource
        self.offset = offset
        self.pymodule = self.project.get_pymodule(self.resource)
        scope = self.pymodule.get_scope().get_inner_scope_for_offset(offset)
        if scope.get_kind() != "Function":
            raise exceptions.RefactoringError(
                "Introduce parameter should be performed inside functions"
            )
        self.pyfunction = scope.pyobject
        self.name, self.pyname = self._get_name_and_pyname()
        if self.pyname is None:
            raise exceptions.RefactoringError(
                "Cannot find the definition of <%s>" % self.name
            )

    def _get_primary(self):
        word_finder = worder.Worder(self.resource.read())
        return word_finder.get_primary_at(self.offset)

    def _get_name_and_pyname(self):
        return (
            worder.get_name_at(self.resource, self.offset),
            evaluate.eval_location(self.pymodule, self.offset),
        )

    def get_changes(self, new_parameter):
        definition_info = functionutils.DefinitionInfo.read(self.pyfunction)
        definition_info.args_with_defaults.append((new_parameter, self._get_primary()))
        collector = codeanalyze.ChangeCollector(self.resource.read())
        header_start, header_end = self._get_header_offsets()
        body_start, body_end = sourceutils.get_body_region(self.pyfunction)
        collector.add_change(header_start, header_end, definition_info.to_string())
        self._change_function_occurrences(
            collector, body_start, body_end, new_parameter
        )
        changes = rope.base.change.ChangeSet("Introduce parameter <%s>" % new_parameter)
        change = rope.base.change.ChangeContents(self.resource, collector.get_changed())
        changes.add_change(change)
        return changes

    def _get_header_offsets(self):
        lines = self.pymodule.lines
        start_line = self.pyfunction.get_scope().get_start()
        end_line = self.pymodule.logical_lines.logical_line_in(start_line)[1]
        start = lines.get_line_start(start_line)
        end = lines.get_line_end(end_line)
        start = self.pymodule.source_code.find("def", start) + 4
        end = self.pymodule.source_code.rfind(":", start, end)
        return start, end

    def _change_function_occurrences(
        self, collector, function_start, function_end, new_name
    ):
        finder = occurrences.create_finder(self.project, self.name, self.pyname)
        for occurrence in finder.find_occurrences(resource=self.resource):
            start, end = occurrence.get_primary_range()
            if function_start <= start < function_end:
                collector.add_change(start, end, new_name)
