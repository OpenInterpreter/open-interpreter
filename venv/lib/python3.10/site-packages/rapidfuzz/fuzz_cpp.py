# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann
from __future__ import annotations

from rapidfuzz._feature_detector import AVX2, supports

__all__ = [
    "QRatio",
    "WRatio",
    "partial_ratio",
    "partial_ratio_alignment",
    "partial_token_ratio",
    "partial_token_set_ratio",
    "partial_token_sort_ratio",
    "ratio",
    "token_ratio",
    "token_set_ratio",
    "token_sort_ratio",
]

if supports(AVX2):
    from rapidfuzz.fuzz_cpp_impl_avx2 import (
        QRatio,
        WRatio,
        partial_ratio,
        partial_ratio_alignment,
        partial_token_ratio,
        partial_token_set_ratio,
        partial_token_sort_ratio,
        ratio,
        token_ratio,
        token_set_ratio,
        token_sort_ratio,
    )
else:
    from rapidfuzz.fuzz_cpp_impl import (
        QRatio,
        WRatio,
        partial_ratio,
        partial_ratio_alignment,
        partial_token_ratio,
        partial_token_set_ratio,
        partial_token_sort_ratio,
        ratio,
        token_ratio,
        token_set_ratio,
        token_sort_ratio,
    )
