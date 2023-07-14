from __future__ import annotations

import tarfile
import tempfile
import zipfile

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from build import BuildBackendException
from build import ProjectBuilder
from build.env import IsolatedEnv as BaseIsolatedEnv
from poetry.core.utils.helpers import temporary_directory
from pyproject_hooks import quiet_subprocess_runner  # type: ignore[import]

from poetry.utils._compat import decode
from poetry.utils.env import ephemeral_environment


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection
    from contextlib import AbstractContextManager

    from poetry.repositories import RepositoryPool
    from poetry.utils.cache import ArtifactCache
    from poetry.utils.env import Env


class ChefError(Exception):
    ...


class ChefBuildError(ChefError):
    ...


class IsolatedEnv(BaseIsolatedEnv):
    def __init__(self, env: Env, pool: RepositoryPool) -> None:
        self._env = env
        self._pool = pool

    @property
    def executable(self) -> str:
        return str(self._env.python)

    @property
    def scripts_dir(self) -> str:
        return str(self._env._bin_dir)

    def install(self, requirements: Collection[str]) -> None:
        from cleo.io.null_io import NullIO
        from poetry.core.packages.dependency import Dependency
        from poetry.core.packages.project_package import ProjectPackage

        from poetry.config.config import Config
        from poetry.installation.installer import Installer
        from poetry.packages.locker import Locker
        from poetry.repositories.installed_repository import InstalledRepository

        # We build Poetry dependencies from the requirements
        package = ProjectPackage("__root__", "0.0.0")
        package.python_versions = ".".join(str(v) for v in self._env.version_info[:3])
        for requirement in requirements:
            dependency = Dependency.create_from_pep_508(requirement)
            package.add_dependency(dependency)

        installer = Installer(
            NullIO(),
            self._env,
            package,
            Locker(self._env.path.joinpath("poetry.lock"), {}),
            self._pool,
            Config.create(),
            InstalledRepository.load(self._env),
        )
        installer.update(True)
        installer.run()


class Chef:
    def __init__(
        self, artifact_cache: ArtifactCache, env: Env, pool: RepositoryPool
    ) -> None:
        self._env = env
        self._pool = pool
        self._artifact_cache = artifact_cache

    def prepare(
        self, archive: Path, output_dir: Path | None = None, *, editable: bool = False
    ) -> Path:
        if not self._should_prepare(archive):
            return archive

        if archive.is_dir():
            destination = output_dir or Path(tempfile.mkdtemp(prefix="poetry-chef-"))
            return self._prepare(archive, destination=destination, editable=editable)

        return self._prepare_sdist(archive, destination=output_dir)

    def _prepare(
        self, directory: Path, destination: Path, *, editable: bool = False
    ) -> Path:
        from subprocess import CalledProcessError

        with ephemeral_environment(self._env.python) as venv:
            env = IsolatedEnv(venv, self._pool)
            builder = ProjectBuilder(
                directory,
                python_executable=env.executable,
                scripts_dir=env.scripts_dir,
                runner=quiet_subprocess_runner,
            )
            env.install(builder.build_system_requires)

            stdout = StringIO()
            error: Exception | None = None
            try:
                with redirect_stdout(stdout):
                    dist_format = "wheel" if not editable else "editable"
                    env.install(
                        builder.build_system_requires
                        | builder.get_requires_for_build(dist_format)
                    )
                    path = Path(
                        builder.build(
                            dist_format,
                            destination.as_posix(),
                        )
                    )
            except BuildBackendException as e:
                message_parts = [str(e)]
                if isinstance(e.exception, CalledProcessError) and (
                    e.exception.stdout is not None or e.exception.stderr is not None
                ):
                    message_parts.append(
                        decode(e.exception.stderr)
                        if e.exception.stderr is not None
                        else decode(e.exception.stdout)
                    )

                error = ChefBuildError("\n\n".join(message_parts))

            if error is not None:
                raise error from None

            return path

    def _prepare_sdist(self, archive: Path, destination: Path | None = None) -> Path:
        from poetry.core.packages.utils.link import Link

        suffix = archive.suffix
        context: Callable[
            [str], AbstractContextManager[zipfile.ZipFile | tarfile.TarFile]
        ]
        if suffix == ".zip":  # noqa: SIM108
            context = zipfile.ZipFile
        else:
            context = tarfile.open

        with temporary_directory() as tmp_dir:
            with context(archive.as_posix()) as archive_archive:
                archive_archive.extractall(tmp_dir)

            archive_dir = Path(tmp_dir)

            elements = list(archive_dir.glob("*"))

            if len(elements) == 1 and elements[0].is_dir():
                sdist_dir = elements[0]
            else:
                sdist_dir = archive_dir / archive.name.rstrip(suffix)
                if not sdist_dir.is_dir():
                    sdist_dir = archive_dir

            if destination is None:
                destination = self._artifact_cache.get_cache_directory_for_link(
                    Link(archive.as_uri())
                )

            destination.mkdir(parents=True, exist_ok=True)

            return self._prepare(
                sdist_dir,
                destination,
            )

    def _should_prepare(self, archive: Path) -> bool:
        return archive.is_dir() or not self._is_wheel(archive)

    @classmethod
    def _is_wheel(cls, archive: Path) -> bool:
        return archive.suffix == ".whl"
