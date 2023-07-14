from __future__ import annotations

from contextlib import suppress

from cleo.helpers import argument
from cleo.helpers import option

from poetry.console.commands.command import Command


class NewCommand(Command):
    name = "new"
    description = "Creates a new Python project at <path>."

    arguments = [argument("path", "The path to create the project at.")]
    options = [
        option("name", None, "Set the resulting package name.", flag=False),
        option("src", None, "Use the src layout for the project."),
        option(
            "readme",
            None,
            "Specify the readme file format. One of md (default) or rst",
            flag=False,
        ),
    ]

    def handle(self) -> int:
        from pathlib import Path

        from poetry.core.vcs.git import GitConfig

        from poetry.config.config import Config
        from poetry.layouts import layout
        from poetry.utils.env import EnvManager

        if self.io.input.option("directory"):
            self.line_error(
                "<warning>--directory only makes sense with existing projects, and will"
                " be ignored. You should consider the option --path instead.</warning>"
            )

        layout_cls = layout("src") if self.option("src") else layout("standard")

        path = Path(self.argument("path"))
        if not path.is_absolute():
            # we do not use resolve here due to compatibility issues
            # for path.resolve(strict=False)
            path = Path.cwd().joinpath(path)

        name = self.option("name")
        if not name:
            name = path.name

        if path.exists() and list(path.glob("*")):
            # Directory is not empty. Aborting.
            raise RuntimeError(
                f"Destination <fg=yellow>{path}</> exists and is not empty"
            )

        readme_format = self.option("readme") or "md"

        config = GitConfig()
        author = None
        if config.get("user.name"):
            author = config["user.name"]
            author_email = config.get("user.email")
            if author_email:
                author += f" <{author_email}>"

        poetry_config = Config.create()
        default_python = (
            "^"
            + EnvManager.get_python_version(
                precision=2,
                prefer_active_python=poetry_config.get(
                    "virtualenvs.prefer-active-python"
                ),
                io=self.io,
            ).to_string()
        )

        layout_ = layout_cls(
            name,
            "0.1.0",
            author=author,
            readme_format=readme_format,
            python=default_python,
        )
        layout_.create(path)

        path = path.resolve()

        with suppress(ValueError):
            path = path.relative_to(Path.cwd())

        self.line(
            f"Created package <info>{layout_._package_name}</> in"
            f" <fg=blue>{path.as_posix()}</>"
        )

        return 0
