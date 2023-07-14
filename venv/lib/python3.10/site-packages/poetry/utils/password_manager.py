from __future__ import annotations

import dataclasses
import logging

from contextlib import suppress
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from poetry.config.config import Config

logger = logging.getLogger(__name__)


class PasswordManagerError(Exception):
    pass


class PoetryKeyringError(Exception):
    pass


@dataclasses.dataclass
class HTTPAuthCredential:
    username: str | None = dataclasses.field(default=None)
    password: str | None = dataclasses.field(default=None)


class PoetryKeyring:
    def __init__(self, namespace: str) -> None:
        self._namespace = namespace
        self._is_available = True

        self._check()

    def is_available(self) -> bool:
        return self._is_available

    def get_credential(
        self, *names: str, username: str | None = None
    ) -> HTTPAuthCredential:
        default = HTTPAuthCredential(username=username, password=None)

        if not self.is_available():
            return default

        import keyring

        for name in names:
            credential = keyring.get_credential(name, username)
            if credential:
                return HTTPAuthCredential(
                    username=credential.username, password=credential.password
                )

        return default

    def get_password(self, name: str, username: str) -> str | None:
        if not self.is_available():
            return None

        import keyring
        import keyring.errors

        name = self.get_entry_name(name)

        try:
            return keyring.get_password(name, username)
        except (RuntimeError, keyring.errors.KeyringError):
            raise PoetryKeyringError(
                f"Unable to retrieve the password for {name} from the key ring"
            )

    def set_password(self, name: str, username: str, password: str) -> None:
        if not self.is_available():
            return

        import keyring
        import keyring.errors

        name = self.get_entry_name(name)

        try:
            keyring.set_password(name, username, password)
        except (RuntimeError, keyring.errors.KeyringError) as e:
            raise PoetryKeyringError(
                f"Unable to store the password for {name} in the key ring: {e}"
            )

    def delete_password(self, name: str, username: str) -> None:
        if not self.is_available():
            return

        import keyring.errors

        name = self.get_entry_name(name)

        try:
            keyring.delete_password(name, username)
        except (RuntimeError, keyring.errors.KeyringError):
            raise PoetryKeyringError(
                f"Unable to delete the password for {name} from the key ring"
            )

    def get_entry_name(self, name: str) -> str:
        return f"{self._namespace}-{name}"

    def _check(self) -> None:
        try:
            import keyring
        except ImportError as e:
            logger.debug("An error occurred while importing keyring: %s", e)
            self._is_available = False

            return

        backend = keyring.get_keyring()
        name = backend.name.split(" ")[0]
        if name in ("fail", "null"):
            logger.debug("No suitable keyring backend found")
            self._is_available = False
        elif "plaintext" in backend.name.lower():
            logger.debug("Only a plaintext keyring backend is available. Not using it.")
            self._is_available = False
        elif name == "chainer":
            try:
                import keyring.backend

                backends = keyring.backend.get_all_keyring()

                self._is_available = any(
                    b.name.split(" ")[0] not in ["chainer", "fail", "null"]
                    and "plaintext" not in b.name.lower()
                    for b in backends
                )
            except ImportError:
                self._is_available = False

        if not self._is_available:
            logger.debug("No suitable keyring backends were found")


class PasswordManager:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._keyring: PoetryKeyring | None = None

    @property
    def keyring(self) -> PoetryKeyring:
        if self._keyring is None:
            self._keyring = PoetryKeyring("poetry-repository")

            if not self._keyring.is_available():
                logger.debug(
                    "<warning>Keyring is not available, credentials will be stored and "
                    "retrieved from configuration files as plaintext.</>"
                )

        return self._keyring

    @staticmethod
    def warn_plaintext_credentials_stored() -> None:
        logger.warning("Using a plaintext file to store credentials")

    def set_pypi_token(self, name: str, token: str) -> None:
        if not self.keyring.is_available():
            self.warn_plaintext_credentials_stored()
            self._config.auth_config_source.add_property(f"pypi-token.{name}", token)
        else:
            self.keyring.set_password(name, "__token__", token)

    def get_pypi_token(self, repo_name: str) -> str | None:
        """Get PyPi token.

        First checks the environment variables for a token,
        then the configured username/password and the
        available keyring.

        :param repo_name:  Name of repository.
        :return: Returns a token as a string if found, otherwise None.
        """
        token: str | None = self._config.get(f"pypi-token.{repo_name}")
        if token:
            return token

        return self.keyring.get_password(repo_name, "__token__")

    def delete_pypi_token(self, name: str) -> None:
        if not self.keyring.is_available():
            return self._config.auth_config_source.remove_property(f"pypi-token.{name}")

        self.keyring.delete_password(name, "__token__")

    def get_http_auth(self, name: str) -> dict[str, str | None] | None:
        username = self._config.get(f"http-basic.{name}.username")
        password = self._config.get(f"http-basic.{name}.password")
        if not username and not password:
            return None

        if not password:
            password = self.keyring.get_password(name, username)

        return {
            "username": username,
            "password": password,
        }

    def set_http_password(self, name: str, username: str, password: str) -> None:
        auth = {"username": username}

        if not self.keyring.is_available():
            self.warn_plaintext_credentials_stored()
            auth["password"] = password
        else:
            self.keyring.set_password(name, username, password)

        self._config.auth_config_source.add_property(f"http-basic.{name}", auth)

    def delete_http_password(self, name: str) -> None:
        auth = self.get_http_auth(name)
        if not auth:
            return

        username = auth.get("username")
        if username is None:
            return

        with suppress(PoetryKeyringError):
            self.keyring.delete_password(name, username)

        self._config.auth_config_source.remove_property(f"http-basic.{name}")
