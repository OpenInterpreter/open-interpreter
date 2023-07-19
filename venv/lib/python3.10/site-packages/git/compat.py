# -*- coding: utf-8 -*-
# config.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
"""utilities to help provide compatibility with python 3"""
# flake8: noqa

import locale
import os
import sys

from gitdb.utils.encoding import (
    force_bytes,  # @UnusedImport
    force_text,  # @UnusedImport
)

# typing --------------------------------------------------------------------

from typing import (
    Any,
    AnyStr,
    Dict,
    IO,
    Optional,
    Tuple,
    Type,
    Union,
    overload,
)

# ---------------------------------------------------------------------------


is_win: bool = os.name == "nt"
is_posix = os.name == "posix"
is_darwin = os.name == "darwin"
defenc = sys.getfilesystemencoding()


@overload
def safe_decode(s: None) -> None:
    ...


@overload
def safe_decode(s: AnyStr) -> str:
    ...


def safe_decode(s: Union[AnyStr, None]) -> Optional[str]:
    """Safely decodes a binary string to unicode"""
    if isinstance(s, str):
        return s
    elif isinstance(s, bytes):
        return s.decode(defenc, "surrogateescape")
    elif s is None:
        return None
    else:
        raise TypeError("Expected bytes or text, but got %r" % (s,))


@overload
def safe_encode(s: None) -> None:
    ...


@overload
def safe_encode(s: AnyStr) -> bytes:
    ...


def safe_encode(s: Optional[AnyStr]) -> Optional[bytes]:
    """Safely encodes a binary string to unicode"""
    if isinstance(s, str):
        return s.encode(defenc)
    elif isinstance(s, bytes):
        return s
    elif s is None:
        return None
    else:
        raise TypeError("Expected bytes or text, but got %r" % (s,))


@overload
def win_encode(s: None) -> None:
    ...


@overload
def win_encode(s: AnyStr) -> bytes:
    ...


def win_encode(s: Optional[AnyStr]) -> Optional[bytes]:
    """Encode unicodes for process arguments on Windows."""
    if isinstance(s, str):
        return s.encode(locale.getpreferredencoding(False))
    elif isinstance(s, bytes):
        return s
    elif s is not None:
        raise TypeError("Expected bytes or text, but got %r" % (s,))
    return None
