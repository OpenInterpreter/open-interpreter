# SPDX-License-Identifier: MIT
# Copyright (C) 2021 Max Bachmann

from __future__ import annotations

from typing import Callable, Hashable, Sequence

from rapidfuzz.distance import ScoreAlignment
from rapidfuzz.utils import default_process

def ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: float | None = 0,
) -> float: ...
def partial_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: float | None = 0,
) -> float: ...
def partial_ratio_alignment(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: float | None = 0,
) -> ScoreAlignment | None: ...
def token_sort_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def token_set_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def token_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def partial_token_sort_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def partial_token_set_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def partial_token_ratio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def WRatio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
def QRatio(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = default_process,
    score_cutoff: float | None = 0,
) -> float: ...
