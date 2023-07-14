import types

from .distribution import Distribution

def get_metadata(path_or_module: str | types.ModuleType, metadata_version: str | None = ...) -> Distribution | None: ...
