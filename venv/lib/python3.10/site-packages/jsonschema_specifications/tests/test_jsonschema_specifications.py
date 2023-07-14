from collections.abc import Mapping

from jsonschema_specifications import REGISTRY


def test_it_contains_metaschemas():
    schema = REGISTRY.contents("http://json-schema.org/draft-07/schema#")
    assert isinstance(schema, Mapping)
    assert schema["$id"] == "http://json-schema.org/draft-07/schema#"
    assert schema["title"] == "Core schema meta-schema"
