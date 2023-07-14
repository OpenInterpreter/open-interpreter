from __future__ import annotations


class RepositoryError(Exception):
    pass


class PackageNotFound(Exception):
    pass


class InvalidSourceError(Exception):
    pass
