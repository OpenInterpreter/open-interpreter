from openai.datalib.common import INSTRUCTIONS, MissingDependencyError

try:
    import numpy
except ImportError:
    numpy = None

HAS_NUMPY = bool(numpy)

NUMPY_INSTRUCTIONS = INSTRUCTIONS.format(library="numpy")


def assert_has_numpy():
    if not HAS_NUMPY:
        raise MissingDependencyError(NUMPY_INSTRUCTIONS)
