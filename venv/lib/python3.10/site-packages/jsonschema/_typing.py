"""
Some (initially private) typing helpers for jsonschema's types.
"""
from typing import Any, Callable, Iterable, Protocol, Tuple, Union

import referencing.jsonschema

from jsonschema.protocols import Validator


class SchemaKeywordValidator(Protocol):
    def __call__(
        self,
        validator: Validator,
        value: Any,
        instance: Any,
        schema: referencing.jsonschema.Schema,
    ) -> None:
        ...


id_of = Callable[[referencing.jsonschema.Schema], Union[str, None]]


ApplicableValidators = Callable[
    [referencing.jsonschema.Schema],
    Iterable[Tuple[str, Any]],
]
