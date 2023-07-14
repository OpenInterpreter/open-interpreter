from __future__ import annotations

import base64
import contextlib
import hashlib
import itertools
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import sysconfig

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING
from typing import Any

import packaging.tags
import tomlkit
import virtualenv

from cleo.io.null_io import NullIO
from cleo.io.outputs.output import Verbosity
from packaging.tags import Tag
from packaging.tags import interpreter_name
from packaging.tags import interpreter_version
from packaging.tags import sys_tags
from poetry.core.constraints.version import Version
from poetry.core.constraints.version import parse_constraint
from poetry.core.utils.helpers import temporary_directory
from virtualenv.seed.wheels.embed import get_embed_wheel

from poetry.toml.file import TOMLFile
from poetry.utils._compat import WINDOWS
from poetry.utils._compat import decode
from poetry.utils._compat import encode
from poetry.utils._compat import metadata
from poetry.utils.helpers import get_real_windows_path
from poetry.utils.helpers import is_dir_writable
from poetry.utils.helpers import paths_csv
from poetry.utils.helpers import remove_directory


if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from cleo.io.io import IO
    from poetry.core.poetry import Poetry as CorePoetry
    from poetry.core.version.markers import BaseMarker
    from virtualenv.seed.wheels.util import Wheel

    from poetry.poetry import Poetry

GET_SYS_TAGS = f"""
import importlib.util
import json
import sys

from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "packaging", Path(r"{packaging.__file__}")
)
packaging = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = packaging

spec = importlib.util.spec_from_file_location(
    "packaging.tags", Path(r"{packaging.tags.__file__}")
)
packaging_tags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging_tags)

print(
    json.dumps([(t.interpreter, t.abi, t.platform) for t in packaging_tags.sys_tags()])
)
"""

GET_ENVIRONMENT_INFO = """\
import json
import os
import platform
import sys
import sysconfig

INTERPRETER_SHORT_NAMES = {
    "python": "py",
    "cpython": "cp",
    "pypy": "pp",
    "ironpython": "ip",
    "jython": "jy",
}


def interpreter_version():
    version = sysconfig.get_config_var("interpreter_version")
    if version:
        version = str(version)
    else:
        version = _version_nodot(sys.version_info[:2])

    return version


def _version_nodot(version):
    if any(v >= 10 for v in version):
        sep = "_"
    else:
        sep = ""

    return sep.join(map(str, version))


if hasattr(sys, "implementation"):
    info = sys.implementation.version
    iver = "{0.major}.{0.minor}.{0.micro}".format(info)
    kind = info.releaselevel
    if kind != "final":
        iver += kind[0] + str(info.serial)

    implementation_name = sys.implementation.name
else:
    iver = "0"
    implementation_name = platform.python_implementation().lower()

env = {
    "implementation_name": implementation_name,
    "implementation_version": iver,
    "os_name": os.name,
    "platform_machine": platform.machine(),
    "platform_release": platform.release(),
    "platform_system": platform.system(),
    "platform_version": platform.version(),
    "python_full_version": platform.python_version(),
    "platform_python_implementation": platform.python_implementation(),
    "python_version": ".".join(platform.python_version_tuple()[:2]),
    "sys_platform": sys.platform,
    "version_info": tuple(sys.version_info),
    # Extra information
    "interpreter_name": INTERPRETER_SHORT_NAMES.get(
        implementation_name, implementation_name
    ),
    "interpreter_version": interpreter_version(),
}

print(json.dumps(env))
"""

GET_BASE_PREFIX = """\
import sys

if hasattr(sys, "real_prefix"):
    print(sys.real_prefix)
elif hasattr(sys, "base_prefix"):
    print(sys.base_prefix)
else:
    print(sys.prefix)
"""

GET_PYTHON_VERSION = """\
import sys

print('.'.join([str(s) for s in sys.version_info[:3]]))
"""

GET_PYTHON_VERSION_ONELINER = (
    "import sys; print('.'.join([str(s) for s in sys.version_info[:3]]))"
)
GET_ENV_PATH_ONELINER = "import sys; print(sys.prefix)"

GET_SYS_PATH = """\
import json
import sys

print(json.dumps(sys.path))
"""

GET_PATHS = """\
import json
import sysconfig

print(json.dumps(sysconfig.get_paths()))
"""

GET_PATHS_FOR_GENERIC_ENVS = """\
import json
import site
import sysconfig

paths = sysconfig.get_paths().copy()

if site.check_enableusersite():
    paths["usersite"] = site.getusersitepackages()
    paths["userbase"] = site.getuserbase()

print(json.dumps(paths))
"""


