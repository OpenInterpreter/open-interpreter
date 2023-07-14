from __future__ import annotations

import json

from pathlib import Path
from typing import Any


SCHEMA_DIR = Path(__file__).parent / "schemas"


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any], schema_name: str) -> list[str]:
    schema_file = SCHEMA_DIR / f"{schema_name}.json"

    if not schema_file.exists():
        raise ValueError(f"Schema {schema_name} does not exist.")

    with schema_file.open(encoding="utf-8") as f:
        schema = json.load(f)

    from jsonschema import Draft7Validator

    validator = Draft7Validator(schema)
    validation_errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)  # type: ignore[no-any-return] # noqa: E501

    errors = []

    for error in validation_errors:
        message = error.message
        if error.path:
            path = ".".join(map(str, error.absolute_path))
            message = f"[{path}] {message}"

        errors.append(message)

    return errors
