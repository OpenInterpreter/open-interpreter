from __future__ import annotations

from typing import Any

from cleo.helpers import argument
from cleo.helpers import option
from packaging.utils import canonicalize_name
from poetry.core.packages.dependency_group import MAIN_GROUP
from tomlkit.toml_document import TOMLDocument

from poetry.console.commands.installer_command import InstallerCommand


class RemoveCommand(InstallerCommand):
    name = "remove"
    description = "Removes a package from the project dependencies."

    arguments = [argument("packages", "The packages to remove.", multiple=True)]
    options = [
        option("group", "G", "The group to remove the dependency from.", flag=False),
        option(
            "dev",
            "D",
            (
                "Remove a package from the development dependencies."
                " (<warning>Deprecated</warning>)"
                " Use --group=dev instead."
            ),
        ),
        option(
            "dry-run",
            None,
            (
                "Output the operations but do not execute anything "
                "(implicitly enables --verbose)."
            ),
        ),
        option("lock", None, "Do not perform operations (only update the lockfile)."),
    ]

    help = """The <info>remove</info> command removes a package from the current
list of installed packages

<info>poetry remove</info>"""

    loggers = ["poetry.repositories.pypi_repository", "poetry.inspection.info"]

    def handle(self) -> int:
        packages = self.argument("packages")

        if self.option("dev"):
            self.line_error(
                "<warning>The --dev option is deprecated, "
                "use the `--group dev` notation instead.</warning>"
            )
            group = "dev"
        else:
            group = self.option("group", self.default_group)

        content: dict[str, Any] = self.poetry.file.read()
        poetry_content = content["tool"]["poetry"]

        if group is None:
            removed = []
            group_sections = [
                (group_name, group_section.get("dependencies", {}))
                for group_name, group_section in poetry_content.get("group", {}).items()
            ]

            for group_name, section in [
                (MAIN_GROUP, poetry_content["dependencies"]),
                *group_sections,
            ]:
                removed += self._remove_packages(packages, section, group_name)
                if group_name != MAIN_GROUP:
                    if not section:
                        del poetry_content["group"][group_name]
                    else:
                        poetry_content["group"][group_name]["dependencies"] = section
        elif group == "dev" and "dev-dependencies" in poetry_content:
            # We need to account for the old `dev-dependencies` section
            removed = self._remove_packages(
                packages, poetry_content["dev-dependencies"], "dev"
            )

            if not poetry_content["dev-dependencies"]:
                del poetry_content["dev-dependencies"]
        else:
            removed = []
            if "group" in poetry_content:
                if group in poetry_content["group"]:
                    removed = self._remove_packages(
                        packages,
                        poetry_content["group"][group].get("dependencies", {}),
                        group,
                    )

                if not poetry_content["group"][group]:
                    del poetry_content["group"][group]

        if "group" in poetry_content and not poetry_content["group"]:
            del poetry_content["group"]

        removed_set = set(removed)
        not_found = set(packages).difference(removed_set)
        if not_found:
            raise ValueError(
                "The following packages were not found: " + ", ".join(sorted(not_found))
            )

        # Refresh the locker
        self.poetry.locker.set_local_config(poetry_content)
        self.installer.set_locker(self.poetry.locker)
        self.installer.set_package(self.poetry.package)
        self.installer.dry_run(self.option("dry-run", False))
        self.installer.verbose(self.io.is_verbose())
        self.installer.update(True)
        self.installer.execute_operations(not self.option("lock"))
        self.installer.whitelist(removed_set)

        status = self.installer.run()

        if not self.option("dry-run") and status == 0:
            assert isinstance(content, TOMLDocument)
            self.poetry.file.write(content)

        return status

    def _remove_packages(
        self, packages: list[str], section: dict[str, Any], group_name: str
    ) -> list[str]:
        removed = []
        group = self.poetry.package.dependency_group(group_name)
        section_keys = list(section.keys())

        for package in packages:
            for existing_package in section_keys:
                if canonicalize_name(existing_package) == canonicalize_name(package):
                    del section[existing_package]
                    removed.append(package)
                    group.remove_dependency(package)

        return removed
