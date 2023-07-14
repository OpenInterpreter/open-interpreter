from __future__ import annotations

import logging
import os
import re
import tarfile

from collections import defaultdict
from contextlib import contextmanager
from copy import copy
from gzip import GzipFile
from io import BytesIO
from pathlib import Path
from posixpath import join as pjoin
from pprint import pformat
from typing import TYPE_CHECKING

from poetry.core.masonry.builders.builder import Builder
from poetry.core.masonry.builders.builder import BuildIncludeFile
from poetry.core.masonry.utils.helpers import distribution_name


if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from tarfile import TarInfo

    from poetry.core.masonry.utils.package_include import PackageInclude
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.project_package import ProjectPackage

SETUP = """\
# -*- coding: utf-8 -*-
from setuptools import setup

{before}
setup_kwargs = {{
    'name': {name!r},
    'version': {version!r},
    'description': {description!r},
    'long_description': {long_description!r},
    'author': {author!r},
    'author_email': {author_email!r},
    'maintainer': {maintainer!r},
    'maintainer_email': {maintainer_email!r},
    'url': {url!r},
    {extra}
}}
{after}

setup(**setup_kwargs)
"""

logger = logging.getLogger(__name__)


class SdistBuilder(Builder):
    format = "sdist"

    def build(
        self,
        target_dir: Path | None = None,
    ) -> Path:
        logger.info("Building <info>sdist</info>")
        target_dir = target_dir or self.default_target_dir

        if not target_dir.exists():
            target_dir.mkdir(parents=True)

        name = distribution_name(self._package.name)
        target = target_dir / f"{name}-{self._meta.version}.tar.gz"
        gz = GzipFile(target.as_posix(), mode="wb", mtime=0)
        tar = tarfile.TarFile(
            target.as_posix(), mode="w", fileobj=gz, format=tarfile.PAX_FORMAT
        )

        try:
            tar_dir = f"{name}-{self._meta.version}"

            files_to_add = self.find_files_to_add(exclude_build=False)

            for file in sorted(files_to_add, key=lambda x: x.relative_to_source_root()):
                tar_info = tar.gettarinfo(
                    str(file.path),
                    arcname=pjoin(tar_dir, str(file.relative_to_source_root())),
                )
                tar_info = self.clean_tarinfo(tar_info)

                if tar_info.isreg():
                    with file.path.open("rb") as f:
                        tar.addfile(tar_info, f)
                else:
                    tar.addfile(tar_info)  # Symlinks & ?

            if self._poetry.package.build_should_generate_setup():
                setup = self.build_setup()
                tar_info = tarfile.TarInfo(pjoin(tar_dir, "setup.py"))
                tar_info.size = len(setup)
                tar_info.mtime = 0
                tar_info = self.clean_tarinfo(tar_info)
                tar.addfile(tar_info, BytesIO(setup))

            pkg_info = self.build_pkg_info()

            tar_info = tarfile.TarInfo(pjoin(tar_dir, "PKG-INFO"))
            tar_info.size = len(pkg_info)
            tar_info.mtime = 0
            tar_info = self.clean_tarinfo(tar_info)
            tar.addfile(tar_info, BytesIO(pkg_info))
        finally:
            tar.close()
            gz.close()

        logger.info(f"Built <comment>{target.name}</comment>")
        return target

    def build_setup(self) -> bytes:
        from poetry.core.masonry.utils.package_include import PackageInclude

        before, extra, after = [], [], []
        package_dir: dict[str, str] = {}

        # If we have a build script, use it
        if self._package.build_script:
            import_name = ".".join(
                Path(self._package.build_script).with_suffix("").parts
            )
            after += [f"from {import_name} import *", "build(setup_kwargs)"]

        modules = []
        packages = []
        package_data = {}
        for include in self._module.includes:
            if include.formats and "sdist" not in include.formats:
                continue

            if isinstance(include, PackageInclude):
                if include.is_package():
                    pkg_dir, _packages, _package_data = self.find_packages(include)

                    if pkg_dir is not None:
                        pkg_root = os.path.relpath(pkg_dir, str(self._path))
                        if "" in package_dir:
                            package_dir.update(
                                (p, os.path.join(pkg_root, p.replace(".", "/")))
                                for p in _packages
                            )
                        else:
                            package_dir[""] = pkg_root

                    packages += [p for p in _packages if p not in packages]
                    package_data.update(_package_data)
                else:
                    module = include.elements[0].relative_to(include.base).stem

                    if include.source is not None:
                        package_dir[""] = str(include.base.relative_to(self._path))

                    if module not in modules:
                        modules.append(module)
            else:
                pass

        if package_dir:
            before.append(f"package_dir = \\\n{pformat(package_dir)}\n")
            extra.append("'package_dir': package_dir,")

        if packages:
            before.append(f"packages = \\\n{pformat(sorted(packages))}\n")
            extra.append("'packages': packages,")

        if package_data:
            before.append(f"package_data = \\\n{pformat(package_data)}\n")
            extra.append("'package_data': package_data,")

        if modules:
            before.append(f"modules = \\\n{pformat(modules)}")
            extra.append("'py_modules': modules,")

        dependencies, extras = self.convert_dependencies(
            self._package, self._package.requires
        )
        if dependencies:
            before.append(f"install_requires = \\\n{pformat(sorted(dependencies))}\n")
            extra.append("'install_requires': install_requires,")

        if extras:
            before.append(f"extras_require = \\\n{pformat(extras)}\n")
            extra.append("'extras_require': extras_require,")

        entry_points = self.convert_entry_points()
        if entry_points:
            before.append(f"entry_points = \\\n{pformat(entry_points)}\n")
            extra.append("'entry_points': entry_points,")

        script_files = self.convert_script_files()
        if script_files:
            rel_paths = [str(p.relative_to(self._path)) for p in script_files]
            before.append(f"scripts = \\\n{pformat(rel_paths)}\n")
            extra.append("'scripts': scripts,")

        if self._package.python_versions != "*":
            python_requires = self._meta.requires_python

            extra.append(f"'python_requires': {python_requires!r},")

        return SETUP.format(
            before="\n".join(before),
            name=str(self._meta.name),
            version=self._meta.version,
            description=str(self._meta.summary),
            long_description=str(self._meta.description),
            author=str(self._meta.author),
            author_email=str(self._meta.author_email),
            maintainer=str(self._meta.maintainer),
            maintainer_email=str(self._meta.maintainer_email),
            url=str(self._meta.home_page),
            extra="\n    ".join(extra),
            after="\n".join(after),
        ).encode()

    @contextmanager
    def setup_py(self) -> Iterator[Path]:
        setup = self._path / "setup.py"
        has_setup = setup.exists()

        if has_setup:
            logger.warning("A setup.py file already exists. Using it.")
        else:
            with setup.open("w", encoding="utf-8") as f:
                f.write(self.build_setup().decode())

        yield setup

        if not has_setup:
            setup.unlink()

    def build_pkg_info(self) -> bytes:
        return self.get_metadata_content().encode()

    def find_packages(
        self, include: PackageInclude
    ) -> tuple[str | None, list[str], dict[str, list[str]]]:
        """
        Discover subpackages and data.

        It also retrieves necessary files.
        """
        pkgdir = None
        if include.source is not None:
            pkgdir = str(include.base)

        base = str(include.elements[0].parent)

        pkg_name = include.package
        pkg_data: dict[str, list[str]] = defaultdict(list)
        # Undocumented setup() feature:
        # the empty string matches all package names
        pkg_data[""].append("*")
        packages = [pkg_name]
        subpkg_paths = set()

        def find_nearest_pkg(rel_path: str) -> tuple[str, str]:
            parts = rel_path.split(os.sep)
            for i in reversed(range(1, len(parts))):
                ancestor = "/".join(parts[:i])
                if ancestor in subpkg_paths:
                    pkg = ".".join([pkg_name] + parts[:i])
                    return pkg, "/".join(parts[i:])

            # Relative to the top-level package
            return pkg_name, Path(rel_path).as_posix()

        for path, _dirnames, filenames in os.walk(str(base), topdown=True):
            if os.path.basename(path) == "__pycache__":
                continue

            from_top_level = os.path.relpath(path, base)
            if from_top_level == ".":
                continue

            is_subpkg = any(
                filename.endswith(".py") for filename in filenames
            ) and not all(
                self.is_excluded(Path(path, filename).relative_to(self._path))
                for filename in filenames
                if filename.endswith(".py")
            )
            if is_subpkg:
                subpkg_paths.add(from_top_level)
                parts = from_top_level.split(os.sep)
                packages.append(".".join([pkg_name, *parts]))
            else:
                pkg, from_nearest_pkg = find_nearest_pkg(from_top_level)

                data_elements = [
                    f.relative_to(self._path)
                    for f in Path(path).glob("*")
                    if not f.is_dir()
                ]

                data = [e for e in data_elements if not self.is_excluded(e)]
                if not data:
                    continue

                if len(data) == len(data_elements):
                    pkg_data[pkg].append(pjoin(from_nearest_pkg, "*"))
                else:
                    for d in data:
                        if d.is_dir():
                            continue

                        pkg_data[pkg] += [pjoin(from_nearest_pkg, d.name) for d in data]

        # Sort values in pkg_data
        pkg_data = {k: sorted(v) for (k, v) in pkg_data.items() if v}

        return pkgdir, sorted(packages), pkg_data

    def find_files_to_add(self, exclude_build: bool = False) -> set[BuildIncludeFile]:
        to_add = super().find_files_to_add(exclude_build)

        # add any additional files, starting with all LICENSE files
        additional_files: set[Path] = set(self._path.glob("LICENSE*"))

        # add script files
        additional_files.update(self.convert_script_files())

        # Include project files
        additional_files.add(Path("pyproject.toml"))

        # add readme files if specified
        if "readme" in self._poetry.local_config:
            readme: str | Iterable[str] = self._poetry.local_config["readme"]
            if isinstance(readme, str):
                additional_files.add(Path(readme))
            else:
                additional_files.update(Path(r) for r in readme)

        for additional_file in additional_files:
            file = BuildIncludeFile(
                path=additional_file, project_root=self._path, source_root=self._path
            )
            if file.path.exists():
                logger.debug(f"Adding: {file.relative_to_source_root()}")
                to_add.add(file)

        return to_add

    @classmethod
    def convert_dependencies(
        cls, package: ProjectPackage, dependencies: list[Dependency]
    ) -> tuple[list[str], dict[str, list[str]]]:
        main = []
        extras = defaultdict(list)
        req_regex = re.compile(r"^(.+) \((.+)\)$")

        for dependency in dependencies:
            if dependency.is_optional():
                for extra_name, reqs in package.extras.items():
                    for req in reqs:
                        if req.name == dependency.name:
                            requirement = dependency.to_pep_508(with_extras=False)
                            if ";" in requirement:
                                requirement, conditions = requirement.split(";")

                                requirement = requirement.strip()
                                if req_regex.match(requirement):
                                    requirement = req_regex.sub(
                                        "\\1\\2", requirement.strip()
                                    )

                                extras[extra_name + ":" + conditions.strip()].append(
                                    requirement
                                )

                                continue

                            requirement = requirement.strip()
                            if req_regex.match(requirement):
                                requirement = req_regex.sub(
                                    "\\1\\2", requirement.strip()
                                )
                            extras[extra_name].append(requirement)
                continue

            requirement = dependency.to_pep_508()
            if ";" in requirement:
                requirement, conditions = requirement.split(";")

                requirement = requirement.strip()
                if req_regex.match(requirement):
                    requirement = req_regex.sub("\\1\\2", requirement.strip())

                extras[":" + conditions.strip()].append(requirement)

                continue

            requirement = requirement.strip()
            if req_regex.match(requirement):
                requirement = req_regex.sub("\\1\\2", requirement.strip())

            main.append(requirement)

        return main, dict(extras)

    @classmethod
    def clean_tarinfo(cls, tar_info: TarInfo) -> TarInfo:
        """
        Clean metadata from a TarInfo object to make it more reproducible.

            - Set uid & gid to 0
            - Set uname and gname to ""
            - Normalise permissions to 644 or 755
            - Set mtime if not None
        """
        from poetry.core.masonry.utils.helpers import normalize_file_permissions

        ti = copy(tar_info)
        ti.uid = 0
        ti.gid = 0
        ti.uname = ""
        ti.gname = ""
        ti.mode = normalize_file_permissions(ti.mode)

        return ti
