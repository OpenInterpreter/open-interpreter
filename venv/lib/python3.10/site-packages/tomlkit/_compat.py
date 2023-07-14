from __future__ import annotations

import contextlib
import sys

from typing import Any


PY38 = sys.version_info >= (3, 8)


def decode(string: Any, encodings: list[str] | None = None):
    if not isinstance(string, bytes):
        return string

    encodings = encodings or ["utf-8", "latin1", "ascii"]

    for encoding in encodings:
        with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
            return string.decode(encoding)

    return string.decode(encodings[0], errors="ignore")
