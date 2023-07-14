from __future__ import annotations

from cleo.helpers import option

from poetry.console.commands.installer_command import InstallerCommand


class LockCommand(InstallerCommand):
    name = "lock"
    description = "Locks the project dependencies."

    options = [
        option(
            "no-update", None, "Do not update locked versions, only refresh lock file."
        ),
        option(
            "check",
            None,
            (
                "Check that the <comment>poetry.lock</> file corresponds to the current"
                " version of <comment>pyproject.toml</>."
            ),
        ),
    ]

    help = """
The <info>lock</info> command reads the <comment>pyproject.toml</> file from the
current directory, processes it, and locks the dependencies in the\
 <comment>poetry.lock</>
file.

<info>poetry lock</info>
"""

    loggers = ["poetry.repositories.pypi_repository"]

    def handle(self) -> int:
        if self.option("check"):
            if self.poetry.locker.is_locked() and self.poetry.locker.is_fresh():
                self.line("poetry.lock is consistent with pyproject.toml.")
                return 0
            self.line_error(
                "<error>"
                "Error: poetry.lock is not consistent with pyproject.toml. "
                "Run `poetry lock [--no-update]` to fix it."
                "</error>"
            )
            return 1

        self.installer.lock(update=not self.option("no-update"))

        return self.installer.run()
