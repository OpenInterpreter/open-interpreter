# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann

from __future__ import annotations

import heapq
from math import isnan
from typing import (
    Any,
    Callable,
    Collection,
    Hashable,
    Iterable,
    Mapping,
    Sequence,
    overload,
)

from rapidfuzz._utils import ScorerFlag
from rapidfuzz.fuzz import WRatio, ratio
from rapidfuzz.utils import default_process

__all__ = ["extract", "extract_iter", "extractOne", "cdist"]


def _get_scorer_flags_py(scorer: Any, kwargs: dict[str, Any]) -> tuple[int, int]:
    params = getattr(scorer, "_RF_ScorerPy", None)
    if params is not None:
        flags = params["get_scorer_flags"](**kwargs)
        return (flags["worst_score"], flags["optimal_score"])
    return (0, 100)


def _is_none(s: Any) -> bool:
    if s is None:
        return True

    if isinstance(s, float) and isnan(s):
        return True

    return False


@overload
def extract_iter(
    query: Sequence[Hashable] | None,
    choices: Iterable[Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> Iterable[tuple[Sequence[Hashable], int | float, int]]:
    ...


@overload
def extract_iter(
    query: Sequence[Hashable] | None,
    choices: Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> Iterable[tuple[Sequence[Hashable], int | float, Any]]:
    ...


def extract_iter(
    query: Sequence[Hashable] | None,
    choices: Iterable[Sequence[Hashable] | None]
    | Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = default_process,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> Iterable[tuple[Sequence[Hashable], int | float, Any]]:
    """
    Find the best match in a list of choices

    Parameters
    ----------
    query : Sequence[Hashable]
        string we want to find
    choices : Iterable[Sequence[Hashable]] | Mapping[Sequence[Hashable]]
        list of all strings the query should be compared with or dict with a mapping
        {<result>: <string to compare>}
    scorer : Callable, optional
        Optional callable that is used to calculate the matching score between
        the query and each choice. This can be any of the scorers included in RapidFuzz
        (both scorers that calculate the edit distance or the normalized edit distance), or
        a custom function, which returns a normalized edit distance.
        fuzz.WRatio is used by default.
    processor : Callable, optional
        Optional callable that reformats the strings.
        utils.default_process is used by default, which lowercases the strings and trims whitespace
    score_cutoff : Any, optional
        Optional argument for a score threshold. When an edit distance is used this represents the maximum
        edit distance and matches with a `distance <= score_cutoff` are ignored. When a
        normalized edit distance is used this represents the minimal similarity
        and matches with a `similarity >= score_cutoff` are ignored. Default is None, which deactivates this behaviour.
    score_hint : Any, optional
        Optional argument for an expected score to be passed to the scorer.
        This is used to select a faster implementation. Default is None,
        which deactivates this behaviour.
    **kwargs : Any, optional
        any other named parameters are passed to the scorer. This can be used to pass
        e.g. weights to string_metric.levenshtein

    Yields
    -------
    Tuple[Sequence[Hashable], Any, Any]
        Yields similarity between the query and each choice in form of a Tuple with 3 elements.
        The values stored in the tuple depend on the types of the input arguments.

        * The first element is always the current `choice`, which is the value that's compared to the query.

        * The second value represents the similarity calculated by the scorer. This can be:

          * An edit distance (distance is 0 for a perfect match and > 0 for non perfect matches).
            In this case only choices which have a `distance <= max` are yielded.
            An example of a scorer with this behavior is `string_metric.levenshtein`.
          * A normalized edit distance (similarity is a score between 0 and 100, with 100 being a perfect match).
            In this case only choices which have a `similarity >= score_cutoff` are yielded.
            An example of a scorer with this behavior is `string_metric.normalized_levenshtein`.

          Note, that for all scorers, which are not provided by RapidFuzz, only normalized edit distances are supported.

        * The third parameter depends on the type of the `choices` argument it is:

          * The `index of choice` when choices is a simple iterable like a list
          * The `key of choice` when choices is a mapping like a dict, or a pandas Series

    """
    worst_score, optimal_score = _get_scorer_flags_py(scorer, kwargs)
    lowest_score_worst = optimal_score > worst_score

    if _is_none(query):
        return

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if score_cutoff is None:
        score_cutoff = worst_score

    # preprocess the query
    if processor is not None:
        query = processor(query)

    choices_iter: Iterable[tuple[Any, Sequence[Hashable] | None]]
    choices_iter = choices.items() if hasattr(choices, "items") else enumerate(choices)  # type: ignore[union-attr]
    for key, choice in choices_iter:
        if _is_none(choice):
            continue

        if processor is None:
            score = scorer(
                query, choice, processor=None, score_cutoff=score_cutoff, **kwargs
            )
        else:
            score = scorer(
                query,
                processor(choice),
                processor=None,
                score_cutoff=score_cutoff,
                **kwargs,
            )

        if lowest_score_worst:
            if score >= score_cutoff:
                yield (choice, score, key)
        else:
            if score <= score_cutoff:
                yield (choice, score, key)


@overload
def extractOne(
    query: Sequence[Hashable] | None,
    choices: Iterable[Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> tuple[Sequence[Hashable], int | float, int] | None:
    ...


@overload
def extractOne(
    query: Sequence[Hashable] | None,
    choices: Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> tuple[Sequence[Hashable], int | float, Any] | None:
    ...


def extractOne(
    query: Sequence[Hashable] | None,
    choices: Iterable[Sequence[Hashable] | None]
    | Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = default_process,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> tuple[Sequence[Hashable], int | float, Any] | None:
    """
    Find the best match in a list of choices. When multiple elements have the same similarity,
    the first element is returned.

    Parameters
    ----------
    query : Sequence[Hashable]
        string we want to find
    choices : Iterable[Sequence[Hashable]] | Mapping[Sequence[Hashable]]
        list of all strings the query should be compared with or dict with a mapping
        {<result>: <string to compare>}
    scorer : Callable, optional
        Optional callable that is used to calculate the matching score between
        the query and each choice. This can be any of the scorers included in RapidFuzz
        (both scorers that calculate the edit distance or the normalized edit distance), or
        a custom function, which returns a normalized edit distance.
        fuzz.WRatio is used by default.
    processor : Callable, optional
        Optional callable that reformats the strings.
        utils.default_process is used by default, which lowercases the strings and trims whitespace
    score_cutoff : Any, optional
        Optional argument for a score threshold. When an edit distance is used this represents the maximum
        edit distance and matches with a `distance <= score_cutoff` are ignored. When a
        normalized edit distance is used this represents the minimal similarity
        and matches with a `similarity >= score_cutoff` are ignored. Default is None, which deactivates this behaviour.
    score_hint : Any, optional
        Optional argument for an expected score to be passed to the scorer.
        This is used to select a faster implementation. Default is None,
        which deactivates this behaviour.
    **kwargs : Any, optional
        any other named parameters are passed to the scorer. This can be used to pass
        e.g. weights to string_metric.levenshtein

    Returns
    -------
    Tuple[Sequence[Hashable], Any, Any]
        Returns the best match in form of a Tuple with 3 elements. The values stored in the
        tuple depend on the types of the input arguments.

        * The first element is always the `choice`, which is the value that's compared to the query.

        * The second value represents the similarity calculated by the scorer. This can be:

          * An edit distance (distance is 0 for a perfect match and > 0 for non perfect matches).
            In this case only choices which have a `distance <= score_cutoff` are returned.
            An example of a scorer with this behavior is `string_metric.levenshtein`.
          * A normalized edit distance (similarity is a score between 0 and 100, with 100 being a perfect match).
            In this case only choices which have a `similarity >= score_cutoff` are returned.
            An example of a scorer with this behavior is `string_metric.normalized_levenshtein`.

          Note, that for all scorers, which are not provided by RapidFuzz, only normalized edit distances are supported.

        * The third parameter depends on the type of the `choices` argument it is:

          * The `index of choice` when choices is a simple iterable like a list
          * The `key of choice` when choices is a mapping like a dict, or a pandas Series

    None
        When no choice has a `similarity >= score_cutoff`/`distance <= score_cutoff` None is returned

    Examples
    --------

    >>> from rapidfuzz.process import extractOne
    >>> from rapidfuzz.string_metric import levenshtein, normalized_levenshtein
    >>> from rapidfuzz.fuzz import ratio

    extractOne can be used with normalized edit distances.

    >>> extractOne("abcd", ["abce"], scorer=ratio)
    ("abcd", 75.0, 1)
    >>> extractOne("abcd", ["abce"], scorer=normalized_levenshtein)
    ("abcd", 75.0, 1)

    extractOne can be used with edit distances as well.

    >>> extractOne("abcd", ["abce"], scorer=levenshtein)
    ("abce", 1, 0)

    additional settings of the scorer can be passed as keyword arguments to extractOne

    >>> extractOne("abcd", ["abce"], scorer=levenshtein, weights=(1,1,2))
    ("abcde", 2, 1)

    when a mapping is used for the choices the key of the choice is returned instead of the List index

    >>> extractOne("abcd", {"key": "abce"}, scorer=ratio)
    ("abcd", 75.0, "key")

    By default each string is preprocessed using `utils.default_process`, which lowercases the strings,
    replaces non alphanumeric characters with whitespaces and trims whitespaces from start and end of them.
    This behavior can be changed by passing a custom function, or None to disable the behavior. Preprocessing
    can take a significant part of the runtime, so it makes sense to disable it, when it is not required.


    >>> extractOne("abcd", ["abdD"], scorer=ratio)
    ("abcD", 100.0, 0)
    >>> extractOne("abcd", ["abdD"], scorer=ratio, processor=None)
    ("abcD", 75.0, 0)
    >>> extractOne("abcd", ["abdD"], scorer=ratio, processor=lambda s: s.upper())
    ("abcD", 100.0, 0)

    When only results with a similarity above a certain threshold are relevant, the parameter score_cutoff can be
    used to filter out results with a lower similarity. This threshold is used by some of the scorers to exit early,
    when they are sure, that the similarity is below the threshold.
    For normalized edit distances all results with a similarity below score_cutoff are filtered out

    >>> extractOne("abcd", ["abce"], scorer=ratio)
    ("abce", 75.0, 0)
    >>> extractOne("abcd", ["abce"], scorer=ratio, score_cutoff=80)
    None

    For edit distances all results with an edit distance above the score_cutoff are filtered out

    >>> extractOne("abcd", ["abce"], scorer=levenshtein, weights=(1,1,2))
    ("abce", 2, 0)
    >>> extractOne("abcd", ["abce"], scorer=levenshtein, weights=(1,1,2), score_cutoff=1)
    None

    """
    worst_score, optimal_score = _get_scorer_flags_py(scorer, kwargs)
    lowest_score_worst = optimal_score > worst_score

    if _is_none(query):
        return None

    if processor is True:
        processor = default_process
    elif processor is False:
        processor = None

    if score_cutoff is None:
        score_cutoff = worst_score

    # preprocess the query
    if processor is not None:
        query = processor(query)

    result: tuple[Sequence[Hashable], int | float, Any] | None = None

    choices_iter: Iterable[tuple[Any, Sequence[Hashable] | None]]
    choices_iter = choices.items() if hasattr(choices, "items") else enumerate(choices)  # type: ignore[union-attr]
    for key, choice in choices_iter:
        if _is_none(choice):
            continue

        if processor is None:
            score = scorer(
                query, choice, processor=None, score_cutoff=score_cutoff, **kwargs
            )
        else:
            score = scorer(
                query,
                processor(choice),
                processor=None,
                score_cutoff=score_cutoff,
                **kwargs,
            )

        if lowest_score_worst:
            if score >= score_cutoff and (result is None or score > result[1]):
                score_cutoff = score
                result = (choice, score, key)
        else:
            if score <= score_cutoff and (result is None or score < result[1]):
                score_cutoff = score
                result = (choice, score, key)

        if score == optimal_score:
            break

    return result


@overload
def extract(
    query: Sequence[Hashable] | None,
    choices: Collection[Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    limit: int | None = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> list[tuple[Sequence[Hashable], int | float, int]]:
    ...


@overload
def extract(
    query: Sequence[Hashable] | None,
    choices: Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = None,
    limit: int | None = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> list[tuple[Sequence[Hashable], int | float, Any]]:
    ...


def extract(
    query: Sequence[Hashable] | None,
    choices: Collection[Sequence[Hashable] | None]
    | Mapping[Any, Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = WRatio,
    processor: Callable[..., Sequence[Hashable]] | None | bool = default_process,
    limit: int | None = 5,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    **kwargs: Any,
) -> list[tuple[Sequence[Hashable], int | float, Any]]:
    """
    Find the best matches in a list of choices. The list is sorted by the similarity.
    When multiple choices have the same similarity, they are sorted by their index

    Parameters
    ----------
    query : Sequence[Hashable]
        string we want to find
    choices : Collection[Sequence[Hashable]] | Mapping[Sequence[Hashable]]
        list of all strings the query should be compared with or dict with a mapping
        {<result>: <string to compare>}
    scorer : Callable, optional
        Optional callable that is used to calculate the matching score between
        the query and each choice. This can be any of the scorers included in RapidFuzz
        (both scorers that calculate the edit distance or the normalized edit distance), or
        a custom function, which returns a normalized edit distance.
        fuzz.WRatio is used by default.
    processor : Callable, optional
        Optional callable that reformats the strings.
        utils.default_process is used by default, which lowercases the strings and trims whitespace
    limit : int
        maximum amount of results to return
    score_cutoff : Any, optional
        Optional argument for a score threshold. When an edit distance is used this represents the maximum
        edit distance and matches with a `distance <= score_cutoff` are ignored. When a
        normalized edit distance is used this represents the minimal similarity
        and matches with a `similarity >= score_cutoff` are ignored. Default is None, which deactivates this behaviour.
    score_hint : Any, optional
        Optional argument for an expected score to be passed to the scorer.
        This is used to select a faster implementation. Default is None,
        which deactivates this behaviour.
    **kwargs : Any, optional
        any other named parameters are passed to the scorer. This can be used to pass
        e.g. weights to string_metric.levenshtein

    Returns
    -------
    List[Tuple[Sequence[Hashable], Any, Any]]
        The return type is always a List of Tuples with 3 elements. However the values stored in the
        tuple depend on the types of the input arguments.

        * The first element is always the `choice`, which is the value that's compared to the query.

        * The second value represents the similarity calculated by the scorer. This can be:

          * An edit distance (distance is 0 for a perfect match and > 0 for non perfect matches).
            In this case only choices which have a `distance <= max` are returned.
            An example of a scorer with this behavior is `string_metric.levenshtein`.
          * A normalized edit distance (similarity is a score between 0 and 100, with 100 being a perfect match).
            In this case only choices which have a `similarity >= score_cutoff` are returned.
            An example of a scorer with this behavior is `string_metric.normalized_levenshtein`.

          Note, that for all scorers, which are not provided by RapidFuzz, only normalized edit distances are supported.

        * The third parameter depends on the type of the `choices` argument it is:

          * The `index of choice` when choices is a simple iterable like a list
          * The `key of choice` when choices is a mapping like a dict, or a pandas Series

        The list is sorted by `score_cutoff` or `max` depending on the scorer used. The first element in the list
        has the `highest similarity`/`smallest distance`.

    """
    worst_score, optimal_score = _get_scorer_flags_py(scorer, kwargs)
    lowest_score_worst = optimal_score > worst_score

    result_iter = extract_iter(
        query,
        choices,
        processor=processor,
        scorer=scorer,
        score_cutoff=score_cutoff,
        **kwargs,
    )

    if limit is None:
        return sorted(result_iter, key=lambda i: i[1], reverse=lowest_score_worst)

    if lowest_score_worst:
        return heapq.nlargest(limit, result_iter, key=lambda i: i[1])
    return heapq.nsmallest(limit, result_iter, key=lambda i: i[1])


try:
    import numpy as np
except BaseException:
    pass


def _dtype_to_type_num(
    dtype: np.dtype | None,
    scorer: Callable[..., int | float],
    **kwargs: dict[str, Any],
) -> np.dtype:
    import numpy as np

    if dtype is not None:
        return dtype

    params = getattr(scorer, "_RF_ScorerPy", None)
    if params is not None:
        flags = params["get_scorer_flags"](**kwargs)
        if flags["flags"] & ScorerFlag.RESULT_I64:
            return np.int32
        return np.float32

    return np.float32


def _is_symmetric(scorer: Callable[..., int | float], **kwargs: dict[str, Any]) -> bool:
    params = getattr(scorer, "_RF_ScorerPy", None)
    if params is not None:
        flags = params["get_scorer_flags"](**kwargs)
        if flags["flags"] & ScorerFlag.SYMMETRIC:
            return True

    return False


def cdist(
    queries: Collection[Sequence[Hashable] | None],
    choices: Collection[Sequence[Hashable] | None],
    *,
    scorer: Callable[..., int | float] = ratio,
    processor: Callable[..., Sequence[Hashable]] | None = None,
    score_cutoff: int | float | None = None,
    score_hint: int | float | None = None,
    dtype: np.dtype | None = None,
    workers: int = 1,
    **kwargs: Any,
) -> np.ndarray:
    """
    Compute distance/similarity between each pair of the two collections of inputs.

    Parameters
    ----------
    queries : Collection[Sequence[Hashable]]
        list of all strings the queries
    choices : Collection[Sequence[Hashable]]
        list of all strings the query should be compared
    scorer : Callable, optional
        Optional callable that is used to calculate the matching score between
        the query and each choice. This can be:

        - a scorer using the RapidFuzz C-API like the builtin scorers in RapidFuzz,
          which can return a distance or similarity between two strings. Further details can be found here.
        - a Python function which returns a similarity between two strings in the range 0-100. This is not
          recommended, since it is far slower than a scorer using the RapidFuzz C-API.

        fuzz.ratio is used by default.
    processor : Callable, optional
        Optional callable that is used to preprocess the strings before
        comparing them. Default is None, which deactivates this behaviour.
    score_cutoff : Any, optional
        Optional argument for a score threshold to be passed to the scorer.
        Default is None, which deactivates this behaviour.
    score_hint : Any, optional
        Optional argument for an expected score to be passed to the scorer.
        This is used to select a faster implementation. Default is None,
        which deactivates this behaviour.
    dtype : data-type, optional
        The desired data-type for the result array.Depending on the scorer type the following
        dtypes are supported:

        - similarity:
          - np.float32, np.float64
          - np.uint8 -> stores fixed point representation of the result scaled to a range 0-100
        - distance:
          - np.int8, np.int16, np.int32, np.int64

        If not given, then the type will be np.float32 for similarities and np.int32 for distances.
    workers : int, optional
        The calculation is subdivided into workers sections and evaluated in parallel.
        Supply -1 to use all available CPU cores.
        This argument is only available for scorers using the RapidFuzz C-API so far, since it
        releases the Python GIL.
    **kwargs : Any, optional
        any other named parameters are passed to the scorer. This can be used to pass
        e.g. weights to string_metric.levenshtein

    Returns
    -------
    ndarray
        Returns a matrix of dtype with the distance/similarity between each pair
        of the two collections of inputs.
    """
    import numpy as np

    dtype = _dtype_to_type_num(dtype, scorer, **kwargs)
    results = np.zeros((len(queries), len(choices)), dtype=dtype)

    if queries is choices and _is_symmetric(scorer, **kwargs):
        if processor is None:
            proc_queries = list(queries)
        else:
            proc_queries = [processor(x) for x in queries]

        for i, query in enumerate(proc_queries):
            results[i, i] = scorer(
                query, query, processor=None, score_cutoff=score_cutoff, **kwargs
            )
            for j in range(i + 1, len(proc_queries)):
                results[i, j] = results[j, i] = scorer(
                    query,
                    proc_queries[j],
                    processor=None,
                    score_cutoff=score_cutoff,
                    **kwargs,
                )
    else:
        if processor is None:
            proc_choices = list(choices)
        else:
            proc_choices = [processor(x) for x in choices]

        for i, query in enumerate(queries):
            proc_query = processor(query) if processor else query
            for j, choice in enumerate(proc_choices):
                results[i, j] = scorer(
                    proc_query,
                    choice,
                    processor=None,
                    score_cutoff=score_cutoff,
                    **kwargs,
                )

    return results