class SitePackages:
    def __init__(
        self,
        purelib: Path,
        platlib: Path | None = None,
        fallbacks: list[Path] | None = None,
        skip_write_checks: bool = False,
    ) -> None:
        self._purelib = purelib
        self._platlib = platlib or purelib

        if platlib and platlib.resolve() == purelib.resolve():
            self._platlib = purelib

        self._fallbacks = fallbacks or []
        self._skip_write_checks = skip_write_checks

        self._candidates: list[Path] = []
        for path in itertools.chain([self._purelib, self._platlib], self._fallbacks):
            if path not in self._candidates:
                self._candidates.append(path)

        self._writable_candidates = None if not skip_write_checks else self._candidates

    @property
    def path(self) -> Path:
        return self._purelib

    @property
    def purelib(self) -> Path:
        return self._purelib

    @property
    def platlib(self) -> Path:
        return self._platlib

    @property
    def candidates(self) -> list[Path]:
        return self._candidates

    @property
    def writable_candidates(self) -> list[Path]:
        if self._writable_candidates is not None:
            return self._writable_candidates

        self._writable_candidates = []
        for candidate in self._candidates:
            if not is_dir_writable(path=candidate, create=True):
                continue
            self._writable_candidates.append(candidate)

        return self._writable_candidates

    def make_candidates(
        self, path: Path, writable_only: bool = False, strict: bool = False
    ) -> list[Path]:
        candidates = self._candidates if not writable_only else self.writable_candidates
        if path.is_absolute():
            for candidate in candidates:
                with contextlib.suppress(ValueError):
                    path.relative_to(candidate)
                    return [path]
            site_type = "writable " if writable_only else ""
            raise ValueError(
                f"{path} is not relative to any discovered {site_type}sites"
            )

        results = [candidate / path for candidate in candidates]

        if not results and strict:
            raise RuntimeError(
                f'Unable to find a suitable destination for "{path}" in'
                f" {paths_csv(self._candidates)}"
            )

        return results

    def distributions(
        self, name: str | None = None, writable_only: bool = False
    ) -> Iterable[metadata.Distribution]:
        path = list(
            map(
                str, self._candidates if not writable_only else self.writable_candidates
            )
        )

        yield from metadata.PathDistribution.discover(name=name, path=path)

    def find_distribution(
        self, name: str, writable_only: bool = False
    ) -> metadata.Distribution | None:
        for distribution in self.distributions(name=name, writable_only=writable_only):
            return distribution
        return None

    def find_distribution_files_with_suffix(
        self, distribution_name: str, suffix: str, writable_only: bool = False
    ) -> Iterable[Path]:
        for distribution in self.distributions(
            name=distribution_name, writable_only=writable_only
        ):
            files = [] if distribution.files is None else distribution.files
            for file in files:
                if file.name.endswith(suffix):
                    yield Path(distribution.locate_file(file))

    def find_distribution_files_with_name(
        self, distribution_name: str, name: str, writable_only: bool = False
    ) -> Iterable[Path]:
        for distribution in self.distributions(
            name=distribution_name, writable_only=writable_only
        ):
            files = [] if distribution.files is None else distribution.files
            for file in files:
                if file.name == name:
                    yield Path(distribution.locate_file(file))

    def find_distribution_direct_url_json_files(
        self, distribution_name: str, writable_only: bool = False
    ) -> Iterable[Path]:
        return self.find_distribution_files_with_name(
            distribution_name=distribution_name,
            name="direct_url.json",
            writable_only=writable_only,
        )

    def remove_distribution_files(self, distribution_name: str) -> list[Path]:
        paths = []

        for distribution in self.distributions(
            name=distribution_name, writable_only=True
        ):
            files = [] if distribution.files is None else distribution.files
            for file in files:
                path = Path(distribution.locate_file(file))

                # We can't use unlink(missing_ok=True) because it's not always available
                if path.exists():
                    path.unlink()

            distribution_path: Path = distribution._path  # type: ignore[attr-defined]
            if distribution_path.exists():
                remove_directory(distribution_path, force=True)

            paths.append(distribution_path)

        return paths

    def _path_method_wrapper(
        self,
        path: Path,
        method: str,
        *args: Any,
        return_first: bool = True,
        writable_only: bool = False,
        **kwargs: Any,
    ) -> tuple[Path, Any] | list[tuple[Path, Any]]:
        candidates = self.make_candidates(
            path, writable_only=writable_only, strict=True
        )

        results = []

        for candidate in candidates:
            try:
                result = candidate, getattr(candidate, method)(*args, **kwargs)
                if return_first:
                    return result
                results.append(result)
            except OSError:
                # TODO: Replace with PermissionError
                pass

        if results:
            return results

        raise OSError(f"Unable to access any of {paths_csv(candidates)}")

    def write_text(self, path: Path, *args: Any, **kwargs: Any) -> Path:
        paths = self._path_method_wrapper(path, "write_text", *args, **kwargs)
        assert isinstance(paths, tuple)
        return paths[0]

    def mkdir(self, path: Path, *args: Any, **kwargs: Any) -> Path:
        paths = self._path_method_wrapper(path, "mkdir", *args, **kwargs)
        assert isinstance(paths, tuple)
        return paths[0]

    def exists(self, path: Path) -> bool:
        return any(
            value[-1]
            for value in self._path_method_wrapper(path, "exists", return_first=False)
        )

    def find(
        self,
        path: Path,
        writable_only: bool = False,
    ) -> list[Path]:
        return [
            value[0]
            for value in self._path_method_wrapper(
                path, "exists", return_first=False, writable_only=writable_only
            )
            if value[-1] is True
        ]


class EnvError(Exception):
    pass


class IncorrectEnvError(EnvError):
    def __init__(self, env_name: str) -> None:
        message = f"Env {env_name} doesn't belong to this project."
        super().__init__(message)


class EnvCommandError(EnvError):
    def __init__(self, e: CalledProcessError, input: str | None = None) -> None:
        self.e = e

        message_parts = [
            f"Command {e.cmd} errored with the following return code {e.returncode}"
        ]
        if e.output:
            message_parts.append(f"Output:\n{decode(e.output)}")
        if e.stderr:
            message_parts.append(f"Error output:\n{decode(e.stderr)}")
        if input:
            message_parts.append(f"Input:\n{input}")
        super().__init__("\n\n".join(message_parts))


class PythonVersionNotFound(EnvError):
    def __init__(self, expected: str) -> None:
        super().__init__(f"Could not find the python executable {expected}")


class NoCompatiblePythonVersionFound(EnvError):
    def __init__(self, expected: str, given: str | None = None) -> None:
        if given:
            message = (
                f"The specified Python version ({given}) "
                f"is not supported by the project ({expected}).\n"
                "Please choose a compatible version "
                "or loosen the python constraint specified "
                "in the pyproject.toml file."
            )
        else:
            message = (
                "Poetry was unable to find a compatible version. "
                "If you have one, you can explicitly use it "
                'via the "env use" command.'
            )

        super().__init__(message)


class InvalidCurrentPythonVersionError(EnvError):
    def __init__(self, expected: str, given: str) -> None:
        message = (
            f"Current Python version ({given}) "
            f"is not allowed by the project ({expected}).\n"
            'Please change python executable via the "env use" command.'
        )

        super().__init__(message)


