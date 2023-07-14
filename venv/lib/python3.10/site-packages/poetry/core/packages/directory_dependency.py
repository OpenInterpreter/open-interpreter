from __future__ import annotations

import functools

from typing import TYPE_CHECKING

from poetry.core.packages.path_dependency import PathDependency
from poetry.core.packages.utils.utils import is_python_project
from poetry.core.pyproject.toml import PyProjectTOML


if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class DirectoryDependency(PathDependency):
    def __init__(
        self,
        name: str,
        path: Path,
        groups: Iterable[str] | None = None,
        optional: bool = False,
        base: Path | None = None,
        develop: bool = False,
        extras: Iterable[str] | None = None,
    ) -> None:
        super().__init__(
            name,
            path,
            source_type="directory",
            groups=groups,
            optional=optional,
            base=base,
            extras=extras,
        )
        self._develop = develop

        # cache this function to avoid multiple IO reads and parsing
        self.supports_poetry = functools.lru_cache(maxsize=1)(self._supports_poetry)

    @property
    def develop(self) -> bool:
        return self._develop

    def _validate(self) -> str:
        message = super()._validate()
        if message:
            return message

        if self._full_path.is_file():
            return (
                f"{self._full_path} for {self.pretty_name} is a file,"
                " expected a directory"
            )
        if not is_python_project(self._full_path):
            return (
                f"Directory {self._full_path} for {self.pretty_name} does not seem"
                " to be a Python package"
            )
        return ""

    def _supports_poetry(self) -> bool:
        return PyProjectTOML(self._full_path / "pyproject.toml").is_poetry_project()
