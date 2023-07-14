from __future__ import annotations

import logging
import os
import sys

from pathlib import Path

from platformdirs import user_cache_path
from platformdirs import user_config_path
from platformdirs import user_data_path


logger = logging.getLogger(__name__)

_APP_NAME = "pypoetry"

DEFAULT_CACHE_DIR = user_cache_path(_APP_NAME, appauthor=False)
CONFIG_DIR = Path(
    os.getenv("POETRY_CONFIG_DIR")
    or user_config_path(_APP_NAME, appauthor=False, roaming=True)
)

# platformdirs 2.0.0 corrected the OSX/macOS config directory from
# /Users/<user>/Library/Application Support/<appname> to
# /Users/<user>/Library/Preferences/<appname>.
#
# Then platformdirs 3.0.0 corrected it back again!
#
# Treat Preferences as deprecated, and hope that this is finally decided.
if sys.platform == "darwin":
    _LEGACY_CONFIG_DIR = CONFIG_DIR.parent.parent / "Preferences" / _APP_NAME
    config_toml = _LEGACY_CONFIG_DIR / "config.toml"
    auth_toml = _LEGACY_CONFIG_DIR / "auth.toml"

    if any(file.exists() for file in (auth_toml, config_toml)):
        logger.warning(
            (
                "Configuration file exists at %s, reusing this"
                " directory.\n\nConsider moving TOML configuration files to %s, as"
                " support for the legacy directory will be removed in an upcoming"
                " release."
            ),
            _LEGACY_CONFIG_DIR,
            CONFIG_DIR,
        )
        CONFIG_DIR = _LEGACY_CONFIG_DIR


def data_dir() -> Path:
    poetry_home = os.getenv("POETRY_HOME")
    if poetry_home:
        return Path(poetry_home).expanduser()

    return user_data_path(_APP_NAME, appauthor=False, roaming=True)