class EnvManager:
    """
    Environments manager
    """

    _env = None

    ENVS_FILE = "envs.toml"

    def __init__(self, poetry: Poetry, io: None | IO = None) -> None:
        self._poetry = poetry
        self._io = io or NullIO()

    @staticmethod
    def _full_python_path(python: str) -> Path | None:
        # eg first find pythonXY.bat on windows.
        path_python = shutil.which(python)
        if path_python is None:
            return None

        try:
            executable = decode(
                subprocess.check_output(
                    [path_python, "-c", "import sys; print(sys.executable)"],
                ).strip()
            )
            return Path(executable)

        except CalledProcessError:
            return None

    @staticmethod
    def _detect_active_python(io: None | IO = None) -> Path | None:
        io = io or NullIO()
        io.write_error_line(
            (
                "Trying to detect current active python executable as specified in"
                " the config."
            ),
            verbosity=Verbosity.VERBOSE,
        )

        executable = EnvManager._full_python_path("python")

        if executable is not None:
            io.write_error_line(f"Found: {executable}", verbosity=Verbosity.VERBOSE)
        else:
            io.write_error_line(
                (
                    "Unable to detect the current active python executable. Falling"
                    " back to default."
                ),
                verbosity=Verbosity.VERBOSE,
            )

        return executable

    @staticmethod
    def get_python_version(
        precision: int = 3,
        prefer_active_python: bool = False,
        io: None | IO = None,
    ) -> Version:
        version = ".".join(str(v) for v in sys.version_info[:precision])

        if prefer_active_python:
            executable = EnvManager._detect_active_python(io)

            if executable:
                python_patch = decode(
                    subprocess.check_output(
                        [str(executable), "-c", GET_PYTHON_VERSION_ONELINER],
                    ).strip()
                )

                version = ".".join(str(v) for v in python_patch.split(".")[:precision])

        return Version.parse(version)

    @property
    def in_project_venv(self) -> Path:
        venv: Path = self._poetry.file.path.parent / ".venv"
        return venv

    def activate(self, python: str) -> Env:
        venv_path = self._poetry.config.virtualenvs_path
        cwd = self._poetry.file.path.parent

        envs_file = TOMLFile(venv_path / self.ENVS_FILE)

        try:
            python_version = Version.parse(python)
            python = f"python{python_version.major}"
            if python_version.precision > 1:
                python += f".{python_version.minor}"
        except ValueError:
            # Executable in PATH or full executable path
            pass

        python_path = self._full_python_path(python)
        if python_path is None:
            raise PythonVersionNotFound(python)

        try:
            python_version_string = decode(
                subprocess.check_output(
                    [str(python_path), "-c", GET_PYTHON_VERSION_ONELINER],
                )
            )
        except CalledProcessError as e:
            raise EnvCommandError(e)

        python_version = Version.parse(python_version_string.strip())
        minor = f"{python_version.major}.{python_version.minor}"
        patch = python_version.text

        create = False
        # If we are required to create the virtual environment in the project directory,
        # create or recreate it if needed
        if self.use_in_project_venv():
            create = False
            venv = self.in_project_venv
            if venv.exists():
                # We need to check if the patch version is correct
                _venv = VirtualEnv(venv)
                current_patch = ".".join(str(v) for v in _venv.version_info[:3])

                if patch != current_patch:
                    create = True

            self.create_venv(executable=python_path, force=create)

            return self.get(reload=True)

        envs = tomlkit.document()
        base_env_name = self.generate_env_name(self._poetry.package.name, str(cwd))
        if envs_file.exists():
            envs = envs_file.read()
            current_env = envs.get(base_env_name)
            if current_env is not None:
                current_minor = current_env["minor"]
                current_patch = current_env["patch"]

                if current_minor == minor and current_patch != patch:
                    # We need to recreate
                    create = True

        name = f"{base_env_name}-py{minor}"
        venv = venv_path / name

        # Create if needed
        if not venv.exists() or venv.exists() and create:
            in_venv = os.environ.get("VIRTUAL_ENV") is not None
            if in_venv or not venv.exists():
                create = True

            if venv.exists():
                # We need to check if the patch version is correct
                _venv = VirtualEnv(venv)
                current_patch = ".".join(str(v) for v in _venv.version_info[:3])

                if patch != current_patch:
                    create = True

            self.create_venv(executable=python_path, force=create)

        # Activate
        envs[base_env_name] = {"minor": minor, "patch": patch}
        envs_file.write(envs)

        return self.get(reload=True)

    def deactivate(self) -> None:
        venv_path = self._poetry.config.virtualenvs_path
        name = self.generate_env_name(
            self._poetry.package.name, str(self._poetry.file.path.parent)
        )

        envs_file = TOMLFile(venv_path / self.ENVS_FILE)
        if envs_file.exists():
            envs = envs_file.read()
            env = envs.get(name)
            if env is not None:
                venv = venv_path / f"{name}-py{env['minor']}"
                self._io.write_error_line(
                    f"Deactivating virtualenv: <comment>{venv}</comment>"
                )
                del envs[name]

                envs_file.write(envs)

    def get(self, reload: bool = False) -> Env:
        if self._env is not None and not reload:
            return self._env

        prefer_active_python = self._poetry.config.get(
            "virtualenvs.prefer-active-python"
        )
        python_minor = self.get_python_version(
            precision=2, prefer_active_python=prefer_active_python, io=self._io
        ).to_string()

        venv_path = self._poetry.config.virtualenvs_path

        cwd = self._poetry.file.path.parent
        envs_file = TOMLFile(venv_path / self.ENVS_FILE)
        env = None
        base_env_name = self.generate_env_name(self._poetry.package.name, str(cwd))
        if envs_file.exists():
            envs = envs_file.read()
            env = envs.get(base_env_name)
            if env:
                python_minor = env["minor"]

        # Check if we are inside a virtualenv or not
        # Conda sets CONDA_PREFIX in its envs, see
        # https://github.com/conda/conda/issues/2764
        env_prefix = os.environ.get("VIRTUAL_ENV", os.environ.get("CONDA_PREFIX"))
        conda_env_name = os.environ.get("CONDA_DEFAULT_ENV")
        # It's probably not a good idea to pollute Conda's global "base" env, since
        # most users have it activated all the time.
        in_venv = env_prefix is not None and conda_env_name != "base"

        if not in_venv or env is not None:
            # Checking if a local virtualenv exists
            if self.in_project_venv_exists():
                venv = self.in_project_venv

                return VirtualEnv(venv)

            create_venv = self._poetry.config.get("virtualenvs.create", True)

            if not create_venv:
                return self.get_system_env()

            venv_path = self._poetry.config.virtualenvs_path

            name = f"{base_env_name}-py{python_minor.strip()}"

            venv = venv_path / name

            if not venv.exists():
                return self.get_system_env()

            return VirtualEnv(venv)

        if env_prefix is not None:
            prefix = Path(env_prefix)
            base_prefix = None
        else:
            prefix = Path(sys.prefix)
            base_prefix = self.get_base_prefix()

        return VirtualEnv(prefix, base_prefix)

    def list(self, name: str | None = None) -> list[VirtualEnv]:
        if name is None:
            name = self._poetry.package.name

        venv_name = self.generate_env_name(name, str(self._poetry.file.path.parent))
        venv_path = self._poetry.config.virtualenvs_path
        env_list = [VirtualEnv(p) for p in sorted(venv_path.glob(f"{venv_name}-py*"))]

        if self.in_project_venv_exists():
            venv = self.in_project_venv
            env_list.insert(0, VirtualEnv(venv))
        return env_list

    @staticmethod
    def check_env_is_for_current_project(env: str, base_env_name: str) -> bool:
        """
        Check if env name starts with projects name.

        This is done to prevent action on other project's envs.
        """
        return env.startswith(base_env_name)

    def remove(self, python: str) -> Env:
        venv_path = self._poetry.config.virtualenvs_path

        cwd = self._poetry.file.path.parent
        envs_file = TOMLFile(venv_path / self.ENVS_FILE)
        base_env_name = self.generate_env_name(self._poetry.package.name, str(cwd))

        python_path = Path(python)
        if python_path.is_file():
            # Validate env name if provided env is a full path to python
            try:
                env_dir = decode(
                    subprocess.check_output(
                        [python, "-c", GET_ENV_PATH_ONELINER],
                    )
                ).strip("\n")
                env_name = Path(env_dir).name
                if not self.check_env_is_for_current_project(env_name, base_env_name):
                    raise IncorrectEnvError(env_name)
            except CalledProcessError as e:
                raise EnvCommandError(e)

        if self.check_env_is_for_current_project(python, base_env_name):
            venvs = self.list()
            for venv in venvs:
                if venv.path.name == python:
                    # Exact virtualenv name
                    if not envs_file.exists():
                        self.remove_venv(venv.path)

                        return venv

                    venv_minor = ".".join(str(v) for v in venv.version_info[:2])
                    base_env_name = self.generate_env_name(cwd.name, str(cwd))
                    envs = envs_file.read()

                    current_env = envs.get(base_env_name)
                    if not current_env:
                        self.remove_venv(venv.path)

                        return venv

                    if current_env["minor"] == venv_minor:
                        del envs[base_env_name]
                        envs_file.write(envs)

                    self.remove_venv(venv.path)

                    return venv

            raise ValueError(
                f'<warning>Environment "{python}" does not exist.</warning>'
            )
        else:
            venv_path = self._poetry.config.virtualenvs_path
            # Get all the poetry envs, even for other projects
            env_names = [p.name for p in sorted(venv_path.glob("*-*-py*"))]
            if python in env_names:
                raise IncorrectEnvError(python)

        try:
            python_version = Version.parse(python)
            python = f"python{python_version.major}"
            if python_version.precision > 1:
                python += f".{python_version.minor}"
        except ValueError:
            # Executable in PATH or full executable path
            pass

        try:
            python_version_string = decode(
                subprocess.check_output(
                    [python, "-c", GET_PYTHON_VERSION_ONELINER],
                )
            )
        except CalledProcessError as e:
            raise EnvCommandError(e)

        python_version = Version.parse(python_version_string.strip())
        minor = f"{python_version.major}.{python_version.minor}"

        name = f"{base_env_name}-py{minor}"
        venv_path = venv_path / name

        if not venv_path.exists():
            raise ValueError(f'<warning>Environment "{name}" does not exist.</warning>')

        if envs_file.exists():
            envs = envs_file.read()
            current_env = envs.get(base_env_name)
            if current_env is not None:
                current_minor = current_env["minor"]

                if current_minor == minor:
                    del envs[base_env_name]
                    envs_file.write(envs)

        self.remove_venv(venv_path)

        return VirtualEnv(venv_path, venv_path)

    def use_in_project_venv(self) -> bool:
        in_project: bool | None = self._poetry.config.get("virtualenvs.in-project")
        if in_project is not None:
            return in_project

        return self.in_project_venv.is_dir()

    def in_project_venv_exists(self) -> bool:
        in_project: bool | None = self._poetry.config.get("virtualenvs.in-project")
        if in_project is False:
            return False

        return self.in_project_venv.is_dir()

    def create_venv(
        self,
        name: str | None = None,
        executable: Path | None = None,
        force: bool = False,
    ) -> Env:
        if self._env is not None and not force:
            return self._env

        cwd = self._poetry.file.path.parent
        env = self.get(reload=True)

        if not env.is_sane():
            force = True

        if env.is_venv() and not force:
            # Already inside a virtualenv.
            current_python = Version.parse(
                ".".join(str(c) for c in env.version_info[:3])
            )
            if not self._poetry.package.python_constraint.allows(current_python):
                raise InvalidCurrentPythonVersionError(
                    self._poetry.package.python_versions, str(current_python)
                )
            return env

        create_venv = self._poetry.config.get("virtualenvs.create")
        in_project_venv = self.use_in_project_venv()
        prefer_active_python = self._poetry.config.get(
            "virtualenvs.prefer-active-python"
        )
        venv_prompt = self._poetry.config.get("virtualenvs.prompt")

        if not executable and prefer_active_python:
            executable = self._detect_active_python()

        venv_path = (
            self.in_project_venv
            if in_project_venv
            else self._poetry.config.virtualenvs_path
        )
        if not name:
            name = self._poetry.package.name

        python_patch = ".".join([str(v) for v in sys.version_info[:3]])
        python_minor = ".".join([str(v) for v in sys.version_info[:2]])
        if executable:
            python_patch = decode(
                subprocess.check_output(
                    [str(executable), "-c", GET_PYTHON_VERSION_ONELINER],
                ).strip()
            )
            python_minor = ".".join(python_patch.split(".")[:2])

        supported_python = self._poetry.package.python_constraint
        if not supported_python.allows(Version.parse(python_patch)):
            # The currently activated or chosen Python version
            # is not compatible with the Python constraint specified
            # for the project.
            # If an executable has been specified, we stop there
            # and notify the user of the incompatibility.
            # Otherwise, we try to find a compatible Python version.
            if executable and not prefer_active_python:
                raise NoCompatiblePythonVersionFound(
                    self._poetry.package.python_versions, python_patch
                )

            self._io.write_error_line(
                f"<warning>The currently activated Python version {python_patch} is not"
                f" supported by the project ({self._poetry.package.python_versions}).\n"
                "Trying to find and use a compatible version.</warning> "
            )

            for suffix in sorted(
                self._poetry.package.AVAILABLE_PYTHONS,
                key=lambda v: (v.startswith("3"), -len(v), v),
                reverse=True,
            ):
                if len(suffix) == 1:
                    if not parse_constraint(f"^{suffix}.0").allows_any(
                        supported_python
                    ):
                        continue
                elif not supported_python.allows_any(parse_constraint(suffix + ".*")):
                    continue

                python_name = f"python{suffix}"
                if self._io.is_debug():
                    self._io.write_error_line(f"<debug>Trying {python_name}</debug>")

                python = self._full_python_path(python_name)
                if python is None:
                    continue

                try:
                    python_patch = decode(
                        subprocess.check_output(
                            [str(python), "-c", GET_PYTHON_VERSION_ONELINER],
                            stderr=subprocess.STDOUT,
                        ).strip()
                    )
                except CalledProcessError:
                    continue

                if supported_python.allows(Version.parse(python_patch)):
                    self._io.write_error_line(
                        f"Using <c1>{python_name}</c1> ({python_patch})"
                    )
                    executable = python
                    python_minor = ".".join(python_patch.split(".")[:2])
                    break

            if not executable:
                raise NoCompatiblePythonVersionFound(
                    self._poetry.package.python_versions
                )

        if in_project_venv:
            venv = venv_path
        else:
            name = self.generate_env_name(name, str(cwd))
            name = f"{name}-py{python_minor.strip()}"
            venv = venv_path / name

        if venv_prompt is not None:
            venv_prompt = venv_prompt.format(
                project_name=self._poetry.package.name or "virtualenv",
                python_version=python_minor,
            )

        if not venv.exists():
            if create_venv is False:
                self._io.write_error_line(
                    "<fg=black;bg=yellow>"
                    "Skipping virtualenv creation, "
                    "as specified in config file."
                    "</>"
                )

                return self.get_system_env()

            self._io.write_error_line(
                f"Creating virtualenv <c1>{name}</> in"
                f" {venv_path if not WINDOWS else get_real_windows_path(venv_path)!s}"
            )
        else:
            create_venv = False
            if force:
                if not env.is_sane():
                    self._io.write_error_line(
                        f"<warning>The virtual environment found in {env.path} seems to"
                        " be broken.</warning>"
                    )
                self._io.write_error_line(
                    f"Recreating virtualenv <c1>{name}</> in {venv!s}"
                )
                self.remove_venv(venv)
                create_venv = True
            elif self._io.is_very_verbose():
                self._io.write_error_line(f"Virtualenv <c1>{name}</> already exists.")

        if create_venv:
            self.build_venv(
                venv,
                executable=executable,
                flags=self._poetry.config.get("virtualenvs.options"),
                prompt=venv_prompt,
            )

        # venv detection:
        # stdlib venv may symlink sys.executable, so we can't use realpath.
        # but others can symlink *to* the venv Python,
        # so we can't just use sys.executable.
        # So we just check every item in the symlink tree (generally <= 3)
        p = os.path.normcase(sys.executable)
        paths = [p]
        while os.path.islink(p):
            p = os.path.normcase(os.path.join(os.path.dirname(p), os.readlink(p)))
            paths.append(p)

        p_venv = os.path.normcase(str(venv))
        if any(p.startswith(p_venv) for p in paths):
            # Running properly in the virtualenv, don't need to do anything
            return self.get_system_env()

        return VirtualEnv(venv)

    @classmethod
    def build_venv(
        cls,
        path: Path,
        executable: Path | None = None,
        flags: dict[str, bool] | None = None,
        with_pip: bool | None = None,
        with_wheel: bool | None = None,
        with_setuptools: bool | None = None,
        prompt: str | None = None,
    ) -> virtualenv.run.session.Session:
        if WINDOWS:
            path = get_real_windows_path(path)
            executable = get_real_windows_path(executable) if executable else None

        flags = flags or {}

        flags["no-pip"] = (
            not with_pip if with_pip is not None else flags.pop("no-pip", True)
        )

        flags["no-setuptools"] = (
            not with_setuptools
            if with_setuptools is not None
            else flags.pop("no-setuptools", True)
        )

        # we want wheels to be enabled when pip is required and it has not been
        # explicitly disabled
        flags["no-wheel"] = (
            not with_wheel
            if with_wheel is not None
            else flags.pop("no-wheel", flags["no-pip"])
        )

        executable_str = None if executable is None else executable.resolve().as_posix()

        args = [
            "--no-download",
            "--no-periodic-update",
            "--python",
            executable_str or sys.executable,
        ]

        if prompt is not None:
            args.extend(["--prompt", prompt])

        for flag, value in flags.items():
            if value is True:
                args.append(f"--{flag}")

        args.append(str(path))

        cli_result = virtualenv.cli_run(args)

        # Exclude the venv folder from from macOS Time Machine backups
        # TODO: Add backup-ignore markers for other platforms too
        if sys.platform == "darwin":
            import xattr

            xattr.setxattr(
                str(path),
                "com.apple.metadata:com_apple_backup_excludeItem",
                plistlib.dumps("com.apple.backupd", fmt=plistlib.FMT_BINARY),
            )

        return cli_result

    @classmethod
    def remove_venv(cls, path: Path) -> None:
        assert path.is_dir()
        try:
            remove_directory(path)
            return
        except OSError as e:
            # Continue only if e.errno == 16
            if e.errno != 16:  # ERRNO 16: Device or resource busy
                raise e

        # Delete all files and folders but the toplevel one. This is because sometimes
        # the venv folder is mounted by the OS, such as in a docker volume. In such
        # cases, an attempt to delete the folder itself will result in an `OSError`.
        # See https://github.com/python-poetry/poetry/pull/2064
        for file_path in path.iterdir():
            if file_path.is_file() or file_path.is_symlink():
                file_path.unlink()
            elif file_path.is_dir():
                remove_directory(file_path, force=True)

    @classmethod
    def get_system_env(cls, naive: bool = False) -> Env:
        """
        Retrieve the current Python environment.

        This can be the base Python environment or an activated virtual environment.

        This method also workaround the issue that the virtual environment
        used by Poetry internally (when installed via the custom installer)
        is incorrectly detected as the system environment. Note that this workaround
        happens only when `naive` is False since there are times where we actually
        want to retrieve Poetry's custom virtual environment
        (e.g. plugin installation or self update).
        """
        prefix, base_prefix = Path(sys.prefix), Path(cls.get_base_prefix())
        env: Env = SystemEnv(prefix)
        if not naive:
            if prefix.joinpath("poetry_env").exists():
                env = GenericEnv(base_prefix, child_env=env)
            else:
                from poetry.locations import data_dir

                try:
                    prefix.relative_to(data_dir())
                except ValueError:
                    pass
                else:
                    env = GenericEnv(base_prefix, child_env=env)

        return env

    @classmethod
    def get_base_prefix(cls) -> Path:
        real_prefix = getattr(sys, "real_prefix", None)
        if real_prefix is not None:
            return Path(real_prefix)

        base_prefix = getattr(sys, "base_prefix", None)
        if base_prefix is not None:
            return Path(base_prefix)

        return Path(sys.prefix)

    @classmethod
    def generate_env_name(cls, name: str, cwd: str) -> str:
        name = name.lower()
        sanitized_name = re.sub(r'[ $`!*@"\\\r\n\t]', "_", name)[:42]
        normalized_cwd = os.path.normcase(os.path.realpath(cwd))
        h_bytes = hashlib.sha256(encode(normalized_cwd)).digest()
        h_str = base64.urlsafe_b64encode(h_bytes).decode()[:8]

        return f"{sanitized_name}-{h_str}"


