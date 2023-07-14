from __future__ import annotations

import dataclasses

from typing import TYPE_CHECKING

from poetry.console.commands.self.self_command import SelfCommand


if TYPE_CHECKING:
    from poetry.core.packages.package import Package

    from poetry.utils._compat import metadata


@dataclasses.dataclass
class PluginPackage:
    package: Package
    plugins: list[metadata.EntryPoint] = dataclasses.field(default_factory=list)
    application_plugins: list[metadata.EntryPoint] = dataclasses.field(
        default_factory=list
    )

    def append(self, entry_point: metadata.EntryPoint) -> None:
        from poetry.plugins.application_plugin import ApplicationPlugin
        from poetry.plugins.plugin import Plugin

        group = entry_point.group

        if group == ApplicationPlugin.group:
            self.application_plugins.append(entry_point)
        elif group == Plugin.group:
            self.plugins.append(entry_point)
        else:
            name = entry_point.name
            raise ValueError(f"Unknown plugin group ({group}) for {name}")


class SelfShowPluginsCommand(SelfCommand):
    name = "self show plugins"
    description = "Shows information about the currently installed plugins."
    help = """\
The <c1>self show plugins</c1> command lists all installed Poetry plugins.

Plugins can be added and removed using the <c1>self add</c1> and <c1>self remove</c1> \
commands respectively.

<warning>This command does not list packages that do not provide a Poetry plugin.</>
"""

    def _system_project_handle(self) -> int:
        from packaging.utils import canonicalize_name

        from poetry.plugins.application_plugin import ApplicationPlugin
        from poetry.plugins.plugin import Plugin
        from poetry.plugins.plugin_manager import PluginManager
        from poetry.repositories.installed_repository import InstalledRepository
        from poetry.utils.env import EnvManager
        from poetry.utils.helpers import pluralize

        plugins: dict[str, PluginPackage] = {}

        system_env = EnvManager.get_system_env(naive=True)
        installed_repository = InstalledRepository.load(
            system_env, with_dependencies=True
        )

        packages_by_name: dict[str, Package] = {
            pkg.name: pkg for pkg in installed_repository.packages
        }

        for group in [ApplicationPlugin.group, Plugin.group]:
            for entry_point in PluginManager(group).get_plugin_entry_points(
                env=system_env
            ):
                assert entry_point.dist is not None

                package = packages_by_name[canonicalize_name(entry_point.dist.name)]

                name = package.pretty_name

                info = plugins.get(name) or PluginPackage(package=package)
                info.append(entry_point)

                plugins[name] = info

        for name, info in plugins.items():
            package = info.package
            description = " " + package.description if package.description else ""
            self.line("")
            self.line(f"  • <c1>{name}</c1> (<c2>{package.version}</c2>){description}")
            provide_line = "     "

            if info.plugins:
                count = len(info.plugins)
                provide_line += f" <info>{count}</info> plugin{pluralize(count)}"

            if info.application_plugins:
                if info.plugins:
                    provide_line += " and"

                count = len(info.application_plugins)
                provide_line += (
                    f" <info>{count}</info> application plugin{pluralize(count)}"
                )

            self.line(provide_line)

            if package.requires:
                self.line("")
                self.line("      <info>Dependencies</info>")
                for dependency in package.requires:
                    self.line(
                        f"        - {dependency.pretty_name}"
                        f" (<c2>{dependency.pretty_constraint}</c2>)"
                    )

        return 0
