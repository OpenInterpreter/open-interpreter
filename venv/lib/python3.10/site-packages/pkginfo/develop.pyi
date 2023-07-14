from .distribution import Distribution as Distribution

class Develop(Distribution):
    path: str
    metadata_version: str
    def __init__(self, path: str, metadata_version: str | None = ...) -> None: ...
    def read(self) -> bytes: ...