class Env:
    """
    An abstract Python environment.
    """

    def __init__(self, path: Path, base: Path | None = None) -> None:
        self._is_windows = sys.platform == "win32"
        self._is_mingw = sysconfig.get_platform().startswith("mingw")
        self._is_conda = bool(os.environ.get("CONDA_DEFAULT_ENV"))

        if self._is_windows:
            path = get_real_windows_path(path)
            base = get_real_windows_path(base) if base else None

        bin_dir = "bin" if not self._is_windows or self._is_mingw else "Scripts"
        self._path = path
        self._bin_dir = self._path / bin_dir

        self._executable = "python"
        self._pip_executable = "pip"

        self.find_executables()

        self._base = base or path

        self._marker_env: dict[str, Any] | None = None
        self._pip_version: Version | None = None
        self._site_packages: SitePackages | None = None
        self._paths: dict[str, str] | None = None
        self._supported_tags: list[Tag] | None = None
        self._purelib: Path | None = None
        self._platlib: Path | None = None
        self._script_dirs: list[Path] | None = None

        self._embedded_pip_path: Path | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def base(self) -> Path:
        return self._base

    @property
    def version_info(self) -> tuple[int, int, int, str, int]:
        version_info: tuple[int, int, int, str, int] = self.marker_env["version_info"]
        return version_info

    @property
    def python_implementation(self) -> str:
        implementation: str = self.marker_env["platform_python_implementation"]
        return implementation

    @property
    def python(self) -> Path:
        """
        Path to current python executable
        """
        return Path(self._bin(self._executable))

    @property
    def marker_env(self) -> dict[str, Any]:
        if self._marker_env is None:
            self._marker_env = self.get_marker_env()

        return self._marker_env

    @property
    def parent_env(self) -> GenericEnv:
        return GenericEnv(self.base, child_env=self)

    def _find_python_executable(self) -> None:
        bin_dir = self._bin_dir

        if self._is_windows and self._is_conda:
            bin_dir = self._path

        python_executables = sorted(
            p.name
            for p in bin_dir.glob("python*")
            if re.match(r"python(?:\d+(?:\.\d+)?)?(?:\.exe)?$", p.name)
        )
        if python_executables:
            executable = python_executables[0]
            if executable.endswith(".exe"):
                executable = executable[:-4]

            self._executable = executable

    def _find_pip_executable(self) -> None:
        pip_executables = sorted(
            p.name
            for p in self._bin_dir.glob("pip*")
            if re.match(r"pip(?:\d+(?:\.\d+)?)?(?:\.exe)?$", p.name)
        )
        if pip_executables:
            pip_executable = pip_executables[0]
            if pip_executable.endswith(".exe"):
                pip_executable = pip_executable[:-4]

            self._pip_executable = pip_executable

    def find_executables(self) -> None:
        self._find_python_executable()
        self._find_pip_executable()

    def get_embedded_wheel(self, distribution: str) -> Path:
        wheel: Wheel = get_embed_wheel(
            distribution, f"{self.version_info[0]}.{self.version_info[1]}"
        )
        path: Path = wheel.path
        return path

    @property
    def pip_embedded(self) -> Path:
        if self._embedded_pip_path is None:
            self._embedded_pip_path = self.get_embedded_wheel("pip") / "pip"
        return self._embedded_pip_path

    @property
    def pip(self) -> Path:
        """
        Path to current pip executable
        """
        # we do not use as_posix() here due to issues with windows pathlib2
        # implementation
        path = Path(self._bin(self._pip_executable))
        if not path.exists():
            return self.pip_embedded
        return path

    @property
    def platform(self) -> str:
        return sys.platform

    @property
    def os(self) -> str:
        return os.name

    @property
    def pip_version(self) -> Version:
        if self._pip_version is None:
            self._pip_version = self.get_pip_version()

        return self._pip_version

    @property
    def site_packages(self) -> SitePackages:
        if self._site_packages is None:
            # we disable write checks if no user site exist
            fallbacks = [self.usersite] if self.usersite else []
            self._site_packages = SitePackages(
                self.purelib,
                self.platlib,
                fallbacks,
                skip_write_checks=not fallbacks,
            )
        return self._site_packages

    @property
    def usersite(self) -> Path | None:
        if "usersite" in self.paths:
            return Path(self.paths["usersite"])
        return None

    @property
    def userbase(self) -> Path | None:
        if "userbase" in self.paths:
            return Path(self.paths["userbase"])
        return None

    @property
    def purelib(self) -> Path:
        if self._purelib is None:
            self._purelib = Path(self.paths["purelib"])

        return self._purelib

    @property
    def platlib(self) -> Path:
        if self._platlib is None:
            if "platlib" in self.paths:
                self._platlib = Path(self.paths["platlib"])
            else:
                self._platlib = self.purelib

        return self._platlib

    def is_path_relative_to_lib(self, path: Path) -> bool:
        for lib_path in [self.purelib, self.platlib]:
            with contextlib.suppress(ValueError):
                path.relative_to(lib_path)
                return True

        return False

    @property
    def sys_path(self) -> list[str]:
        raise NotImplementedError()

    @property
    def paths(self) -> dict[str, str]:
        if self._paths is None:
            self._paths = self.get_paths()

            if self.is_venv():
                # We copy pip's logic here for the `include` path
                self._paths["include"] = str(
                    self.path.joinpath(
                        "include",
                        "site",
                        f"python{self.version_info[0]}.{self.version_info[1]}",
                    )
                )

        return self._paths

    @property
    def supported_tags(self) -> list[Tag]:
        if self._supported_tags is None:
            self._supported_tags = self.get_supported_tags()

        return self._supported_tags

    @classmethod
    def get_base_prefix(cls) -> Path:
        real_prefix = getattr(sys, "real_prefix", None)
        if real_prefix is not None:
            return Path(real_prefix)

        base_prefix = getattr(sys, "base_prefix", None)
        if base_prefix is not None:
            return Path(base_prefix)

        return Path(sys.prefix)

    def get_version_info(self) -> tuple[Any, ...]:
        raise NotImplementedError()

    def get_python_implementation(self) -> str:
        raise NotImplementedError()

    def get_marker_env(self) -> dict[str, Any]:
        raise NotImplementedError()

    def get_pip_command(self, embedded: bool = False) -> list[str]:
        if embedded or not Path(self._bin(self._pip_executable)).exists():
            return [str(self.python), str(self.pip_embedded)]
        # run as module so that pip can update itself on Windows
        return [str(self.python), "-m", "pip"]

    def get_supported_tags(self) -> list[Tag]:
        raise NotImplementedError()

    def get_pip_version(self) -> Version:
        raise NotImplementedError()

    def get_paths(self) -> dict[str, str]:
        raise NotImplementedError()

    def is_valid_for_marker(self, marker: BaseMarker) -> bool:
        valid: bool = marker.validate(self.marker_env)
        return valid

    def is_sane(self) -> bool:
        """
        Checks whether the current environment is sane or not.
        """
        return True

    def get_command_from_bin(self, bin: str) -> list[str]:
        if bin == "pip":
            # when pip is required we need to ensure that we fallback to
            # embedded pip when pip is not available in the environment
            return self.get_pip_command()

        return [self._bin(bin)]

    def run(self, bin: str, *args: str, **kwargs: Any) -> str:
        cmd = self.get_command_from_bin(bin) + list(args)
        return self._run(cmd, **kwargs)

    def run_pip(self, *args: str, **kwargs: Any) -> str:
        pip = self.get_pip_command()
        cmd = pip + list(args)
        return self._run(cmd, **kwargs)

    def run_python_script(self, content: str, **kwargs: Any) -> str:
        return self.run(
            self._executable,
            "-I",
            "-W",
            "ignore",
            "-",
            input_=content,
            stderr=subprocess.PIPE,
            **kwargs,
        )

    def _run(self, cmd: list[str], **kwargs: Any) -> str:
        """
        Run a command inside the Python environment.
        """
        call = kwargs.pop("call", False)
        input_ = kwargs.pop("input_", None)
        env = kwargs.pop("env", dict(os.environ))
        stderr = kwargs.pop("stderr", subprocess.STDOUT)

        try:
            if input_:
                output = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=stderr,
                    input=encode(input_),
                    check=True,
                    env=env,
                    **kwargs,
                ).stdout
            elif call:
                assert stderr != subprocess.PIPE
                subprocess.check_call(cmd, stderr=stderr, env=env, **kwargs)
                output = ""
            else:
                output = subprocess.check_output(cmd, stderr=stderr, env=env, **kwargs)
        except CalledProcessError as e:
            raise EnvCommandError(e, input=input_)

        return decode(output)

    def execute(self, bin: str, *args: str, **kwargs: Any) -> int:
        command = self.get_command_from_bin(bin) + list(args)
        env = kwargs.pop("env", dict(os.environ))

        if not self._is_windows:
            return os.execvpe(command[0], command, env=env)

        kwargs["shell"] = True
        exe = subprocess.Popen(command, env=env, **kwargs)
        exe.communicate()
        return exe.returncode

    def is_venv(self) -> bool:
        raise NotImplementedError()

    @property
    def script_dirs(self) -> list[Path]:
        if self._script_dirs is None:
            scripts = self.paths.get("scripts")
            self._script_dirs = [
                Path(scripts) if scripts is not None else self._bin_dir
            ]
            if self.userbase:
                self._script_dirs.append(self.userbase / self._script_dirs[0].name)
        return self._script_dirs

    def _bin(self, bin: str) -> str:
        """
        Return path to the given executable.
        """
        if self._is_windows and not bin.endswith(".exe"):
            bin_path = self._bin_dir / (bin + ".exe")
        else:
            bin_path = self._bin_dir / bin

        if not bin_path.exists():
            # On Windows, some executables can be in the base path
            # This is especially true when installing Python with
            # the official installer, where python.exe will be at
            # the root of the env path.
            if self._is_windows:
                if not bin.endswith(".exe"):
                    bin_path = self._path / (bin + ".exe")
                else:
                    bin_path = self._path / bin

                if bin_path.exists():
                    return str(bin_path)

            return bin

        return str(bin_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Env):
            return False

        return other.__class__ == self.__class__ and other.path == self.path

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self._path}")'


