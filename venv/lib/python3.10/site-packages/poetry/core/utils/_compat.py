from __future__ import annotations

import sys


WINDOWS = sys.platform == "win32"

if sys.version_info < (3, 8):
    # no caching for python 3.7
    cached_property = property
else:
    import functools

    cached_property = functools.cached_property

if sys.version_info < (3, 11):
    # compatibility for python <3.11
    import tomli as tomllib
else:
    import tomllib  # nopycln: import

__all__ = ["tomllib"]
