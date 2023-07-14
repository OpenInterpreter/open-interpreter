from __future__ import annotations

import sys

from contextlib import suppress


# TODO: use try/except ImportError when
# https://github.com/python/mypy/issues/1393 is fixed

if sys.version_info < (3, 11):
    # compatibility for python <3.11
    import tomli as tomllib
else:
    import tomllib  # nopycln: import


if sys.version_info < (3, 10):
    # compatibility for python <3.10
    import importlib_metadata as metadata
else:
    from importlib import metadata

if sys.version_info < (3, 8):
    # compatibility for python <3.8
    from backports.cached_property import cached_property
else:
    from functools import cached_property

WINDOWS = sys.platform == "win32"


def decode(string: bytes | str, encodings: list[str] | None = None) -> str:
    if not isinstance(string, bytes):
        return string

    encodings = encodings or ["utf-8", "latin1", "ascii"]

    for encoding in encodings:
        with suppress(UnicodeEncodeError, UnicodeDecodeError):
            return string.decode(encoding)

    return string.decode(encodings[0], errors="ignore")


def encode(string: str, encodings: list[str] | None = None) -> bytes:
    if isinstance(string, bytes):
        return string

    encodings = encodings or ["utf-8", "latin1", "ascii"]

    for encoding in encodings:
        with suppress(UnicodeEncodeError, UnicodeDecodeError):
            return string.encode(encoding)

    return string.encode(encodings[0], errors="ignore")


__all__ = [
    "WINDOWS",
    "cached_property",
    "decode",
    "encode",
    "metadata",
    "tomllib",
]
