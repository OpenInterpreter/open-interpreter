from __future__ import absolute_import
from __future__ import unicode_literals

from typing import Dict
from typing import Optional

from clikit.api.io.io import IO

from poetry.core.factory import Factory as BaseFactory
from poetry.core.toml.file import TOMLFile

from .config.config import Config
from .config.file_config_source import FileConfigSource
from .io.null_io import NullIO
from .locations import CONFIG_DIR
from .packages.locker import Locker
from .poetry import Poetry
from .repositories.pypi_repository import PyPiRepository
from .utils._compat import Path


class Factory(BaseFactory):
    """
    Factory class to create various elements needed by Poetry.
    """

    def create_poetry(
        self, cwd=None, io=None
    ):  # type: (Optional[Path], Optional[IO]) -> Poetry
        if io is None:
            io = NullIO()

        base_poetry = super(Factory, self).create_poetry(cwd)

        locker = Locker(
            base_poetry.file.parent / "poetry.lock", base_poetry.local_config
        )

        # Loading global configuration
        config = self.create_config(io)

        # Loading local configuration
        local_config_file = TOMLFile(base_poetry.file.parent / "poetry.toml")
        if local_config_file.exists():
            if io.is_debug():
                io.write_line(
                    "Loading configuration file {}".format(local_config_file.path)
                )

            config.merge(local_config_file.read())

        # Load local sources
        repositories = {}
        existing_repositories = config.get("repositories", {})
        for source in base_poetry.pyproject.poetry_config.get("source", []):
            name = source.get("name")
            url = source.get("url")
            if name and url:
                if name not in existing_repositories:
                    repositories[name] = {"url": url}

        config.merge({"repositories": repositories})

        poetry = Poetry(
            base_poetry.file.path,
            base_poetry.local_config,
            base_poetry.package,
            locker,
            config,
        )

        # Configuring sources
        sources = poetry.local_config.get("source", [])
        for source in sources:
            repository = self.create_legacy_repository(source, config)
            is_default = source.get("default", False)
            is_secondary = source.get("secondary", False)
            if io.is_debug():
                message = "Adding repository {} ({})".format(
                    repository.name, repository.url
                )
                if is_default:
                    message += " and setting it as the default one"
                elif is_secondary:
                    message += " and setting it as secondary"

                io.write_line(message)

            poetry.pool.add_repository(repository, is_default, secondary=is_secondary)

        # Put PyPI last to prefer private repositories
        # unless we have no default source AND no primary sources
        # (default = false, secondary = false)
        if poetry.pool.has_default():
            if io.is_debug():
                io.write_line("Deactivating the PyPI repository")
        else:
            default = not poetry.pool.has_primary_repositories()
            poetry.pool.add_repository(PyPiRepository(config=poetry.config), default, not default)

        return poetry

    @classmethod
    def create_config(cls, io=None):  # type: (Optional[IO]) -> Config
        if io is None:
            io = NullIO()

        config = Config()
        # Load global config
        config_file = TOMLFile(Path(CONFIG_DIR) / "config.toml")
        if config_file.exists():
            if io.is_debug():
                io.write_line(
                    "<debug>Loading configuration file {}</debug>".format(
                        config_file.path
                    )
                )

            config.merge(config_file.read())

        config.set_config_source(FileConfigSource(config_file))

        # Load global auth config
        auth_config_file = TOMLFile(Path(CONFIG_DIR) / "auth.toml")
        if auth_config_file.exists():
            if io.is_debug():
                io.write_line(
                    "<debug>Loading configuration file {}</debug>".format(
                        auth_config_file.path
                    )
                )

            config.merge(auth_config_file.read())

        config.set_auth_config_source(FileConfigSource(auth_config_file))

        return config

    def create_legacy_repository(
        self, source, auth_config
    ):  # type: (Dict[str, str], Config) -> LegacyRepository
        from .repositories.legacy_repository import LegacyRepository
        from .utils.helpers import get_cert
        from .utils.helpers import get_client_cert

        if "url" in source:
            # PyPI-like repository
            if "name" not in source:
                raise RuntimeError("Missing [name] in source.")
        else:
            raise RuntimeError("Unsupported source specified")

        name = source["name"]
        url = source["url"]

        return LegacyRepository(
            name,
            url,
            config=auth_config,
            cert=get_cert(auth_config, name),
            client_cert=get_client_cert(auth_config, name),
        )
