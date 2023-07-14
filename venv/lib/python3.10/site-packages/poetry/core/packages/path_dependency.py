from __future__ import annotations

import logging

from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from poetry.core.packages.dependency import Dependency
from poetry.core.packages.utils.utils import path_to_url


if TYPE_CHECKING:
    from collections.abc import Iterable


logger = logging.getLogger(__name__)


class PathDependency(Dependency, ABC):
    @abstractmethod
    def __init__(
        self,
        name: str,
        path: Path,
        *,
        source_type: str,
        groups: Iterable[str] | None = None,
        optional: bool = False,
        base: Path | None = None,
        subdirectory: str | None = None,
        extras: Iterable[str] | None = None,
    ) -> None:
        assert source_type in ("file", "directory")
        self._path = path
        self._base = base or Path.cwd()
        self._full_path = path

        if not self._path.is_absolute():
            self._full_path = self._base.joinpath(self._path).resolve()

        super().__init__(
            name,
            "*",
            groups=groups,
            optional=optional,
            allows_prereleases=True,
            source_type=source_type,
            source_url=self._full_path.as_posix(),
            source_subdirectory=subdirectory,
            extras=extras,
        )
        # cache validation result to avoid unnecessary file system access
        self._validation_error = self._validate()
        self.validate(raise_error=False)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def full_path(self) -> Path:
        return self._full_path

    @property
    def base(self) -> Path:
        return self._base

    def is_file(self) -> bool:
        return self._source_type == "file"

    def is_directory(self) -> bool:
        return self._source_type == "directory"

    def validate(self, *, raise_error: bool) -> bool:
        if not self._validation_error:
            return True
        if raise_error:
            raise ValueError(self._validation_error)
        logger.warning(self._validation_error)
        return False

    @property
    def base_pep_508_name(self) -> str:
        requirement = self.pretty_name

        if self.extras:
            extras = ",".join(sorted(self.extras))
            requirement += f"[{extras}]"

        path = path_to_url(self.full_path)
        requirement += f" @ {path}"

        return requirement

    def _validate(self) -> str:
        if not self._full_path.exists():
            return f"Path {self._full_path} for {self.pretty_name} does not exist"
        return ""
