from __future__ import annotations

from cleo.exceptions import CleoError


class PoetryConsoleError(CleoError):
    pass


class GroupNotFound(PoetryConsoleError):
    pass
