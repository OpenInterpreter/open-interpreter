"""
This module serves to convert a data structure composed of Python primitives
(dict, list, tuple, int, str, None) to JSON-serializable primitives (object,
array, number, str, null).

A core feature of this serializer is that the produced will round-trip to
identical objects when deserialized by the standard library json module.
In other words, this property always holds:

    >>> original_data = ... any JSON ...
    >>> encoded = python_to_json(original_data)
    >>> serialized = json.dumps(encoded)
    >>> decoded = json.loads(serialized)
    >>> rehydrated_data = json_to_python(decoded)

    >>> assert rehydrated_data == original_data
    >>> assert encoded == decoded

Couple challenges in straight serialization that this module helps resolve:

- json.dumps() maps both Python list and tuple to JSON array. This module
  provides two variants:

  - In version=1, this module converts Python list `[1, 2, 3]` as-is and
    converts Python tuple `(1, 2, 3)` to special object construct
    `{"$": "t", "items": [1, 2, 3]}`

  - In version=2, it is the other way around, this module converts Python tuple
    `(1, 2, 3)` as-is and converts Python list `[1, 2, 3]` to special object
    construct `{"$": "l", "items": [1, 2, 3]}`

- Python dict keys can be a tuple/dict, but JSON Object keys must be strings
  This module replaces all `dict` keys with `refid` which can be resolved using
  the `encoded["references"][refid]` lookup table. Except there's a small
  optimisation, if the dict key is a string that isn't only numeric, which is
  encoded directly into the object.

- Python dict keys cannot be another dict because it is unhashable, therefore
  there's no encoding for having objects as keys either.

- There is currently no support for floating point numbers.

Note that `json_to_python` only accepts Python objects that can be the output
of `python_to_json`, there is NO guarantee for going the other way around. This
may or may not work:

    >>> python_to_json(json_to_python(original_data)) == original_data

"""


def python_to_json(o, version=1):
    if version not in (1, 2):
        raise ValueError(f"Unexpected version {version}")
    references = []
    result = {
        "v": version,
        "data": _py2js(o, references, version=version),
        "references": references,
    }
    if not result["references"]:
        del result["references"]
    return result


def json_to_python(o):
    version = o["v"]
    if version not in (1, 2):
        raise ValueError(f"Unexpected version {version}")
    references = o.get("references", {})
    data = _js2py(o["data"], references, version)
    return data


def _py2js(o, references, version):
    if isinstance(o, (str, int)) or o is None:
        return o
    elif isinstance(o, tuple):
        if version == 1:
            return {
                "$": "t",
                "items": [_py2js(item, references, version) for item in o],
            }
        else:
            return [_py2js(item, references, version) for item in o]
    elif isinstance(o, list):
        if version == 2:
            return {
                "$": "l",
                "items": [_py2js(item, references, version) for item in o],
            }
        else:
            return [_py2js(item, references, version) for item in o]
    elif isinstance(o, dict):
        result = {}
        for pykey, pyvalue in o.items():
            if pykey == "$":
                raise ValueError('dict cannot contain reserved key "$"')
            if isinstance(pykey, str) and not pykey.isdigit():
                result[pykey] = _py2js(pyvalue, references, version)
            else:
                assert isinstance(pykey, (str, int, tuple)) or pykey is None
                assert not isinstance(pykey, list)
                refid = len(references)
                references.append(_py2js(pykey, references, version))
                result[str(refid)] = _py2js(pyvalue, references, version)
        return result
    raise TypeError(f"Object of type {type(o)} is not allowed {o}")


def _js2py(o, references, version):
    if isinstance(o, (str, int)) or o is None:
        return o
    elif isinstance(o, list):
        if version == 1:
            return list(_js2py(item, references, version) for item in o)
        elif version == 2:
            return tuple(_js2py(item, references, version) for item in o)
        raise ValueError(f"Unexpected version {version}")
    elif isinstance(o, dict):
        result = {}
        if "$" in o:
            if o["$"] == "t":
                assert version == 1
                data = o["items"]
                return tuple(_js2py(item, references, version) for item in data)
            elif o["$"] == "l":
                assert version == 2
                data = o["items"]
                return list(_js2py(item, references, version) for item in data)
            raise TypeError(f'Unrecognized object of type: {o["$"]} {o}')
        else:
            for refid, jsvalue in o.items():
                assert isinstance(refid, str)
                if refid.isdigit():
                    refid = int(refid)
                    assert 0 <= refid < len(references)
                    jskey = references[refid]
                    pyvalue = _js2py(jsvalue, references, version)
                    pykey = _js2py(jskey, references, version)
                    result[pykey] = pyvalue
                else:
                    result[refid] = _js2py(jsvalue, references, version)
        return result
    raise TypeError(f'Object of type "{type(o).__name__}" is not allowed {o}')
