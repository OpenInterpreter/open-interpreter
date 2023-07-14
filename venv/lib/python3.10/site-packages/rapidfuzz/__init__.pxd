from libc.stdint cimport int64_t, uint32_t
from libcpp cimport bool


cdef extern from "rapidfuzz.h":
    cdef enum RF_StringType:
        RF_UINT8
        RF_UINT16
        RF_UINT32
        RF_UINT64

    uint32_t RF_SCORER_FLAG_MULTI_STRING_INIT
    uint32_t RF_SCORER_FLAG_MULTI_STRING_CALL
    uint32_t RF_SCORER_FLAG_RESULT_F64
    uint32_t RF_SCORER_FLAG_RESULT_I64
    uint32_t RF_SCORER_FLAG_SYMMETRIC
    uint32_t RF_SCORER_FLAG_TRIANGLE_INEQUALITY

    ctypedef struct RF_String:
        void (*dtor) (RF_String*) nogil

        RF_StringType kind
        void* data
        int64_t length
        void* context

    ctypedef bool (*RF_Preprocess) (object, RF_String*) except False

    uint32_t PREPROCESSOR_STRUCT_VERSION

    ctypedef struct RF_Preprocessor:
        uint32_t version
        RF_Preprocess preprocess

    ctypedef struct RF_Kwargs:
        void (*dtor) (RF_Kwargs*)

        void* context

    ctypedef bool (*RF_KwargsInit) (RF_Kwargs*, dict) except False

    ctypedef union _RF_ScorerFunc_union:
        bool (*f64) (const RF_ScorerFunc*, const RF_String*, int64_t, double, double*) except False nogil
        bool (*i64) (const RF_ScorerFunc*, const RF_String*, int64_t, int64_t, int64_t*) except False nogil

    ctypedef struct RF_ScorerFunc:
        void (*dtor) (RF_ScorerFunc*) nogil
        _RF_ScorerFunc_union call

        void* context

    ctypedef bool (*RF_ScorerFuncInit) (RF_ScorerFunc*, const RF_Kwargs*, int64_t, const RF_String*) except False nogil

    ctypedef union _RF_RF_ScorerFlags_OptimalScore_union:
        double  f64
        int64_t i64

    ctypedef union _RF_RF_ScorerFlags_WorstScore_union:
        double  f64
        int64_t i64

    ctypedef struct RF_ScorerFlags:
        uint32_t flags
        _RF_RF_ScorerFlags_OptimalScore_union optimal_score
        _RF_RF_ScorerFlags_WorstScore_union worst_score

    ctypedef bool (*RF_GetScorerFlags) (const RF_Kwargs*, RF_ScorerFlags*) except False nogil

    uint32_t SCORER_STRUCT_VERSION

    ctypedef struct RF_Scorer:
        uint32_t version
        RF_KwargsInit kwargs_init
        RF_GetScorerFlags get_scorer_flags
        RF_ScorerFuncInit scorer_func_init
