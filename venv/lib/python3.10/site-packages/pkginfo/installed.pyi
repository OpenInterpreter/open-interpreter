import types

from .distribution import Distribution as Distribution

class Installed(Distribution):
    package_name: str
    package: str | types.ModuleType
    metadata_version: str
    def __init__(self, package: str | types.ModuleType, metadata_version: str | None = ...) -> None: ...
    def read(self) -> bytes: ...
