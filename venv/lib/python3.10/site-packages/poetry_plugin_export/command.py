from __future__ import annotations

from pathlib import Path

from cleo.helpers import option
from packaging.utils import canonicalize_name
from poetry.console.commands.group_command import GroupCommand
from poetry.core.packages.dependency_group import MAIN_GROUP

from poetry_plugin_export.exporter import Exporter


class ExportCommand(GroupCommand):
    name = "export"
    description = "Exports the lock file to alternative formats."

    options = [
        option(
            "format",
            "f",
            (
                "Format to export to. Currently, only constraints.txt and"
                " requirements.txt are supported."
            ),
            flag=False,
            default=Exporter.FORMAT_REQUIREMENTS_TXT,
        ),
        option("output", "o", "The name of the output file.", flag=False),
        option("without-hashes", None, "Exclude hashes from the exported file."),
        option(
            "without-urls",
            None,
            "Exclude source repository urls from the exported file.",
        ),
        option(
            "dev",
            None,
            "Include development dependencies. (<warning>Deprecated</warning>)",
        ),
        *GroupCommand._group_dependency_options(),
        option(
            "extras",
            "E",
            "Extra sets of dependencies to include.",
            flag=False,
            multiple=True,
        ),
        option("with-credentials", None, "Include credentials for extra indices."),
    ]

    @property
    def non_optional_groups(self) -> set[str]:
        # method only required for poetry <= 1.2.0-beta.2.dev0
        return {MAIN_GROUP}

    @property
    def default_groups(self) -> set[str]:
        return {MAIN_GROUP}

    def handle(self) -> int:
        fmt = self.option("format")

        if not Exporter.is_format_supported(fmt):
            raise ValueError(f"Invalid export format: {fmt}")

        output = self.option("output")

        locker = self.poetry.locker
        if not locker.is_locked():
            self.line_error("<comment>The lock file does not exist. Locking.</comment>")
            options = []
            if self.io.is_debug():
                options.append(("-vvv", None))
            elif self.io.is_very_verbose():
                options.append(("-vv", None))
            elif self.io.is_verbose():
                options.append(("-v", None))

            self.call("lock", " ".join(options))  # type: ignore[arg-type]

        if not locker.is_fresh():
            self.line_error(
                "<warning>"
                "Warning: The lock file is not up to date with "
                "the latest changes in pyproject.toml. "
                "You may be getting outdated dependencies. "
                "Run update to update them."
                "</warning>"
            )

        # Checking extras
        extras = {
            canonicalize_name(extra)
            for extra_opt in self.option("extras")
            for extra in extra_opt.split()
        }
        invalid_extras = extras - self.poetry.package.extras.keys()
        if invalid_extras:
            raise ValueError(
                f"Extra [{', '.join(sorted(invalid_extras))}] is not specified."
            )

        exporter = Exporter(self.poetry, self.io)
        exporter.only_groups(list(self.activated_groups))
        exporter.with_extras(list(extras))
        exporter.with_hashes(not self.option("without-hashes"))
        exporter.with_credentials(self.option("with-credentials"))
        exporter.with_urls(not self.option("without-urls"))
        exporter.export(fmt, Path.cwd(), output or self.io)

        return 0