class SystemEnv(Env):
    """
    A system (i.e. not a virtualenv) Python environment.
    """

    @property
    def python(self) -> Path:
        return Path(sys.executable)

    @property
    def sys_path(self) -> list[str]:
        return sys.path

    def get_version_info(self) -> tuple[Any, ...]:
        return tuple(sys.version_info)

    def get_python_implementation(self) -> str:
        return platform.python_implementation()

    def get_paths(self) -> dict[str, str]:
        import site

        paths = sysconfig.get_paths().copy()

        if site.check_enableusersite():
            paths["usersite"] = site.getusersitepackages()
            paths["userbase"] = site.getuserbase()

        return paths

    def get_supported_tags(self) -> list[Tag]:
        return list(sys_tags())

    def get_marker_env(self) -> dict[str, Any]:
        if hasattr(sys, "implementation"):
            info = sys.implementation.version
            iver = f"{info.major}.{info.minor}.{info.micro}"
            kind = info.releaselevel
            if kind != "final":
                iver += kind[0] + str(info.serial)

            implementation_name = sys.implementation.name
        else:
            iver = "0"
            implementation_name = ""

        return {
            "implementation_name": implementation_name,
            "implementation_version": iver,
            "os_name": os.name,
            "platform_machine": platform.machine(),
            "platform_release": platform.release(),
            "platform_system": platform.system(),
            "platform_version": platform.version(),
            "python_full_version": platform.python_version(),
            "platform_python_implementation": platform.python_implementation(),
            "python_version": ".".join(platform.python_version().split(".")[:2]),
            "sys_platform": sys.platform,
            "version_info": sys.version_info,
            "interpreter_name": interpreter_name(),
            "interpreter_version": interpreter_version(),
        }

    def get_pip_version(self) -> Version:
        from pip import __version__

        return Version.parse(__version__)

    def is_venv(self) -> bool:
        return self._path != self._base


