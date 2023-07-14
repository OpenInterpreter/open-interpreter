from .distribution import Distribution as Distribution

class BDist(Distribution):
    filename: str
    metadata_version: str
    def __init__(self, filename: str, metadata_version: str | None = ...) -> None: ...
    def read(self) -> bytes: ...
