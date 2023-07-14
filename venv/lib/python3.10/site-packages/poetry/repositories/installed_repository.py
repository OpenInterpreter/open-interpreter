from __future__ import annotations

import itertools
import json
import logging

from pathlib import Path
from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name
from poetry.core.packages.package import Package
from poetry.core.packages.utils.utils import url_to_path
from poetry.core.utils.helpers import module_name

from poetry.repositories.repository import Repository
from poetry.utils._compat import metadata


if TYPE_CHECKING:
    from poetry.utils.env import Env


logger = logging.getLogger(__name__)


class InstalledRepository(Repository):
    def __init__(self) -> None:
        super().__init__("poetry-installed")

    @classmethod
    def get_package_paths(cls, env: Env, name: str) -> set[Path]:
        """
        Process a .pth file within the site-packages directories, and return any valid
        paths. We skip executable .pth files as there is no reliable means to do this
        without side-effects to current run-time. Mo check is made that the item refers
        to a directory rather than a file, however, in order to maintain backwards
        compatibility, we allow non-existing paths to be discovered. The latter
        behaviour is different to how Python's site-specific hook configuration works.

        Reference: https://docs.python.org/3.8/library/site.html

        :param env: The environment to search for the .pth file in.
        :param name: The name of the package to search .pth file for.
        :return: A `Set` of valid `Path` objects.
        """
        paths = set()

        # we identify the candidate pth files to check, this is done so to handle cases
        # where the pth file for foo-bar might have been installed as either foo-bar.pth
        # or foo_bar.pth (expected) in either pure or platform lib directories.
        candidates = itertools.product(
            {env.purelib, env.platlib},
            {name, module_name(name)},
        )

        for lib, module in candidates:
            pth_file = lib.joinpath(module).with_suffix(".pth")
            if not pth_file.exists():
                continue

            with pth_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith(("#", "import ", "import\t")):
                        path = Path(line)
                        if not path.is_absolute():
                            path = lib.joinpath(path).resolve()
                        paths.add(path)

        src_path = env.path / "src" / name
        if not paths and src_path.exists():
            paths.add(src_path)

        return paths

    @classmethod
    def get_package_vcs_properties_from_path(cls, src: Path) -> tuple[str, str, str]:
        from poetry.vcs.git import Git

        info = Git.info(repo=src)
        return "git", info.origin, info.revision

    @classmethod
    def is_vcs_package(cls, package: Path | Package, env: Env) -> bool:
        # A VCS dependency should have been installed
        # in the src directory.
        src = env.path / "src"
        if isinstance(package, Package):
            return src.joinpath(package.name).is_dir()

        try:
            package.relative_to(env.path / "src")
        except ValueError:
            return False
        else:
            return True

    @classmethod
    def create_package_from_distribution(
        cls, distribution: metadata.Distribution, env: Env
    ) -> Package:
        # We first check for a direct_url.json file to determine
        # the type of package.
        path = Path(str(distribution._path))  # type: ignore[attr-defined]

        if (
            path.name.endswith(".dist-info")
            and path.joinpath("direct_url.json").exists()
        ):
            return cls.create_package_from_pep610(distribution)

        is_standard_package = env.is_path_relative_to_lib(path)

        source_type = None
        source_url = None
        source_reference = None
        source_resolved_reference = None
        source_subdirectory = None
        if is_standard_package:
            if path.name.endswith(".dist-info"):
                paths = cls.get_package_paths(
                    env=env, name=distribution.metadata["name"]
                )
                if paths:
                    is_editable_package = False
                    for src in paths:
                        if cls.is_vcs_package(src, env):
                            (
                                source_type,
                                source_url,
                                source_reference,
                            ) = cls.get_package_vcs_properties_from_path(src)
                            break

                        if not (
                            is_editable_package or env.is_path_relative_to_lib(src)
                        ):
                            is_editable_package = True
                    else:
                        # TODO: handle multiple source directories?
                        if is_editable_package:
                            source_type = "directory"
                            source_url = paths.pop().as_posix()
        elif cls.is_vcs_package(path, env):
            (
                source_type,
                source_url,
                source_reference,
            ) = cls.get_package_vcs_properties_from_path(
                env.path / "src" / canonicalize_name(distribution.metadata["name"])
            )
        else:
            # If not, it's a path dependency
            source_type = "directory"
            source_url = str(path.parent)

        package = Package(
            distribution.metadata["name"],
            distribution.metadata["version"],
            source_type=source_type,
            source_url=source_url,
            source_reference=source_reference,
            source_resolved_reference=source_resolved_reference,
            source_subdirectory=source_subdirectory,
        )

        package.description = distribution.metadata.get(  # type: ignore[attr-defined]
            "summary",
            "",
        )

        return package

    @classmethod
    def create_package_from_pep610(cls, distribution: metadata.Distribution) -> Package:
        path = Path(str(distribution._path))  # type: ignore[attr-defined]
        source_type = None
        source_url = None
        source_reference = None
        source_resolved_reference = None
        source_subdirectory = None
        develop = False

        url_reference = json.loads(
            path.joinpath("direct_url.json").read_text(encoding="utf-8")
        )
        if "archive_info" in url_reference:
            # File or URL distribution
            if url_reference["url"].startswith("file:"):
                # File distribution
                source_type = "file"
                source_url = url_to_path(url_reference["url"]).as_posix()
            else:
                # URL distribution
                source_type = "url"
                source_url = url_reference["url"]
        elif "dir_info" in url_reference:
            # Directory distribution
            source_type = "directory"
            source_url = url_to_path(url_reference["url"]).as_posix()
            develop = url_reference["dir_info"].get("editable", False)
        elif "vcs_info" in url_reference:
            # VCS distribution
            source_type = url_reference["vcs_info"]["vcs"]
            source_url = url_reference["url"]
            source_resolved_reference = url_reference["vcs_info"]["commit_id"]
            source_reference = url_reference["vcs_info"].get(
                "requested_revision", source_resolved_reference
            )
        source_subdirectory = url_reference.get("subdirectory")

        package = Package(
            distribution.metadata["name"],
            distribution.metadata["version"],
            source_type=source_type,
            source_url=source_url,
            source_reference=source_reference,
            source_resolved_reference=source_resolved_reference,
            source_subdirectory=source_subdirectory,
            develop=develop,
        )

        package.description = distribution.metadata.get(  # type: ignore[attr-defined]
            "summary",
            "",
        )

        return package

    @classmethod
    def load(cls, env: Env, with_dependencies: bool = False) -> InstalledRepository:
        """
        Load installed packages.
        """
        from poetry.core.packages.dependency import Dependency

        repo = cls()
        seen = set()
        skipped = set()

        for entry in reversed(env.sys_path):
            if not entry.strip():
                logger.debug(
                    "Project environment contains an empty path in <c1>sys_path</>,"
                    " ignoring."
                )
                continue

            for distribution in sorted(
                metadata.distributions(path=[entry]),
                key=lambda d: str(d._path),  # type: ignore[attr-defined]
            ):
                path = Path(str(distribution._path))  # type: ignore[attr-defined]

                if path in skipped:
                    continue

                name = distribution.metadata.get("name")  # type: ignore[attr-defined]
                if name is None:
                    logger.warning(
                        (
                            "Project environment contains an invalid distribution"
                            " (<c1>%s</>). Consider removing it manually or recreate"
                            " the environment."
                        ),
                        path,
                    )
                    skipped.add(path)
                    continue

                name = canonicalize_name(name)

                if name in seen:
                    continue

                package = cls.create_package_from_distribution(distribution, env)

                if with_dependencies:
                    for require in distribution.metadata.get_all("requires-dist", []):
                        dep = Dependency.create_from_pep_508(require)
                        package.add_dependency(dep)

                seen.add(package.name)
                repo.add_package(package)

        return repo
