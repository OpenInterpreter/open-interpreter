from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from poetry.plugins.application_plugin import ApplicationPlugin
from poetry.plugins.plugin import Plugin
from poetry.utils._compat import metadata


if TYPE_CHECKING:
    from typing import Any

    from poetry.utils.env import Env


logger = logging.getLogger(__name__)


class PluginManager:
    """
    This class registers and activates plugins.
    """

    def __init__(self, group: str, disable_plugins: bool = False) -> None:
        self._group = group
        self._disable_plugins = disable_plugins
        self._plugins: list[Plugin] = []

    def load_plugins(self, env: Env | None = None) -> None:
        if self._disable_plugins:
            return

        plugin_entrypoints = self.get_plugin_entry_points(env=env)

        for ep in plugin_entrypoints:
            self._load_plugin_entry_point(ep)

    @staticmethod
    def _is_plugin_candidate(ep: metadata.EntryPoint, env: Env | None = None) -> bool:
        """
        Helper method to check if given entry point is a valid as a plugin candidate.
        When an environment is specified, the entry point's associated distribution
        should be installed, and discoverable in the given environment.
        """
        return env is None or (
            ep.dist is not None
            and env.site_packages.find_distribution(ep.dist.name) is not None
        )

    def get_plugin_entry_points(
        self, env: Env | None = None
    ) -> list[metadata.EntryPoint]:
        return [
            ep
            for ep in metadata.entry_points(group=self._group)
            if self._is_plugin_candidate(ep, env)
        ]

    def add_plugin(self, plugin: Plugin) -> None:
        if not isinstance(plugin, (Plugin, ApplicationPlugin)):
            raise ValueError(
                "The Poetry plugin must be an instance of Plugin or ApplicationPlugin"
            )

        self._plugins.append(plugin)

    def activate(self, *args: Any, **kwargs: Any) -> None:
        for plugin in self._plugins:
            plugin.activate(*args, **kwargs)

    def _load_plugin_entry_point(self, ep: metadata.EntryPoint) -> None:
        logger.debug("Loading the %s plugin", ep.name)

        plugin = ep.load()  # type: ignore[no-untyped-call]

        if not issubclass(plugin, (Plugin, ApplicationPlugin)):
            raise ValueError(
                "The Poetry plugin must be an instance of Plugin or ApplicationPlugin"
            )

        self.add_plugin(plugin())
