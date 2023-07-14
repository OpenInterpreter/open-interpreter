from __future__ import annotations

import json

from pathlib import Path
from typing import Any

import jsonschema

from poetry.core.json import SCHEMA_DIR as CORE_SCHEMA_DIR


SCHEMA_DIR = Path(__file__).parent / "schemas"


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any]) -> list[str]:
    schema_file = Path(SCHEMA_DIR, "poetry.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    validator = jsonschema.Draft7Validator(schema)
    validation_errors = sorted(
        validator.iter_errors(obj),
        key=lambda e: e.path,  # type: ignore[no-any-return]
    )

    errors = []

    for error in validation_errors:
        message = error.message
        if error.path:
            path = ".".join(str(x) for x in error.absolute_path)
            message = f"[{path}] {message}"

        errors.append(message)

    core_schema = json.loads(
        (CORE_SCHEMA_DIR / "poetry-schema.json").read_text(encoding="utf-8")
    )

    properties = {*schema["properties"].keys(), *core_schema["properties"].keys()}
    additional_properties = set(obj.keys()) - properties
    for key in additional_properties:
        errors.append(f"Additional properties are not allowed ('{key}' was unexpected)")

    return errors
