from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from poetry.core.pyproject.toml import PyProjectTOML


if TYPE_CHECKING:
    from pathlib import Path

    from poetry.core.packages.project_package import ProjectPackage


class Poetry:
    def __init__(
        self,
        file: Path,
        local_config: dict[str, Any],
        package: ProjectPackage,
        pyproject_type: type[PyProjectTOML] = PyProjectTOML,
    ) -> None:
        self._pyproject = pyproject_type(file)
        self._package = package
        self._local_config = local_config

    @property
    def pyproject(self) -> PyProjectTOML:
        return self._pyproject

    @property
    def pyproject_path(self) -> Path:
        return self._pyproject.path

    @property
    def package(self) -> ProjectPackage:
        return self._package

    @property
    def local_config(self) -> dict[str, Any]:
        return self._local_config

    def get_project_config(self, config: str, default: Any = None) -> Any:
        return self._local_config.get("config", {}).get(config, default)
