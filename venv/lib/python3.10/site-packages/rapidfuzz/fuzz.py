# SPDX-License-Identifier: MIT
# Copyright (C) 2021 Max Bachmann

from __future__ import annotations

from typing import Any, Callable

from rapidfuzz._utils import ScorerFlag as _ScorerFlag
from rapidfuzz._utils import fallback_import as _fallback_import


def _get_scorer_flags_fuzz(**_kwargs: Any) -> dict[str, Any]:
    return {
        "optimal_score": 100,
        "worst_score": 0,
        "flags": _ScorerFlag.RESULT_F64 | _ScorerFlag.SYMMETRIC,
    }


_fuzz_attribute: dict[str, Callable[..., dict[str, Any]]] = {
    "get_scorer_flags": _get_scorer_flags_fuzz
}

__all__ = [
    "ratio",
    "partial_ratio",
    "partial_ratio_alignment",
    "token_sort_ratio",
    "token_set_ratio",
    "token_ratio",
    "partial_token_sort_ratio",
    "partial_token_set_ratio",
    "partial_token_ratio",
    "WRatio",
    "QRatio",
]

_mod = "rapidfuzz.fuzz"
ratio = _fallback_import(_mod, "ratio", cached_scorer_call=_fuzz_attribute)
partial_ratio = _fallback_import(
    _mod, "partial_ratio", cached_scorer_call=_fuzz_attribute
)
partial_ratio_alignment = _fallback_import(
    _mod, "partial_ratio_alignment", cached_scorer_call=_fuzz_attribute
)
token_sort_ratio = _fallback_import(
    _mod, "token_sort_ratio", cached_scorer_call=_fuzz_attribute
)
token_set_ratio = _fallback_import(
    _mod, "token_set_ratio", cached_scorer_call=_fuzz_attribute
)
token_ratio = _fallback_import(_mod, "token_ratio", cached_scorer_call=_fuzz_attribute)
partial_token_sort_ratio = _fallback_import(
    _mod, "partial_token_sort_ratio", cached_scorer_call=_fuzz_attribute
)
partial_token_set_ratio = _fallback_import(
    _mod, "partial_token_set_ratio", cached_scorer_call=_fuzz_attribute
)
partial_token_ratio = _fallback_import(
    _mod, "partial_token_ratio", cached_scorer_call=_fuzz_attribute
)
WRatio = _fallback_import(_mod, "WRatio", cached_scorer_call=_fuzz_attribute)
QRatio = _fallback_import(_mod, "QRatio", cached_scorer_call=_fuzz_attribute)
