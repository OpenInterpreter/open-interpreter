from openai.datalib.common import INSTRUCTIONS, MissingDependencyError

try:
    import pandas
except ImportError:
    pandas = None

HAS_PANDAS = bool(pandas)

PANDAS_INSTRUCTIONS = INSTRUCTIONS.format(library="pandas")


def assert_has_pandas():
    if not HAS_PANDAS:
        raise MissingDependencyError(PANDAS_INSTRUCTIONS)