class VirtualEnv(Env):
    """
    A virtual Python environment.
    """

    def __init__(self, path: Path, base: Path | None = None) -> None:
        super().__init__(path, base)

        # If base is None, it probably means this is
        # a virtualenv created from VIRTUAL_ENV.
        # In this case we need to get sys.base_prefix
        # from inside the virtualenv.
        if base is None:
            output = self.run_python_script(GET_BASE_PREFIX)
            self._base = Path(output.strip())

    @property
    def sys_path(self) -> list[str]:
        output = self.run_python_script(GET_SYS_PATH)
        paths: list[str] = json.loads(output)
        return paths

    def get_version_info(self) -> tuple[Any, ...]:
        output = self.run_python_script(GET_PYTHON_VERSION)
        assert isinstance(output, str)

        return tuple(int(s) for s in output.strip().split("."))

    def get_python_implementation(self) -> str:
        implementation: str = self.marker_env["platform_python_implementation"]
        return implementation

    def get_supported_tags(self) -> list[Tag]:
        output = self.run_python_script(GET_SYS_TAGS)

        return [Tag(*t) for t in json.loads(output)]

    def get_marker_env(self) -> dict[str, Any]:
        output = self.run_python_script(GET_ENVIRONMENT_INFO)

        env: dict[str, Any] = json.loads(output)
        return env

    def get_pip_version(self) -> Version:
        output = self.run_pip("--version")
        output = output.strip()

        m = re.match("pip (.+?)(?: from .+)?$", output)
        if not m:
            return Version.parse("0.0")

        return Version.parse(m.group(1))

    def get_paths(self) -> dict[str, str]:
        output = self.run_python_script(GET_PATHS)
        paths: dict[str, str] = json.loads(output)
        return paths

    def is_venv(self) -> bool:
        return True

    def is_sane(self) -> bool:
        # A virtualenv is considered sane if "python" exists.
        return os.path.exists(self.python)

    def _run(self, cmd: list[str], **kwargs: Any) -> str:
        kwargs["env"] = self.get_temp_environ(environ=kwargs.get("env"))
        return super()._run(cmd, **kwargs)

    def get_temp_environ(
        self,
        environ: dict[str, str] | None = None,
        exclude: list[str] | None = None,
        **kwargs: str,
    ) -> dict[str, str]:
        exclude = exclude or []
        exclude.extend(["PYTHONHOME", "__PYVENV_LAUNCHER__"])

        if environ:
            environ = deepcopy(environ)
            for key in exclude:
                environ.pop(key, None)
        else:
            environ = {k: v for k, v in os.environ.items() if k not in exclude}

        environ.update(kwargs)

        environ["PATH"] = self._updated_path()
        environ["VIRTUAL_ENV"] = str(self._path)

        return environ

    def execute(self, bin: str, *args: str, **kwargs: Any) -> int:
        kwargs["env"] = self.get_temp_environ(environ=kwargs.get("env"))
        return super().execute(bin, *args, **kwargs)

    @contextmanager
    def temp_environ(self) -> Iterator[None]:
        environ = dict(os.environ)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(environ)

    def _updated_path(self) -> str:
        return os.pathsep.join([str(self._bin_dir), os.environ.get("PATH", "")])


