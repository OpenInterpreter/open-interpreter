from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from packaging.utils import canonicalize_name
from poetry.core.utils.helpers import module_name
from tomlkit import inline_table
from tomlkit import loads
from tomlkit import table
from tomlkit.toml_document import TOMLDocument

from poetry.pyproject.toml import PyProjectTOML


if TYPE_CHECKING:
    from collections.abc import Mapping

    from tomlkit.items import InlineTable


POETRY_DEFAULT = """\
[tool.poetry]
name = ""
version = ""
description = ""
authors = []
license = ""
readme = ""
packages = []

[tool.poetry.dependencies]

[tool.poetry.group.dev.dependencies]
"""

BUILD_SYSTEM_MIN_VERSION: str | None = None
BUILD_SYSTEM_MAX_VERSION: str | None = None


class Layout:
    def __init__(
        self,
        project: str,
        version: str = "0.1.0",
        description: str = "",
        readme_format: str = "md",
        author: str | None = None,
        license: str | None = None,
        python: str = "*",
        dependencies: Mapping[str, str | Mapping[str, Any]] | None = None,
        dev_dependencies: Mapping[str, str | Mapping[str, Any]] | None = None,
    ) -> None:
        self._project = canonicalize_name(project)
        self._package_path_relative = Path(
            *(module_name(part) for part in project.split("."))
        )
        self._package_name = ".".join(self._package_path_relative.parts)
        self._version = version
        self._description = description

        self._readme_format = readme_format.lower()

        self._license = license
        self._python = python
        self._dependencies = dependencies or {}
        self._dev_dependencies = dev_dependencies or {}

        if not author:
            author = "Your Name <you@example.com>"

        self._author = author

    @property
    def basedir(self) -> Path:
        return Path()

    @property
    def package_path(self) -> Path:
        return self.basedir / self._package_path_relative

    def get_package_include(self) -> InlineTable | None:
        package = inline_table()

        # If a project is created in the root directory (this is reasonable inside a
        # docker container, eg <https://github.com/python-poetry/poetry/issues/5103>)
        # then parts will be empty.
        parts = self._package_path_relative.parts
        if not parts:
            return None

        include = parts[0]
        package.append("include", include)

        if self.basedir != Path():
            package.append("from", self.basedir.as_posix())
        else:
            if include == self._project:
                # package include and package name are the same,
                # packages table is redundant here.
                return None

        return package

    def create(self, path: Path, with_tests: bool = True) -> None:
        path.mkdir(parents=True, exist_ok=True)

        self._create_default(path)
        self._create_readme(path)

        if with_tests:
            self._create_tests(path)

        self._write_poetry(path)

    def generate_poetry_content(self) -> TOMLDocument:
        template = POETRY_DEFAULT

        content: dict[str, Any] = loads(template)

        poetry_content = content["tool"]["poetry"]
        poetry_content["name"] = self._project
        poetry_content["version"] = self._version
        poetry_content["description"] = self._description
        poetry_content["authors"].append(self._author)

        if self._license:
            poetry_content["license"] = self._license
        else:
            poetry_content.remove("license")

        poetry_content["readme"] = f"README.{self._readme_format}"
        packages = self.get_package_include()
        if packages:
            poetry_content["packages"].append(packages)
        else:
            poetry_content.remove("packages")

        poetry_content["dependencies"]["python"] = self._python

        for dep_name, dep_constraint in self._dependencies.items():
            poetry_content["dependencies"][dep_name] = dep_constraint

        if self._dev_dependencies:
            for dep_name, dep_constraint in self._dev_dependencies.items():
                poetry_content["group"]["dev"]["dependencies"][
                    dep_name
                ] = dep_constraint
        else:
            del poetry_content["group"]

        # Add build system
        build_system = table()
        build_system_version = ""

        if BUILD_SYSTEM_MIN_VERSION is not None:
            build_system_version = ">=" + BUILD_SYSTEM_MIN_VERSION
        if BUILD_SYSTEM_MAX_VERSION is not None:
            if build_system_version:
                build_system_version += ","
            build_system_version += "<" + BUILD_SYSTEM_MAX_VERSION

        build_system.add("requires", ["poetry-core" + build_system_version])
        build_system.add("build-backend", "poetry.core.masonry.api")

        assert isinstance(content, TOMLDocument)
        content.add("build-system", build_system)

        return content

    def _create_default(self, path: Path, src: bool = True) -> None:
        package_path = path / self.package_path
        package_path.mkdir(parents=True)

        package_init = package_path / "__init__.py"
        package_init.touch()

    def _create_readme(self, path: Path) -> Path:
        readme_file = path.joinpath(f"README.{self._readme_format}")
        readme_file.touch()
        return readme_file

    @staticmethod
    def _create_tests(path: Path) -> None:
        tests = path / "tests"
        tests.mkdir()

        tests_init = tests / "__init__.py"
        tests_init.touch(exist_ok=False)

    def _write_poetry(self, path: Path) -> None:
        pyproject = PyProjectTOML(path / "pyproject.toml")
        content = self.generate_poetry_content()
        for section, item in content.items():
            pyproject.data.append(section, item)
        pyproject.save()
