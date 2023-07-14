# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann
"""
The Levenshtein (edit) distance is a string metric to measure the
difference between two strings/sequences s1 and s2.
It's defined as the minimum number of insertions, deletions or
substitutions required to transform s1 into s2.
"""

from __future__ import annotations

from typing import Any, Callable

from rapidfuzz._utils import ScorerFlag as _ScorerFlag
from rapidfuzz._utils import fallback_import as _fallback_import


def _get_scorer_flags_distance(
    weights: tuple[int, int, int] | None = (1, 1, 1)
) -> dict[str, Any]:
    flags = _ScorerFlag.RESULT_I64
    if weights is None or weights[0] == weights[1]:
        flags |= _ScorerFlag.SYMMETRIC

    return {
        "optimal_score": 0,
        "worst_score": 2**63 - 1,
        "flags": flags,
    }


def _get_scorer_flags_similarity(
    weights: tuple[int, int, int] | None = (1, 1, 1)
) -> dict[str, Any]:
    flags = _ScorerFlag.RESULT_I64
    if weights is None or weights[0] == weights[1]:
        flags |= _ScorerFlag.SYMMETRIC

    return {
        "optimal_score": 2**63 - 1,
        "worst_score": 0,
        "flags": flags,
    }


def _get_scorer_flags_normalized_distance(
    weights: tuple[int, int, int] | None = (1, 1, 1)
) -> dict[str, Any]:
    flags = _ScorerFlag.RESULT_F64
    if weights is None or weights[0] == weights[1]:
        flags |= _ScorerFlag.SYMMETRIC

    return {"optimal_score": 0, "worst_score": 1, "flags": flags}


def _get_scorer_flags_normalized_similarity(
    weights: tuple[int, int, int] | None = (1, 1, 1)
) -> dict[str, Any]:
    flags = _ScorerFlag.RESULT_F64
    if weights is None or weights[0] == weights[1]:
        flags |= _ScorerFlag.SYMMETRIC

    return {"optimal_score": 1, "worst_score": 0, "flags": flags}


_dist_attr: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_distance
}
_sim_attr: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_similarity
}
_norm_dist_attr: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_normalized_distance
}
_norm_sim_attr: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_normalized_similarity
}

_mod = "rapidfuzz.distance.Levenshtein"
distance = _fallback_import(_mod, "distance", cached_scorer_call=_dist_attr)
similarity = _fallback_import(_mod, "similarity", cached_scorer_call=_sim_attr)
normalized_distance = _fallback_import(
    _mod, "normalized_distance", cached_scorer_call=_norm_dist_attr
)
normalized_similarity = _fallback_import(
    _mod, "normalized_similarity", cached_scorer_call=_norm_sim_attr
)
editops = _fallback_import(_mod, "editops")
opcodes = _fallback_import(_mod, "opcodes")
