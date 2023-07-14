from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from poetry.core.packages.dependency import Dependency
from poetry.core.packages.project_package import ProjectPackage

from poetry.__version__ import __version__
from poetry.console.commands.installer_command import InstallerCommand
from poetry.factory import Factory
from poetry.pyproject.toml import PyProjectTOML
from poetry.utils.env import EnvManager
from poetry.utils.env import SystemEnv
from poetry.utils.helpers import directory


if TYPE_CHECKING:
    from poetry.poetry import Poetry
    from poetry.utils.env import Env


class SelfCommand(InstallerCommand):
    ADDITIONAL_PACKAGE_GROUP = "additional"

    @staticmethod
    def get_default_system_pyproject_file() -> Path:
        # We separate this out to avoid unwanted side effect during testing while
        # maintaining dynamic use in help text.
        #
        # This is not ideal, but is the simplest solution for now.
        from poetry.locations import CONFIG_DIR

        return Path(CONFIG_DIR).joinpath("pyproject.toml")

    @property
    def system_pyproject(self) -> Path:
        file = self.get_default_system_pyproject_file()
        file.parent.mkdir(parents=True, exist_ok=True)
        return file

    def reset_env(self) -> None:
        self._env = EnvManager.get_system_env(naive=True)

    @property
    def env(self) -> Env:
        if not isinstance(self._env, SystemEnv):
            self.reset_env()
        assert self._env is not None
        return self._env

    @property
    def default_group(self) -> str:
        return self.ADDITIONAL_PACKAGE_GROUP

    @property
    def activated_groups(self) -> set[str]:
        return {self.default_group}

    def generate_system_pyproject(self) -> None:
        preserved = {}

        if self.system_pyproject.exists():
            content = PyProjectTOML(self.system_pyproject).poetry_config

            for key in {"group", "source"}:
                if key in content:
                    preserved[key] = content[key]

        package = ProjectPackage(name="poetry-instance", version=__version__)
        package.add_dependency(Dependency(name="poetry", constraint=f"{__version__}"))

        package.python_versions = ".".join(str(v) for v in self.env.version_info[:3])

        content = Factory.create_pyproject_from_package(package=package)

        for key in preserved:
            content["tool"]["poetry"][key] = preserved[key]  # type: ignore[index]

        pyproject = PyProjectTOML(self.system_pyproject)
        pyproject.file.write(content)

    def reset_poetry(self) -> None:
        with directory(self.system_pyproject.parent):
            self.generate_system_pyproject()
            self._poetry = Factory().create_poetry(
                self.system_pyproject.parent, io=self.io, disable_plugins=True
            )

    @property
    def poetry(self) -> Poetry:
        if self._poetry is None:
            self.reset_poetry()

        assert self._poetry is not None
        return self._poetry

    def _system_project_handle(self) -> int:
        """
        This is a helper method that by default calls the handle method implemented in
        the child class's next MRO sibling. Override this if you want special handling
        either before calling the handle() from the super class or have custom logic
        to handle the command.

        The default implementations handles cases where a `self` command delegates
        handling to an existing command. Eg: `SelfAddCommand(SelfCommand, AddCommand)`.
        """
        return_code: int = super().handle()
        return return_code

    def reset(self) -> None:
        """
        Reset current command instance's environment and poetry instances to ensure
        use of the system specific ones.
        """
        self.reset_env()
        self.reset_poetry()

    def handle(self) -> int:
        # We override the base class's handle() method to ensure that poetry and env
        # are reset to work within the system project instead of current context.
        # Further, during execution, the working directory is temporarily changed
        # to parent directory of Poetry system pyproject.toml file.
        #
        # This method **should not** be overridden in child classes as it may have
        # unexpected consequences.

        self.reset()

        with directory(self.system_pyproject.parent):
            return self._system_project_handle()
