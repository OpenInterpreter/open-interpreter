from __future__ import annotations

import contextlib
import functools
import glob
import logging
import os
import tarfile
import zipfile

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pkginfo

from poetry.core.factory import Factory
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.package import Package
from poetry.core.utils.helpers import parse_requires
from poetry.core.utils.helpers import temporary_directory
from poetry.core.version.markers import InvalidMarker
from poetry.core.version.requirements import InvalidRequirement

from poetry.pyproject.toml import PyProjectTOML
from poetry.utils.env import EnvCommandError
from poetry.utils.env import ephemeral_environment
from poetry.utils.setup_reader import SetupReader


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from contextlib import AbstractContextManager

    from poetry.core.packages.project_package import ProjectPackage


logger = logging.getLogger(__name__)

PEP517_META_BUILD = """\
import build
import build.env
import pyproject_hooks

source = '{source}'
dest = '{dest}'

with build.env.IsolatedEnvBuilder() as env:
    builder = build.ProjectBuilder(
        srcdir=source,
        scripts_dir=env.scripts_dir,
        python_executable=env.executable,
        runner=pyproject_hooks.quiet_subprocess_runner,
    )
    env.install(builder.build_system_requires)
    env.install(builder.get_requires_for_build('wheel'))
    builder.metadata_path(dest)
"""

PEP517_META_BUILD_DEPS = ["build==0.10.0", "pyproject_hooks==1.0.0"]


class PackageInfoError(ValueError):
    def __init__(self, path: Path, *reasons: BaseException | str) -> None:
        reasons = (f"Unable to determine package info for path: {path!s}", *reasons)
        super().__init__("\n\n".join(str(msg).strip() for msg in reasons if msg))


