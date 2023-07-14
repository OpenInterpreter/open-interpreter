"""Source for pytool.toml files."""
from __future__ import annotations

from pathlib import Path

from .pyproject import PyProject


class PyTool(PyProject):
    """Source for pytool.toml files.

    Uses platformdirs to find configuration directories.
    """

    description: str

    def __init__(self, tool: str):
        """Initialize the TOML configuration.

        :param tool: name of your tool. Will read configuration from [tool.yourtool]
        """
        import platformdirs

        self.file = Path(platformdirs.user_config_dir()) / "pytool.toml"
        self.name = "pytool.toml"
        self.tool = tool
        self.description = rf"""
        The pytool.toml file is found at

        Mac OS X:               ~/Library/Application Support/pytool.toml
        Unix:                   ~/.config/pytool.toml     # or in $XDG_CONFIG_HOME, if defined
        Win *:                  C:\Users\<username>\AppData\Local\pytool.toml
        It is configured in the same fashion as your pyproject.toml.
        Configuration for {tool} is found in the [tool.{tool}] table.
        """