class GenericEnv(VirtualEnv):
    def __init__(
        self, path: Path, base: Path | None = None, child_env: Env | None = None
    ) -> None:
        self._child_env = child_env

        super().__init__(path, base=base)

    def find_executables(self) -> None:
        patterns = [("python*", "pip*")]

        if self._child_env:
            minor_version = (
                f"{self._child_env.version_info[0]}.{self._child_env.version_info[1]}"
            )
            major_version = f"{self._child_env.version_info[0]}"
            patterns = [
                (f"python{minor_version}", f"pip{minor_version}"),
                (f"python{major_version}", f"pip{major_version}"),
            ]

        python_executable = None
        pip_executable = None

        for python_pattern, pip_pattern in patterns:
            if python_executable and pip_executable:
                break

            if not python_executable:
                python_executables = sorted(
                    p.name
                    for p in self._bin_dir.glob(python_pattern)
                    if re.match(r"python(?:\d+(?:\.\d+)?)?(?:\.exe)?$", p.name)
                )

                if python_executables:
                    executable = python_executables[0]
                    if executable.endswith(".exe"):
                        executable = executable[:-4]

                    python_executable = executable

            if not pip_executable:
                pip_executables = sorted(
                    p.name
                    for p in self._bin_dir.glob(pip_pattern)
                    if re.match(r"pip(?:\d+(?:\.\d+)?)?(?:\.exe)?$", p.name)
                )
                if pip_executables:
                    pip_executable = pip_executables[0]
                    if pip_executable.endswith(".exe"):
                        pip_executable = pip_executable[:-4]

            if python_executable:
                self._executable = python_executable

            if pip_executable:
                self._pip_executable = pip_executable

    def get_paths(self) -> dict[str, str]:
        output = self.run_python_script(GET_PATHS_FOR_GENERIC_ENVS)

        paths: dict[str, str] = json.loads(output)
        return paths

    def execute(self, bin: str, *args: str, **kwargs: Any) -> int:
        command = self.get_command_from_bin(bin) + list(args)
        env = kwargs.pop("env", dict(os.environ))

        if not self._is_windows:
            return os.execvpe(command[0], command, env=env)

        exe = subprocess.Popen(command, env=env, **kwargs)
        exe.communicate()

        return exe.returncode

    def _run(self, cmd: list[str], **kwargs: Any) -> str:
        return super(VirtualEnv, self)._run(cmd, **kwargs)

    def is_venv(self) -> bool:
        return self._path != self._base


