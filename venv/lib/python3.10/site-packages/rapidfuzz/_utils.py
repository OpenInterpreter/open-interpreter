# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann

from __future__ import annotations

from enum import IntFlag
from math import isnan
from typing import Any, Callable


class ScorerFlag(IntFlag):
    RESULT_F64 = 1 << 5
    RESULT_I64 = 1 << 6
    SYMMETRIC = 1 << 11


def _get_scorer_flags_distance(**_kwargs: Any) -> dict[str, Any]:
    return {
        "optimal_score": 0,
        "worst_score": 2**63 - 1,
        "flags": ScorerFlag.RESULT_I64 | ScorerFlag.SYMMETRIC,
    }


def _get_scorer_flags_similarity(**_kwargs: Any) -> dict[str, Any]:
    return {
        "optimal_score": 2**63 - 1,
        "worst_score": 0,
        "flags": ScorerFlag.RESULT_I64 | ScorerFlag.SYMMETRIC,
    }


def _get_scorer_flags_normalized_distance(**_kwargs: Any) -> dict[str, Any]:
    return {
        "optimal_score": 0,
        "worst_score": 1,
        "flags": ScorerFlag.RESULT_F64 | ScorerFlag.SYMMETRIC,
    }


def _get_scorer_flags_normalized_similarity(**_kwargs: Any) -> dict[str, Any]:
    return {
        "optimal_score": 1,
        "worst_score": 0,
        "flags": ScorerFlag.RESULT_F64 | ScorerFlag.SYMMETRIC,
    }


def is_none(s: Any) -> bool:
    if s is None:
        return True

    if isinstance(s, float) and isnan(s):
        return True

    return False


def _create_scorer(
    func: Any, cached_scorer_call: dict[str, Callable[..., dict[str, Any]]]
):
    func._RF_ScorerPy = cached_scorer_call
    # used to detect the function hasn't been wrapped afterwards
    func._RF_OriginalScorer = func
    return func


def fallback_import(
    module: str,
    name: str,
    cached_scorer_call: dict[str, Callable[..., dict[str, Any]]] | None = None,
    set_attrs: bool = True,
) -> Any:
    """
    import library function and possibly fall back to a pure Python version
    when no C++ implementation is available
    """
    import importlib
    import os

    impl = os.environ.get("RAPIDFUZZ_IMPLEMENTATION")

    py_mod = importlib.import_module(module + "_py")
    py_func = getattr(py_mod, name)
    if not py_func:
        raise ImportError(
            f"cannot import name {name!r} from {py_mod.__name!r} ({py_mod.__file__})"
        )

    if cached_scorer_call:
        py_func = _create_scorer(py_func, cached_scorer_call)

    if impl == "cpp":
        cpp_mod = importlib.import_module(module + "_cpp")
    elif impl == "python":
        return py_func
    else:
        try:
            cpp_mod = importlib.import_module(module + "_cpp")
        except Exception:
            return py_func

    cpp_func = getattr(cpp_mod, name)
    if not cpp_func:
        raise ImportError(
            f"cannot import name {name!r} from {cpp_mod.__name!r} ({cpp_mod.__file__})"
        )

    # patch cpp function so help does not need to be duplicated
    if set_attrs:
        cpp_func.__name__ = py_func.__name__
        cpp_func.__doc__ = py_func.__doc__

    if cached_scorer_call:
        cpp_func = _create_scorer(cpp_func, cached_scorer_call)

    return cpp_func


default_distance_attribute: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_distance
}
default_similarity_attribute: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_similarity
}
default_normalized_distance_attribute: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_normalized_distance
}
default_normalized_similarity_attribute: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_normalized_similarity
}
