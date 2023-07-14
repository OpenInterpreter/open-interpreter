from __future__ import annotations

from poetry.core.constraints.version import Version

from poetry.__version__ import __version__
from poetry.console.commands.add import AddCommand
from poetry.console.commands.self.self_command import SelfCommand


class SelfAddCommand(SelfCommand, AddCommand):
    name = "self add"
    description = "Add additional packages to Poetry's runtime environment."
    options = [
        o
        for o in AddCommand.options
        if o.name in {"editable", "extras", "source", "dry-run", "allow-prereleases"}
    ]
    help = f"""\
The <c1>self add</c1> command installs additional packages to Poetry's runtime \
environment.

This is managed in the <comment>{SelfCommand.get_default_system_pyproject_file()}</> \
file.

{AddCommand.examples}
"""

    @property
    def _hint_update_packages(self) -> str:
        version = Version.parse(__version__)
        flags = ""

        if not version.is_stable():
            flags = " --preview"

        return (
            "\nIf you want to update it to the latest compatible version, you can use"
            f" `poetry self update{flags}`.\nIf you prefer to upgrade it to the latest"
            " available version, you can use `poetry self add package@latest`.\n"
        )