class NullEnv(SystemEnv):
    def __init__(
        self, path: Path | None = None, base: Path | None = None, execute: bool = False
    ) -> None:
        if path is None:
            path = Path(sys.prefix)

        super().__init__(path, base=base)

        self._execute = execute
        self.executed: list[list[str]] = []

    @property
    def paths(self) -> dict[str, str]:
        if self._paths is None:
            self._paths = self.get_paths()
            self._paths["platlib"] = str(self._path / "platlib")
            self._paths["purelib"] = str(self._path / "purelib")
            self._paths["scripts"] = str(self._path / "scripts")
            self._paths["data"] = str(self._path / "data")

        return self._paths

    def _run(self, cmd: list[str], **kwargs: Any) -> str:
        self.executed.append(cmd)

        if self._execute:
            return super()._run(cmd, **kwargs)
        return ""

    def execute(self, bin: str, *args: str, **kwargs: Any) -> int:
        self.executed.append([bin, *list(args)])

        if self._execute:
            return super().execute(bin, *args, **kwargs)
        return 0

    def _bin(self, bin: str) -> str:
        return bin


@contextmanager
def ephemeral_environment(
    executable: Path | None = None,
    flags: dict[str, bool] | None = None,
) -> Iterator[VirtualEnv]:
    with temporary_directory() as tmp_dir:
        # TODO: cache PEP 517 build environment corresponding to each project venv
        venv_dir = Path(tmp_dir) / ".venv"
        EnvManager.build_venv(
            path=venv_dir,
            executable=executable,
            flags=flags,
        )
        yield VirtualEnv(venv_dir, venv_dir)


@contextmanager
def build_environment(
    poetry: CorePoetry, env: Env | None = None, io: IO | None = None
) -> Iterator[Env]:
    """
    If a build script is specified for the project, there could be additional build
    time dependencies, eg: cython, setuptools etc. In these cases, we create an
    ephemeral build environment with all requirements specified under
    `build-system.requires` and return this. Otherwise, the given default project
    environment is returned.
    """
    if not env or poetry.package.build_script:
        with ephemeral_environment(executable=env.python if env else None) as venv:
            overwrite = (
                io is not None and io.output.is_decorated() and not io.is_debug()
            )

            if io:
                if not overwrite:
                    io.write_error_line("")

                requires = [
                    f"<c1>{requirement}</c1>"
                    for requirement in poetry.pyproject.build_system.requires
                ]

                io.overwrite_error(
                    "<b>Preparing</b> build environment with build-system requirements"
                    f" {', '.join(requires)}"
                )

            venv.run_pip(
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--no-input",
                *poetry.pyproject.build_system.requires,
            )

            if overwrite:
                assert io is not None
                io.write_error_line("")

            yield venv
    else:
        yield env


class MockEnv(NullEnv):
    def __init__(
        self,
        version_info: tuple[int, int, int] = (3, 7, 0),
        python_implementation: str = "CPython",
        platform: str = "darwin",
        os_name: str = "posix",
        is_venv: bool = False,
        pip_version: str = "19.1",
        sys_path: list[str] | None = None,
        marker_env: dict[str, Any] | None = None,
        supported_tags: list[Tag] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._version_info = version_info
        self._python_implementation = python_implementation
        self._platform = platform
        self._os_name = os_name
        self._is_venv = is_venv
        self._pip_version: Version = Version.parse(pip_version)
        self._sys_path = sys_path
        self._mock_marker_env = marker_env
        self._supported_tags = supported_tags

    @property
    def platform(self) -> str:
        return self._platform

    @property
    def os(self) -> str:
        return self._os_name

    @property
    def pip_version(self) -> Version:
        return self._pip_version

    @property
    def sys_path(self) -> list[str]:
        if self._sys_path is None:
            return super().sys_path

        return self._sys_path

    def get_marker_env(self) -> dict[str, Any]:
        if self._mock_marker_env is not None:
            return self._mock_marker_env

        marker_env = super().get_marker_env()
        marker_env["python_implementation"] = self._python_implementation
        marker_env["version_info"] = self._version_info
        marker_env["python_version"] = ".".join(str(v) for v in self._version_info[:2])
        marker_env["python_full_version"] = ".".join(str(v) for v in self._version_info)
        marker_env["sys_platform"] = self._platform
        marker_env["interpreter_name"] = self._python_implementation.lower()
        marker_env["interpreter_version"] = "cp" + "".join(
            str(v) for v in self._version_info[:2]
        )

        return marker_env

    def is_venv(self) -> bool:
        return self._is_venv
