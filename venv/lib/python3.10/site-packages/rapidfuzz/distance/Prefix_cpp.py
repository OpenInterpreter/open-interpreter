# SPDX-License-Identifier: MIT
# Copyright (C) 2022 Max Bachmann
from rapidfuzz._feature_detector import AVX2, supports

if supports(AVX2):
    from rapidfuzz.distance.metrics_cpp_avx2 import prefix_distance as distance
    from rapidfuzz.distance.metrics_cpp_avx2 import (
        prefix_normalized_distance as normalized_distance,
    )
    from rapidfuzz.distance.metrics_cpp_avx2 import (
        prefix_normalized_similarity as normalized_similarity,
    )
    from rapidfuzz.distance.metrics_cpp_avx2 import prefix_similarity as similarity
else:
    from rapidfuzz.distance.metrics_cpp import prefix_distance as distance
    from rapidfuzz.distance.metrics_cpp import (
        prefix_normalized_distance as normalized_distance,
    )
    from rapidfuzz.distance.metrics_cpp import (
        prefix_normalized_similarity as normalized_similarity,
    )
    from rapidfuzz.distance.metrics_cpp import prefix_similarity as similarity


__all__ = [
    "distance",
    "normalized_distance",
    "normalized_similarity",
    "similarity",
]
