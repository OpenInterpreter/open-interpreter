from __future__ import annotations

from cleo.helpers import option

from poetry.console.commands.installer_command import InstallerCommand


class InstallCommand(InstallerCommand):
    name = "install"
    description = "Installs the project dependencies."

    options = [
        *InstallerCommand._group_dependency_options(),
        option(
            "no-dev",
            None,
            (
                "Do not install the development dependencies."
                " (<warning>Deprecated</warning>)"
            ),
        ),
        option(
            "sync",
            None,
            (
                "Synchronize the environment with the locked packages and the specified"
                " groups."
            ),
        ),
        option(
            "no-root", None, "Do not install the root package (the current project)."
        ),
        option(
            "no-directory",
            None,
            (
                "Do not install any directory path dependencies; useful to install"
                " dependencies without source code, e.g. for caching of Docker layers)"
            ),
            flag=True,
            multiple=False,
        ),
        option(
            "dry-run",
            None,
            (
                "Output the operations but do not execute anything "
                "(implicitly enables --verbose)."
            ),
        ),
        option(
            "remove-untracked",
            None,
            (
                "Removes packages not present in the lock file."
                " (<warning>Deprecated</warning>)"
            ),
        ),
        option(
            "extras",
            "E",
            "Extra sets of dependencies to install.",
            flag=False,
            multiple=True,
        ),
        option("all-extras", None, "Install all extra dependencies."),
        option("only-root", None, "Exclude all dependencies."),
        option(
            "compile",
            None,
            (
                "Compile Python source files to bytecode."
                " (This option has no effect if modern-installation is disabled"
                " because the old installer always compiles.)"
            ),
        ),
    ]

    help = """\
The <info>install</info> command reads the <comment>poetry.lock</> file from
the current directory, processes it, and downloads and installs all the
libraries and dependencies outlined in that file. If the file does not
exist it will look for <comment>pyproject.toml</> and do the same.

<info>poetry install</info>

By default, the above command will also install the current project. To install only the
dependencies and not including the current project, run the command with the
<info>--no-root</info> option like below:

<info> poetry install --no-root</info>
"""

    _loggers = ["poetry.repositories.pypi_repository", "poetry.inspection.info"]

    @property
    def activated_groups(self) -> set[str]:
        if self.option("only-root"):
            return set()
        else:
            return super().activated_groups

    def handle(self) -> int:
        from poetry.core.masonry.utils.module import ModuleOrPackageNotFound

        from poetry.masonry.builders.editable import EditableBuilder

        if self.option("extras") and self.option("all-extras"):
            self.line_error(
                "<error>You cannot specify explicit"
                " `<fg=yellow;options=bold>--extras</>` while installing"
                " using `<fg=yellow;options=bold>--all-extras</>`.</error>"
            )
            return 1

        if self.option("only-root") and any(
            self.option(key) for key in {"with", "without", "only"}
        ):
            self.line_error(
                "<error>The `<fg=yellow;options=bold>--with</>`,"
                " `<fg=yellow;options=bold>--without</>` and"
                " `<fg=yellow;options=bold>--only</>` options cannot be used with"
                " the `<fg=yellow;options=bold>--only-root</>`"
                " option.</error>"
            )
            return 1

        if self.option("only-root") and self.option("no-root"):
            self.line_error(
                "<error>You cannot specify `<fg=yellow;options=bold>--no-root</>`"
                " when using `<fg=yellow;options=bold>--only-root</>`.</error>"
            )
            return 1

        extras: list[str]
        if self.option("all-extras"):
            extras = list(self.poetry.package.extras.keys())
        else:
            extras = []
            for extra in self.option("extras", []):
                extras += extra.split()

        self.installer.extras(extras)

        with_synchronization = self.option("sync")
        if self.option("remove-untracked"):
            self.line_error(
                "<warning>The `<fg=yellow;options=bold>--remove-untracked</>` option is"
                " deprecated, use the `<fg=yellow;options=bold>--sync</>` option"
                " instead.</warning>"
            )

            with_synchronization = True

        self.installer.only_groups(self.activated_groups)
        self.installer.skip_directory(self.option("no-directory"))
        self.installer.dry_run(self.option("dry-run"))
        self.installer.requires_synchronization(with_synchronization)
        self.installer.executor.enable_bytecode_compilation(self.option("compile"))
        self.installer.verbose(self.io.is_verbose())

        return_code = self.installer.run()

        if return_code != 0:
            return return_code

        if self.option("no-root"):
            return 0

        try:
            builder = EditableBuilder(self.poetry, self.env, self.io)
        except ModuleOrPackageNotFound:
            # This is likely due to the fact that the project is an application
            # not following the structure expected by Poetry
            # If this is a true error it will be picked up later by build anyway.
            return 0

        log_install = (
            "<b>Installing</> the current project:"
            f" <c1>{self.poetry.package.pretty_name}</c1>"
            f" (<{{tag}}>{self.poetry.package.pretty_version}</>)"
        )
        overwrite = self.io.output.is_decorated() and not self.io.is_debug()
        self.line("")
        self.write(log_install.format(tag="c2"))
        if not overwrite:
            self.line("")

        if self.option("dry-run"):
            self.line("")
            return 0

        builder.build()

        if overwrite:
            self.overwrite(log_install.format(tag="success"))
            self.line("")

        return 0
