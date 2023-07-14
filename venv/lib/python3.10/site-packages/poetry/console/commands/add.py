from __future__ import annotations

import contextlib

from typing import Any

from cleo.helpers import argument
from cleo.helpers import option
from packaging.utils import canonicalize_name
from poetry.core.packages.dependency_group import MAIN_GROUP
from tomlkit.toml_document import TOMLDocument

from poetry.console.commands.init import InitCommand
from poetry.console.commands.installer_command import InstallerCommand


class AddCommand(InstallerCommand, InitCommand):
    name = "add"
    description = "Adds a new dependency to <comment>pyproject.toml</>."

    arguments = [argument("name", "The packages to add.", multiple=True)]
    options = [
        option(
            "group",
            "-G",
            "The group to add the dependency to.",
            flag=False,
            default=MAIN_GROUP,
        ),
        option(
            "dev",
            "D",
            (
                "Add as a development dependency. (<warning>Deprecated</warning>) Use"
                " --group=dev instead."
            ),
        ),
        option("editable", "e", "Add vcs/path dependencies as editable."),
        option(
            "extras",
            "E",
            "Extras to activate for the dependency.",
            flag=False,
            multiple=True,
        ),
        option("optional", None, "Add as an optional dependency."),
        option(
            "python",
            None,
            "Python version for which the dependency must be installed.",
            flag=False,
        ),
        option(
            "platform",
            None,
            "Platforms for which the dependency must be installed.",
            flag=False,
        ),
        option(
            "source",
            None,
            "Name of the source to use to install the package.",
            flag=False,
        ),
        option("allow-prereleases", None, "Accept prereleases."),
        option(
            "dry-run",
            None,
            (
                "Output the operations but do not execute anything (implicitly enables"
                " --verbose)."
            ),
        ),
        option("lock", None, "Do not perform operations (only update the lockfile)."),
    ]
    examples = """\
If you do not specify a version constraint, poetry will choose a suitable one based on\
 the available package versions.

You can specify a package in the following forms:
  - A single name (<b>requests</b>)
  - A name and a constraint (<b>requests@^2.23.0</b>)
  - A git url (<b>git+https://github.com/python-poetry/poetry.git</b>)
  - A git url with a revision\
 (<b>git+https://github.com/python-poetry/poetry.git#develop</b>)
  - A git SSH url (<b>git+ssh://github.com/python-poetry/poetry.git</b>)
  - A git SSH url with a revision\
 (<b>git+ssh://github.com/python-poetry/poetry.git#develop</b>)
  - A file path (<b>../my-package/my-package.whl</b>)
  - A directory (<b>../my-package/</b>)
  - A url (<b>https://example.com/packages/my-package-0.1.0.tar.gz</b>)
"""
    help = f"""\
The add command adds required packages to your <comment>pyproject.toml</> and installs\
 them.

{examples}
"""

    loggers = ["poetry.repositories.pypi_repository", "poetry.inspection.info"]

    def handle(self) -> int:
        from poetry.core.constraints.version import parse_constraint
        from tomlkit import inline_table
        from tomlkit import parse as parse_toml
        from tomlkit import table

        from poetry.factory import Factory

        packages = self.argument("name")
        if self.option("dev"):
            self.line_error(
                "<warning>The --dev option is deprecated, "
                "use the `--group dev` notation instead.</warning>"
            )
            group = "dev"
        else:
            group = self.option("group", self.default_group or MAIN_GROUP)

        if self.option("extras") and len(packages) > 1:
            raise ValueError(
                "You can only specify one package when using the --extras option"
            )

        # tomlkit types are awkward to work with, treat content as a mostly untyped
        # dictionary.
        content: dict[str, Any] = self.poetry.file.read()
        poetry_content = content["tool"]["poetry"]
        project_name = canonicalize_name(poetry_content["name"])

        if group == MAIN_GROUP:
            if "dependencies" not in poetry_content:
                poetry_content["dependencies"] = table()

            section = poetry_content["dependencies"]
        else:
            if "group" not in poetry_content:
                poetry_content["group"] = table(is_super_table=True)

            groups = poetry_content["group"]
            if group not in groups:
                dependencies_toml: dict[str, Any] = parse_toml(
                    f"[tool.poetry.group.{group}.dependencies]\n\n"
                )
                group_table = dependencies_toml["tool"]["poetry"]["group"][group]
                poetry_content["group"][group] = group_table

            if "dependencies" not in poetry_content["group"][group]:
                poetry_content["group"][group]["dependencies"] = table()

            section = poetry_content["group"][group]["dependencies"]

        existing_packages = self.get_existing_packages_from_input(packages, section)

        if existing_packages:
            self.notify_about_existing_packages(existing_packages)

        packages = [name for name in packages if name not in existing_packages]

        if not packages:
            self.line("Nothing to add.")
            return 0

        requirements = self._determine_requirements(
            packages,
            allow_prereleases=self.option("allow-prereleases"),
            source=self.option("source"),
        )

        for _constraint in requirements:
            version = _constraint.get("version")
            if version is not None:
                # Validate version constraint
                assert isinstance(version, str)
                parse_constraint(version)

            constraint: dict[str, Any] = inline_table()
            for name, value in _constraint.items():
                if name == "name":
                    continue

                constraint[name] = value

            if self.option("optional"):
                constraint["optional"] = True

            if self.option("allow-prereleases"):
                constraint["allow-prereleases"] = True

            if self.option("extras"):
                extras = []
                for extra in self.option("extras"):
                    extras += extra.split()

                constraint["extras"] = extras

            if self.option("editable"):
                if "git" in _constraint or "path" in _constraint:
                    constraint["develop"] = True
                else:
                    self.line_error(
                        "\n"
                        "<error>Failed to add packages. "
                        "Only vcs/path dependencies support editable installs. "
                        f"<c1>{_constraint['name']}</c1> is neither."
                    )
                    self.line_error("\nNo changes were applied.")
                    return 1

            if self.option("python"):
                constraint["python"] = self.option("python")

            if self.option("platform"):
                constraint["platform"] = self.option("platform")

            if self.option("source"):
                constraint["source"] = self.option("source")

            if len(constraint) == 1 and "version" in constraint:
                constraint = constraint["version"]

            constraint_name = _constraint["name"]
            assert isinstance(constraint_name, str)

            canonical_constraint_name = canonicalize_name(constraint_name)

            if canonical_constraint_name == project_name:
                self.line_error(
                    f"<error>Cannot add dependency on <c1>{constraint_name}</c1> to"
                    " project with the same name."
                )
                self.line_error("\nNo changes were applied.")
                return 1

            for key in section:
                if canonicalize_name(key) == canonical_constraint_name:
                    section[key] = constraint
                    break
            else:
                section[constraint_name] = constraint

            with contextlib.suppress(ValueError):
                self.poetry.package.dependency_group(group).remove_dependency(
                    constraint_name
                )

            self.poetry.package.add_dependency(
                Factory.create_dependency(
                    constraint_name,
                    constraint,
                    groups=[group],
                    root_dir=self.poetry.file.path.parent,
                )
            )

        # Refresh the locker
        self.poetry.locker.set_local_config(poetry_content)
        self.installer.set_locker(self.poetry.locker)

        # Cosmetic new line
        self.line("")

        self.installer.set_package(self.poetry.package)
        self.installer.dry_run(self.option("dry-run"))
        self.installer.verbose(self.io.is_verbose())
        self.installer.update(True)
        self.installer.execute_operations(not self.option("lock"))

        self.installer.whitelist([r["name"] for r in requirements])

        status = self.installer.run()

        if status == 0 and not self.option("dry-run"):
            assert isinstance(content, TOMLDocument)
            self.poetry.file.write(content)

        return status

    def get_existing_packages_from_input(
        self, packages: list[str], section: dict[str, Any]
    ) -> list[str]:
        existing_packages = []

        for name in packages:
            for key in section:
                if canonicalize_name(key) == canonicalize_name(name):
                    existing_packages.append(name)

        return existing_packages

    @property
    def _hint_update_packages(self) -> str:
        return (
            "\nIf you want to update it to the latest compatible version, you can use"
            " `poetry update package`.\nIf you prefer to upgrade it to the latest"
            " available version, you can use `poetry add package@latest`.\n"
        )

    def notify_about_existing_packages(self, existing_packages: list[str]) -> None:
        self.line(
            "The following packages are already present in the pyproject.toml and will"
            " be skipped:\n"
        )
        for name in existing_packages:
            self.line(f"  • <c1>{name}</c1>")
        self.line(self._hint_update_packages)
