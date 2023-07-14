"""
The JSON Schema meta-schemas and vocabularies, exposed as a Registry.
"""
from referencing import Registry as _Registry
from referencing.jsonschema import SchemaRegistry as _SchemaRegistry

from jsonschema_specifications._core import _schemas

#: A `referencing.jsonschema.SchemaRegistry` containing all of the official
#: meta-schemas and vocabularies.
REGISTRY: _SchemaRegistry = (_schemas() @ _Registry()).crawl()

__all__ = ["REGISTRY"]
