"""The purpose of this module is implement PEP 621 validations that are
difficult to express as a JSON Schema (or that are not supported by the current
JSON Schema library).
"""

from typing import Mapping, TypeVar

from .fastjsonschema_exceptions import JsonSchemaValueException

T = TypeVar("T", bound=Mapping)


class RedefiningStaticFieldAsDynamic(JsonSchemaValueException):
    """According to PEP 621:

    Build back-ends MUST raise an error if the metadata specifies a field
    statically as well as being listed in dynamic.
    """


def validate_project_dynamic(pyproject: T) -> T:
    project_table = pyproject.get("project", {})
    dynamic = project_table.get("dynamic", [])

    for field in dynamic:
        if field in project_table:
            msg = f"You cannot provide a value for `project.{field}` and "
            msg += "list it under `project.dynamic` at the same time"
            name = f"data.project.{field}"
            value = {field: project_table[field], "...": " # ...", "dynamic": dynamic}
            raise RedefiningStaticFieldAsDynamic(msg, value, name, rule="PEP 621")

    return pyproject


EXTRA_VALIDATIONS = (validate_project_dynamic,)