class PackageInfo:
    def __init__(
        self,
        *,
        name: str | None = None,
        version: str | None = None,
        summary: str | None = None,
        requires_dist: list[str] | None = None,
        requires_python: str | None = None,
        files: list[dict[str, str]] | None = None,
        yanked: str | bool = False,
        cache_version: str | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.summary = summary
        self.requires_dist = requires_dist
        self.requires_python = requires_python
        self.files = files or []
        self.yanked = yanked
        self._cache_version = cache_version
        self._source_type: str | None = None
        self._source_url: str | None = None
        self._source_reference: str | None = None

    @property
    def cache_version(self) -> str | None:
        return self._cache_version

    def update(self, other: PackageInfo) -> PackageInfo:
        self.name = other.name or self.name
        self.version = other.version or self.version
        self.summary = other.summary or self.summary
        self.requires_dist = other.requires_dist or self.requires_dist
        self.requires_python = other.requires_python or self.requires_python
        self.files = other.files or self.files
        self._cache_version = other.cache_version or self._cache_version
        return self

    def asdict(self) -> dict[str, Any]:
        """
        Helper method to convert package info into a dictionary used for caching.
        """
        return {
            "name": self.name,
            "version": self.version,
            "summary": self.summary,
            "requires_dist": self.requires_dist,
            "requires_python": self.requires_python,
            "files": self.files,
            "yanked": self.yanked,
            "_cache_version": self._cache_version,
        }

    @classmethod
    def load(cls, data: dict[str, Any]) -> PackageInfo:
        """
        Helper method to load data from a dictionary produced by `PackageInfo.asdict()`.

        :param data: Data to load. This is expected to be a `dict` object output by
            `asdict()`.
        """
        cache_version = data.pop("_cache_version", None)
        return cls(cache_version=cache_version, **data)

    def to_package(
        self,
        name: str | None = None,
        extras: list[str] | None = None,
        root_dir: Path | None = None,
    ) -> Package:
        """
        Create a new `poetry.core.packages.package.Package` instance using metadata from
        this instance.

        :param name: Name to use for the package, if not specified name from this
            instance is used.
        :param extras: Extras to activate for this package.
        :param root_dir:  Optional root directory to use for the package. If set,
            dependency strings will be parsed relative to this directory.
        """
        name = name or self.name

        if not name:
            raise RuntimeError("Unable to create package with no name")

        if not self.version:
            # The version could not be determined, so we raise an error since it is
            # mandatory.
            raise RuntimeError(f"Unable to retrieve the package version for {name}")

        package = Package(
            name=name,
            version=self.version,
            source_type=self._source_type,
            source_url=self._source_url,
            source_reference=self._source_reference,
            yanked=self.yanked,
        )
        if self.summary is not None:
            package.description = self.summary
        package.root_dir = root_dir
        package.python_versions = self.requires_python or "*"
        package.files = self.files

        # If this is a local poetry project, we can extract "richer" requirement
        # information, eg: development requirements etc.
        if root_dir is not None:
            path = root_dir
        elif self._source_type == "directory" and self._source_url is not None:
            path = Path(self._source_url)
        else:
            path = None

        if path is not None:
            poetry_package = self._get_poetry_package(path=path)
            if poetry_package:
                package.extras = poetry_package.extras
                for dependency in poetry_package.requires:
                    package.add_dependency(dependency)

                return package

        seen_requirements = set()

        for req in self.requires_dist or []:
            try:
                # Attempt to parse the PEP-508 requirement string
                dependency = Dependency.create_from_pep_508(req, relative_to=root_dir)
            except InvalidMarker:
                # Invalid marker, We strip the markers hoping for the best
                logger.warning(
                    "Stripping invalid marker (%s) found in %s-%s dependencies",
                    req,
                    package.name,
                    package.version,
                )
                req = req.split(";")[0]
                dependency = Dependency.create_from_pep_508(req, relative_to=root_dir)
            except InvalidRequirement:
                # Unable to parse requirement so we skip it
                logger.warning(
                    "Invalid requirement (%s) found in %s-%s dependencies, skipping",
                    req,
                    package.name,
                    package.version,
                )
                continue

            if dependency.in_extras:
                # this dependency is required by an extra package
                for extra in dependency.in_extras:
                    if extra not in package.extras:
                        # this is the first time we encounter this extra for this
                        # package
                        package.extras[extra] = []

                    package.extras[extra].append(dependency)

            req = dependency.to_pep_508(with_extras=True)

            if req not in seen_requirements:
                package.add_dependency(dependency)
                seen_requirements.add(req)

        return package

    @classmethod
    def _from_distribution(
        cls, dist: pkginfo.BDist | pkginfo.SDist | pkginfo.Wheel
    ) -> PackageInfo:
        """
        Helper method to parse package information from a `pkginfo.Distribution`
        instance.

        :param dist: The distribution instance to parse information from.
        """
        requirements = None

        if dist.requires_dist:
            requirements = list(dist.requires_dist)
        else:
            requires = Path(dist.filename) / "requires.txt"
            if requires.exists():
                with requires.open(encoding="utf-8") as f:
                    requirements = parse_requires(f.read())

        info = cls(
            name=dist.name,
            version=dist.version,
            summary=dist.summary,
            requires_dist=requirements,
            requires_python=dist.requires_python,
        )

        info._source_type = "file"
        info._source_url = Path(dist.filename).resolve().as_posix()

        return info

    @classmethod
    def _from_sdist_file(cls, path: Path) -> PackageInfo:
        """
        Helper method to parse package information from an sdist file. We attempt to
        first inspect the file using `pkginfo.SDist`. If this does not provide us with
        package requirements, we extract the source and handle it as a directory.

        :param path: The sdist file to parse information from.
        """
        info = None

        try:
            info = cls._from_distribution(pkginfo.SDist(str(path)))
        except ValueError:
            # Unable to determine dependencies
            # We pass and go deeper
            pass
        else:
            if info.requires_dist is not None:
                # we successfully retrieved dependencies from sdist metadata
                return info

        # Still not dependencies found
        # So, we unpack and introspect
        suffix = path.suffix

        context: Callable[
            [str], AbstractContextManager[zipfile.ZipFile | tarfile.TarFile]
        ]
        if suffix == ".zip":
            context = zipfile.ZipFile
        else:
            if suffix == ".bz2":
                suffixes = path.suffixes
                if len(suffixes) > 1 and suffixes[-2] == ".tar":
                    suffix = ".tar.bz2"
            else:
                suffix = ".tar.gz"

            context = tarfile.open

        with temporary_directory() as tmp_str:
            tmp = Path(tmp_str)
            with context(path.as_posix()) as archive:
                archive.extractall(tmp.as_posix())

            # a little bit of guess work to determine the directory we care about
            elements = list(tmp.glob("*"))

            if len(elements) == 1 and elements[0].is_dir():
                sdist_dir = elements[0]
            else:
                sdist_dir = tmp / path.name.rstrip(suffix)
                if not sdist_dir.is_dir():
                    sdist_dir = tmp

            # now this is an unpacked directory we know how to deal with
            new_info = cls.from_directory(path=sdist_dir)

        if not info:
            return new_info

        return info.update(new_info)

    @staticmethod
    def has_setup_files(path: Path) -> bool:
        return any((path / f).exists() for f in SetupReader.FILES)

    @classmethod
    def from_setup_files(cls, path: Path) -> PackageInfo:
        """
        Mechanism to parse package information from a `setup.[py|cfg]` file. This uses
        the implementation at `poetry.utils.setup_reader.SetupReader` in order to parse
        the file. This is not reliable for complex setup files and should only attempted
        as a fallback.

        :param path: Path to `setup.py` file
        """
        if not cls.has_setup_files(path):
            raise PackageInfoError(
                path, "No setup files (setup.py, setup.cfg) was found."
            )

        try:
            result = SetupReader.read_from_directory(path)
        except Exception as e:
            raise PackageInfoError(path, e)

        python_requires = result["python_requires"]
        if python_requires is None:
            python_requires = "*"

        requires = "".join(dep + "\n" for dep in result["install_requires"])
        if result["extras_require"]:
            requires += "\n"

        for extra_name, deps in result["extras_require"].items():
            requires += f"[{extra_name}]\n"

            for dep in deps:
                requires += dep + "\n"

            requires += "\n"

        requirements = parse_requires(requires)

        info = cls(
            name=result.get("name"),
            version=result.get("version"),
            summary=result.get("description", ""),
            requires_dist=requirements or None,
            requires_python=python_requires,
        )

        if not (info.name and info.version) and not info.requires_dist:
            # there is nothing useful here
            raise PackageInfoError(
                path,
                "No core metadata (name, version, requires-dist) could be retrieved.",
            )

        return info

    @staticmethod
    def _find_dist_info(path: Path) -> Iterator[Path]:
        """
        Discover all `*.*-info` directories in a given path.

        :param path: Path to search.
        """
        pattern = "**/*.*-info"
        # Sometimes pathlib will fail on recursive symbolic links, so we need to work
        # around it and use the glob module instead. Note that this does not happen with
        # pathlib2 so it's safe to use it for Python < 3.4.
        directories = glob.iglob(path.joinpath(pattern).as_posix(), recursive=True)

        for d in directories:
            yield Path(d)

    @classmethod
    def from_metadata(cls, path: Path) -> PackageInfo | None:
        """
        Helper method to parse package information from an unpacked metadata directory.

        :param path: The metadata directory to parse information from.
        """
        if path.suffix in {".dist-info", ".egg-info"}:
            directories = [path]
        else:
            directories = list(cls._find_dist_info(path=path))

        dist: pkginfo.BDist | pkginfo.SDist | pkginfo.Wheel
        for directory in directories:
            try:
                if directory.suffix == ".egg-info":
                    dist = pkginfo.UnpackedSDist(directory.as_posix())
                elif directory.suffix == ".dist-info":
                    dist = pkginfo.Wheel(directory.as_posix())
                else:
                    continue
                break
            except ValueError:
                continue
        else:
            try:
                # handle PKG-INFO in unpacked sdist root
                dist = pkginfo.UnpackedSDist(path.as_posix())
            except ValueError:
                return None

        return cls._from_distribution(dist=dist)

    @classmethod
    def from_package(cls, package: Package) -> PackageInfo:
        """
        Helper method to inspect a `Package` object, in order to generate package info.

        :param package: This must be a poetry package instance.
        """
        requires = {dependency.to_pep_508() for dependency in package.requires}

        for extra_requires in package.extras.values():
            for dependency in extra_requires:
                requires.add(dependency.to_pep_508())

        return cls(
            name=package.name,
            version=str(package.version),
            summary=package.description,
            requires_dist=list(requires),
            requires_python=package.python_versions,
            files=package.files,
            yanked=package.yanked_reason if package.yanked else False,
        )

    @staticmethod
    def _get_poetry_package(path: Path) -> ProjectPackage | None:
        # Note: we ignore any setup.py file at this step
        # TODO: add support for handling non-poetry PEP-517 builds
        if PyProjectTOML(path.joinpath("pyproject.toml")).is_poetry_project():
            with contextlib.suppress(RuntimeError):
                return Factory().create_poetry(path).package

        return None

    @classmethod
    def from_directory(cls, path: Path, disable_build: bool = False) -> PackageInfo:
        """
        Generate package information from a package source directory. If `disable_build`
        is not `True` and introspection of all available metadata fails, the package is
        attempted to be built in an isolated environment so as to generate required
        metadata.

        :param path: Path to generate package information from.
        :param disable_build: If not `True` and setup reader fails, PEP 517 isolated
            build is attempted in order to gather metadata.
        """
        project_package = cls._get_poetry_package(path)
        info: PackageInfo | None
        if project_package:
            info = cls.from_package(project_package)
        else:
            info = cls.from_metadata(path)

            if not info or info.requires_dist is None:
                try:
                    if disable_build:
                        info = cls.from_setup_files(path)
                    else:
                        info = get_pep517_metadata(path)
                except PackageInfoError:
                    if not info:
                        raise

                    # we discovered PkgInfo but no requirements were listed

        info._source_type = "directory"
        info._source_url = path.as_posix()

        return info

    @classmethod
    def from_sdist(cls, path: Path) -> PackageInfo:
        """
        Gather package information from an sdist file, packed or unpacked.

        :param path: Path to an sdist file or unpacked directory.
        """
        if path.is_file():
            return cls._from_sdist_file(path=path)

        # if we get here then it is neither an sdist instance nor a file
        # so, we assume this is an directory
        return cls.from_directory(path=path)

    @classmethod
    def from_wheel(cls, path: Path) -> PackageInfo:
        """
        Gather package information from a wheel.

        :param path: Path to wheel.
        """
        try:
            return cls._from_distribution(pkginfo.Wheel(str(path)))
        except ValueError:
            return PackageInfo()

    @classmethod
    def from_bdist(cls, path: Path) -> PackageInfo:
        """
        Gather package information from a bdist (wheel etc.).

        :param path: Path to bdist.
        """
        if isinstance(path, (pkginfo.BDist, pkginfo.Wheel)):
            cls._from_distribution(dist=path)

        if path.suffix == ".whl":
            return cls.from_wheel(path=path)

        try:
            return cls._from_distribution(pkginfo.BDist(str(path)))
        except ValueError as e:
            raise PackageInfoError(path, e)

    @classmethod
    def from_path(cls, path: Path) -> PackageInfo:
        """
        Gather package information from a given path (bdist, sdist, directory).

        :param path: Path to inspect.
        """
        try:
            return cls.from_bdist(path=path)
        except PackageInfoError:
            return cls.from_sdist(path=path)


@functools.lru_cache(maxsize=None)
def get_pep517_metadata(path: Path) -> PackageInfo:
    """
    Helper method to use PEP-517 library to build and read package metadata.

    :param path: Path to package source to build and read metadata for.
    """
    info = None

    with contextlib.suppress(PackageInfoError):
        info = PackageInfo.from_setup_files(path)
        if all([info.version, info.name, info.requires_dist]):
            return info

    with ephemeral_environment(
        flags={"no-pip": False, "no-setuptools": False, "no-wheel": False}
    ) as venv:
        # TODO: cache PEP 517 build environment corresponding to each project venv
        dest_dir = venv.path.parent / "dist"
        dest_dir.mkdir()

        pep517_meta_build_script = PEP517_META_BUILD.format(
            source=path.as_posix(), dest=dest_dir.as_posix()
        )

        try:
            venv.run_pip(
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--no-input",
                *PEP517_META_BUILD_DEPS,
            )
            venv.run(
                "python",
                "-",
                input_=pep517_meta_build_script,
            )
            info = PackageInfo.from_metadata(dest_dir)
        except EnvCommandError as e:
            # something went wrong while attempting pep517 metadata build
            # fallback to egg_info if setup.py available
            logger.debug("PEP517 build failed: %s", e)
            setup_py = path / "setup.py"
            if not setup_py.exists():
                raise PackageInfoError(
                    path,
                    e,
                    "No fallback setup.py file was found to generate egg_info.",
                )

            cwd = Path.cwd()
            os.chdir(path)
            try:
                venv.run("python", "setup.py", "egg_info")
                info = PackageInfo.from_metadata(path)
            except EnvCommandError as fbe:
                raise PackageInfoError(
                    path, e, "Fallback egg_info generation failed.", fbe
                )
            finally:
                os.chdir(cwd)

    if info:
        logger.debug("Falling back to parsed setup.py file for %s", path)
        return info

    # if we reach here, everything has failed and all hope is lost
    raise PackageInfoError(path, "Exhausted all core metadata sources.")
