# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann

from __future__ import annotations

from typing import Callable, Hashable, Sequence

from rapidfuzz._utils import is_none
from rapidfuzz.distance._initialize import Editop, Editops, Opcodes


def distance(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: int | None = None,
) -> int:
    """
    Calculates the Hamming distance between two strings.
    The hamming distance is defined as the number of positions
    where the two strings differ. It describes the minimum
    amount of substitutions required to transform s1 into s2.

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : int or None, optional
        Maximum distance between s1 and s2, that is
        considered as a result. If the distance is bigger than score_cutoff,
        score_cutoff + 1 is returned instead. Default is None, which deactivates
        this behaviour.

    Returns
    -------
    distance : int
        distance between s1 and s2

    Raises
    ------
    ValueError
        If s1 and s2 have a different length
    """
    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    dist = 0
    if len(s1) != len(s2):
        raise ValueError("Sequences are not the same length.")

    for i in range(len(s1)):
        dist += s1[i] != s2[i]

    return dist if (score_cutoff is None or dist <= score_cutoff) else score_cutoff + 1


def similarity(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: int | None = None,
) -> int:
    """
    Calculates the Hamming similarity between two strings.

    This is calculated as ``len1 - distance``.

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : int, optional
        Maximum distance between s1 and s2, that is
        considered as a result. If the similarity is smaller than score_cutoff,
        0 is returned instead. Default is None, which deactivates
        this behaviour.

    Returns
    -------
    distance : int
        distance between s1 and s2

    Raises
    ------
    ValueError
        If s1 and s2 have a different length
    """
    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    maximum = len(s1)
    dist = distance(s1, s2)
    sim = maximum - dist

    return sim if (score_cutoff is None or sim >= score_cutoff) else 0


def normalized_distance(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: float | None = None,
) -> float:
    """
    Calculates a normalized Hamming similarity in the range [1, 0].

    This is calculated as ``distance / (len1 + len2)``.

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 1.0.
        For norm_dist > score_cutoff 1.0 is returned instead. Default is 1.0,
        which deactivates this behaviour.

    Returns
    -------
    norm_dist : float
        normalized distance between s1 and s2 as a float between 0 and 1.0

    Raises
    ------
    ValueError
        If s1 and s2 have a different length
    """
    if is_none(s1) or is_none(s2):
        return 1.0

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    maximum = len(s1)
    dist = distance(s1, s2)
    norm_dist = dist / maximum if maximum else 0

    return norm_dist if (score_cutoff is None or norm_dist <= score_cutoff) else 1.0


def normalized_similarity(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: float | None = None,
) -> float:
    """
    Calculates a normalized Hamming similarity in the range [0, 1].

    This is calculated as ``1 - normalized_distance``

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 1.0.
        For norm_sim < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    norm_sim : float
        normalized similarity between s1 and s2 as a float between 0 and 1.0

    Raises
    ------
    ValueError
        If s1 and s2 have a different length
    """
    if is_none(s1) or is_none(s2):
        return 0.0

    norm_dist = normalized_distance(s1, s2, processor=processor)
    norm_sim = 1 - norm_dist

    return norm_sim if (score_cutoff is None or norm_sim >= score_cutoff) else 0.0


def editops(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
) -> Editops:
    """
    Return Editops describing how to turn s1 into s2.

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.

    Returns
    -------
    editops : Editops
        edit operations required to turn s1 into s2
    """
    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    if len(s1) != len(s2):
        raise ValueError("Sequences are not the same length.")

    ops_list = []
    for i in range(len(s1)):
        if s1[i] != s2[i]:
            ops_list.append(Editop("replace", i, i))

    # sidestep input validation
    ops = Editops.__new__(Editops)
    ops._src_len = len(s1)
    ops._dest_len = len(s2)
    ops._editops = ops_list
    return ops


def opcodes(
    s1: Sequence[Hashable],
    s2: Sequence[Hashable],
    *,
    processor: Callable[..., Sequence[Hashable]] | None = None,
) -> Opcodes:
    """
    Return Opcodes describing how to turn s1 into s2.

    Parameters
    ----------
    s1 : Sequence[Hashable]
        First string to compare.
    s2 : Sequence[Hashable]
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.

    Returns
    -------
    opcodes : Opcodes
        edit operations required to turn s1 into s2
    """
    return editops(s1, s2, processor=processor).as_opcodes()
