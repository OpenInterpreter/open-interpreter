# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann
from rapidfuzz._feature_detector import AVX2, supports

if supports(AVX2):
    from rapidfuzz.distance.metrics_cpp_avx2 import levenshtein_distance as distance
    from rapidfuzz.distance.metrics_cpp_avx2 import levenshtein_editops as editops
    from rapidfuzz.distance.metrics_cpp_avx2 import (
        levenshtein_normalized_distance as normalized_distance,
    )
    from rapidfuzz.distance.metrics_cpp_avx2 import (
        levenshtein_normalized_similarity as normalized_similarity,
    )
    from rapidfuzz.distance.metrics_cpp_avx2 import levenshtein_opcodes as opcodes
    from rapidfuzz.distance.metrics_cpp_avx2 import levenshtein_similarity as similarity
else:
    from rapidfuzz.distance.metrics_cpp import levenshtein_distance as distance
    from rapidfuzz.distance.metrics_cpp import levenshtein_editops as editops
    from rapidfuzz.distance.metrics_cpp import (
        levenshtein_normalized_distance as normalized_distance,
    )
    from rapidfuzz.distance.metrics_cpp import (
        levenshtein_normalized_similarity as normalized_similarity,
    )
    from rapidfuzz.distance.metrics_cpp import levenshtein_opcodes as opcodes
    from rapidfuzz.distance.metrics_cpp import levenshtein_similarity as similarity


__all__ = [
    "distance",
    "editops",
    "normalized_distance",
    "normalized_similarity",
    "opcodes",
    "similarity",
]
