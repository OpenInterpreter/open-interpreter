# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann
from __future__ import annotations

from math import ceil
from typing import Callable, Hashable

from rapidfuzz._utils import is_none
from rapidfuzz.distance import ScoreAlignment
from rapidfuzz.distance.Indel_py import (
    _block_normalized_similarity as indel_block_normalized_similarity,
)
from rapidfuzz.distance.Indel_py import distance as indel_distance
from rapidfuzz.distance.Indel_py import (
    normalized_similarity as indel_normalized_similarity,
)
from rapidfuzz.utils_py import default_process


def _norm_distance(dist: int, lensum: int, score_cutoff: float) -> float:
    score = (100 - 100 * dist / lensum) if lensum else 100
    return score if score >= score_cutoff else 0


def ratio(
    s1: str | bytes | None,
    s2: str | bytes | None,
    *,
    processor: Callable[..., str | bytes] | None | bool = None,
    score_cutoff: float | None = None,
) -> float:
    """
    Calculates the normalized Indel distance.

    Parameters
    ----------
    s1 : str | bytes
        First string to compare.
    s2 : str | bytes
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    See Also
    --------
    rapidfuzz.string_metric.normalized_levenshtein : Normalized levenshtein distance

    Notes
    -----
    .. image:: img/ratio.svg

    Examples
    --------
    >>> fuzz.ratio("this is a test", "this is a test!")
    96.55171966552734
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if score_cutoff is not None:
        score_cutoff /= 100

    score = indel_normalized_similarity(
        s1, s2, processor=processor, score_cutoff=score_cutoff
    )
    return score * 100


def _partial_ratio_short_needle(
    s1: str | bytes, s2: str | bytes, score_cutoff: float
) -> ScoreAlignment:
    """
    implementation of partial_ratio for needles <= 64. assumes s1 is already the
    shorter string
    """
    s1_char_set = set(s1)
    len1 = len(s1)
    len2 = len(s2)

    res = ScoreAlignment(0, 0, len1, 0, len1)

    block: dict[Hashable, int] = {}
    block_get = block.get
    x = 1
    for ch1 in s1:
        block[ch1] = block_get(ch1, 0) | x
        x <<= 1

    for i in range(1, len1):
        substr_last = s2[i - 1]
        if substr_last not in s1_char_set:
            continue

        # todo cache map
        ls_ratio = indel_block_normalized_similarity(
            block, s1, s2[:i], score_cutoff=score_cutoff
        )
        if ls_ratio > res.score:
            res.score = score_cutoff = ls_ratio
            res.dest_start = 0
            res.dest_end = i
            if res.score == 1:
                res.score = 100
                return res

    for i in range(len2 - len1):
        substr_last = s2[i + len1 - 1]
        if substr_last not in s1_char_set:
            continue

        # todo cache map
        ls_ratio = indel_block_normalized_similarity(
            block, s1, s2[i : i + len1], score_cutoff=score_cutoff
        )
        if ls_ratio > res.score:
            res.score = score_cutoff = ls_ratio
            res.dest_start = i
            res.dest_end = i + len1
            if res.score == 1:
                res.score = 100
                return res

    for i in range(len2 - len1, len2):
        substr_first = s2[i]
        if substr_first not in s1_char_set:
            continue

        # todo cache map
        ls_ratio = indel_block_normalized_similarity(
            block, s1, s2[i:], score_cutoff=score_cutoff
        )
        if ls_ratio > res.score:
            res.score = score_cutoff = ls_ratio
            res.dest_start = i
            res.dest_end = len2
            if res.score == 1:
                res.score = 100
                return res

    res.score *= 100
    return res


def partial_ratio(
    s1: str | bytes | None,
    s2: str | bytes | None,
    *,
    processor: Callable[..., str | bytes] | None | bool = None,
    score_cutoff: float | None = None,
) -> float:
    """
    Searches for the optimal alignment of the shorter string in the
    longer string and returns the fuzz.ratio for this alignment.

    Parameters
    ----------
    s1 : str | bytes
        First string to compare.
    s2 : str | bytes
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    Depending on the length of the needle (shorter string) different
    implementations are used to improve the performance.

    short needle (length ≤ 64):
        When using a short needle length the fuzz.ratio is calculated for all
        alignments that could result in an optimal alignment. It is
        guaranteed to find the optimal alignment. For short needles this is very
        fast, since for them fuzz.ratio runs in ``O(N)`` time. This results in a worst
        case performance of ``O(NM)``.

    .. image:: img/partial_ratio_short_needle.svg

    long needle (length > 64):
        For long needles a similar implementation to FuzzyWuzzy is used.
        This implementation only considers alignments which start at one
        of the longest common substrings. This results in a worst case performance
        of ``O(N[N/64]M)``. However usually most of the alignments can be skipped.
        The following Python code shows the concept:

        .. code-block:: python

            blocks = SequenceMatcher(None, needle, longer, False).get_matching_blocks()
            score = 0
            for block in blocks:
                long_start = block[1] - block[0] if (block[1] - block[0]) > 0 else 0
                long_end = long_start + len(shorter)
                long_substr = longer[long_start:long_end]
                score = max(score, fuzz.ratio(needle, long_substr))

        This is a lot faster than checking all possible alignments. However it
        only finds one of the best alignments and not necessarily the optimal one.

    .. image:: img/partial_ratio_long_needle.svg

    Examples
    --------
    >>> fuzz.partial_ratio("this is a test", "this is a test!")
    100.0
    """
    alignment = partial_ratio_alignment(
        s1, s2, processor=processor, score_cutoff=score_cutoff
    )
    if alignment is None:
        return 0

    return alignment.score


def partial_ratio_alignment(
    s1: str | bytes | None,
    s2: str | bytes | None,
    *,
    processor: Callable[..., str | bytes] | None | bool = None,
    score_cutoff: float | None = None,
) -> ScoreAlignment | None:
    """
    Searches for the optimal alignment of the shorter string in the
    longer string and returns the fuzz.ratio and the corresponding
    alignment.

    Parameters
    ----------
    s1 : str | bytes
        First string to compare.
    s2 : str | bytes
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff None is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    alignment : ScoreAlignment, optional
        alignment between s1 and s2 with the score as a float between 0 and 100

    Examples
    --------
    >>> s1 = "a certain string"
    >>> s2 = "cetain"
    >>> res = fuzz.partial_ratio_alignment(s1, s2)
    >>> res
    ScoreAlignment(score=83.33333333333334, src_start=2, src_end=8, dest_start=0, dest_end=6)

    Using the alignment information it is possible to calculate the same fuzz.ratio

    >>> fuzz.ratio(s1[res.src_start:res.src_end], s2[res.dest_start:res.dest_end])
    83.33333333333334
    """
    if is_none(s1) or is_none(s2):
        return None

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    if score_cutoff is None:
        score_cutoff = 0

    if not s1 and not s2:
        return ScoreAlignment(100.0, 0, 0, 0, 0)

    if len(s1) <= len(s2):
        shorter = s1
        longer = s2
    else:
        shorter = s2
        longer = s1

    res = _partial_ratio_short_needle(shorter, longer, score_cutoff / 100)
    if res.score != 100 and len(s1) == len(s2):
        score_cutoff = max(score_cutoff, res.score)
        res2 = _partial_ratio_short_needle(longer, shorter, score_cutoff / 100)
        if res2.score > res.score:
            res = ScoreAlignment(
                res2.score, res2.dest_start, res2.dest_end, res2.src_start, res2.src_end
            )

    if res.score < score_cutoff:
        return None

    if len(s1) <= len(s2):
        return res

    return ScoreAlignment(
        res.score, res.dest_start, res.dest_end, res.src_start, res.src_end
    )


def token_sort_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Sorts the words in the strings and calculates the fuzz.ratio between them

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/token_sort_ratio.svg

    Examples
    --------
    >>> fuzz.token_sort_ratio("fuzzy wuzzy was a bear", "wuzzy fuzzy was a bear")
    100.0
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    sorted_s1 = " ".join(sorted(s1.split()))
    sorted_s2 = " ".join(sorted(s2.split()))
    return ratio(sorted_s1, sorted_s2, score_cutoff=score_cutoff)


def token_set_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Compares the words in the strings based on unique and common words between them
    using fuzz.ratio

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/token_set_ratio.svg

    Examples
    --------
    >>> fuzz.token_sort_ratio("fuzzy was a bear", "fuzzy fuzzy was a bear")
    83.8709716796875
    >>> fuzz.token_set_ratio("fuzzy was a bear", "fuzzy fuzzy was a bear")
    100.0
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    if score_cutoff is None:
        score_cutoff = 0

    tokens_a = set(s1.split())
    tokens_b = set(s2.split())

    # in FuzzyWuzzy this returns 0. For sake of compatibility return 0 here as well
    # see https://github.com/maxbachmann/RapidFuzz/issues/110
    if not tokens_a or not tokens_b:
        return 0

    intersect = tokens_a.intersection(tokens_b)
    diff_ab = tokens_a.difference(tokens_b)
    diff_ba = tokens_b.difference(tokens_a)

    if not intersect and (not diff_ab or not diff_ba):
        return 100

    diff_ab_joined = " ".join(sorted(diff_ab))
    diff_ba_joined = " ".join(sorted(diff_ba))

    ab_len = len(diff_ab_joined)
    ba_len = len(diff_ba_joined)
    # todo is length sum without joining faster?
    sect_len = len(" ".join(intersect))

    # string length sect+ab <-> sect and sect+ba <-> sect
    sect_ab_len = sect_len + (sect_len != 0) + ab_len
    sect_ba_len = sect_len + (sect_len != 0) + ba_len

    result = 0.0
    cutoff_distance = ceil((sect_ab_len + sect_ba_len) * (1 - score_cutoff / 100))
    dist = indel_distance(diff_ab_joined, diff_ba_joined, score_cutoff=cutoff_distance)

    if dist <= cutoff_distance:
        result = _norm_distance(dist, sect_ab_len + sect_ba_len, score_cutoff)

    # exit early since the other ratios are 0
    if not sect_len:
        return result

    # levenshtein distance sect+ab <-> sect and sect+ba <-> sect
    # since only sect is similar in them the distance can be calculated based on
    # the length difference
    sect_ab_dist = (sect_len != 0) + ab_len
    sect_ab_ratio = _norm_distance(sect_ab_dist, sect_len + sect_ab_len, score_cutoff)

    sect_ba_dist = (sect_len != 0) + ba_len
    sect_ba_ratio = _norm_distance(sect_ba_dist, sect_len + sect_ba_len, score_cutoff)

    return max(result, sect_ab_ratio, sect_ba_ratio)


def token_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Helper method that returns the maximum of fuzz.token_set_ratio and fuzz.token_sort_ratio
    (faster than manually executing the two functions)

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/token_ratio.svg
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    # todo write combined implementation
    return max(
        token_set_ratio(s1, s2, processor=None, score_cutoff=score_cutoff),
        token_sort_ratio(s1, s2, processor=None, score_cutoff=score_cutoff),
    )


def partial_token_sort_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    sorts the words in the strings and calculates the fuzz.partial_ratio between them

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/partial_token_sort_ratio.svg
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    sorted_s1 = " ".join(sorted(s1.split()))
    sorted_s2 = " ".join(sorted(s2.split()))
    return partial_ratio(sorted_s1, sorted_s2, score_cutoff=score_cutoff)


def partial_token_set_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Compares the words in the strings based on unique and common words between them
    using fuzz.partial_ratio

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/partial_token_set_ratio.svg
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    tokens_a = set(s1.split())
    tokens_b = set(s2.split())
    # in FuzzyWuzzy this returns 0. For sake of compatibility return 0 here as well
    # see https://github.com/maxbachmann/RapidFuzz/issues/110
    if not tokens_a or not tokens_b:
        return 0

    # exit early when there is a common word in both sequences
    if tokens_a.intersection(tokens_b):
        return 100

    diff_ab = " ".join(sorted(tokens_a.difference(tokens_b)))
    diff_ba = " ".join(sorted(tokens_b.difference(tokens_a)))
    return partial_ratio(diff_ab, diff_ba, score_cutoff=score_cutoff)


def partial_token_ratio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Helper method that returns the maximum of fuzz.partial_token_set_ratio and
    fuzz.partial_token_sort_ratio (faster than manually executing the two functions)

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/partial_token_ratio.svg
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    if score_cutoff is None:
        score_cutoff = 0

    tokens_split_a = s1.split()
    tokens_split_b = s2.split()
    tokens_a = set(tokens_split_a)
    tokens_b = set(tokens_split_b)

    # exit early when there is a common word in both sequences
    if tokens_a.intersection(tokens_b):
        return 100

    diff_ab = tokens_a.difference(tokens_b)
    diff_ba = tokens_b.difference(tokens_a)

    result = partial_ratio(
        " ".join(sorted(tokens_split_a)),
        " ".join(sorted(tokens_split_b)),
        score_cutoff=score_cutoff,
    )

    # do not calculate the same partial_ratio twice
    if len(tokens_split_a) == len(diff_ab) and len(tokens_split_b) == len(diff_ba):
        return result

    score_cutoff = max(score_cutoff, result)
    return max(
        result,
        partial_ratio(
            " ".join(sorted(diff_ab)),
            " ".join(sorted(diff_ba)),
            score_cutoff=score_cutoff,
        ),
    )


def WRatio(
    s1: str | None,
    s2: str | None,
    *,
    processor: Callable[..., str] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Calculates a weighted ratio based on the other ratio algorithms

    Parameters
    ----------
    s1 : str
        First string to compare.
    s2 : str
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Notes
    -----
    .. image:: img/WRatio.svg
    """
    if is_none(s1) or is_none(s2):
        return 0

    UNBASE_SCALE = 0.95

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)

    # in FuzzyWuzzy this returns 0. For sake of compatibility return 0 here as well
    # see https://github.com/maxbachmann/RapidFuzz/issues/110
    if not s1 or not s2:
        return 0

    if score_cutoff is None:
        score_cutoff = 0

    len1 = len(s1)
    len2 = len(s2)
    len_ratio = len1 / len2 if len1 > len2 else len2 / len1

    end_ratio = ratio(s1, s2, score_cutoff=score_cutoff)
    if len_ratio < 1.5:
        score_cutoff = max(score_cutoff, end_ratio) / UNBASE_SCALE
        return max(
            end_ratio,
            token_ratio(s1, s2, score_cutoff=score_cutoff, processor=None)
            * UNBASE_SCALE,
        )

    PARTIAL_SCALE = 0.9 if len_ratio < 8.0 else 0.6
    score_cutoff = max(score_cutoff, end_ratio) / PARTIAL_SCALE
    end_ratio = max(
        end_ratio, partial_ratio(s1, s2, score_cutoff=score_cutoff) * PARTIAL_SCALE
    )

    score_cutoff = max(score_cutoff, end_ratio) / UNBASE_SCALE
    return max(
        end_ratio,
        partial_token_ratio(s1, s2, score_cutoff=score_cutoff, processor=None)
        * UNBASE_SCALE
        * PARTIAL_SCALE,
    )


def QRatio(
    s1: str | bytes | None,
    s2: str | bytes | None,
    *,
    processor: Callable[..., str | bytes] | None | bool = default_process,
    score_cutoff: float | None = None,
) -> float:
    """
    Calculates a quick ratio between two strings using fuzz.ratio.
    The only difference to fuzz.ratio is, that this preprocesses
    the strings by default.

    Parameters
    ----------
    s1 : str | bytes
        First string to compare.
    s2 : str | bytes
        Second string to compare.
    processor: callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is ``utils.default_process``.
    score_cutoff : float, optional
        Optional argument for a score threshold as a float between 0 and 100.
        For ratio < score_cutoff 0 is returned instead. Default is 0,
        which deactivates this behaviour.

    Returns
    -------
    similarity : float
        similarity between s1 and s2 as a float between 0 and 100

    Examples
    --------
    >>> fuzz.QRatio("this is a test", "THIS is a test!")
    100.0
    """
    if is_none(s1) or is_none(s2):
        return 0

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if processor is not None:
        s1 = processor(s1)
        s2 = processor(s2)
    # in FuzzyWuzzy this returns 0. For sake of compatibility return 0 here as well
    # see https://github.com/maxbachmann/RapidFuzz/issues/110
    if not s1 or not s2:
        return 0

    return ratio(s1, s2, score_cutoff=score_cutoff)
