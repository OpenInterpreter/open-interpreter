from __future__ import annotations

import contextlib
import dataclasses
import functools
import logging
import time
import urllib.parse

from os.path import commonprefix
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import lockfile
import requests
import requests.auth
import requests.exceptions

from cachecontrol import CacheControlAdapter
from cachecontrol.caches import FileCache
from filelock import FileLock

from poetry.config.config import Config
from poetry.exceptions import PoetryException
from poetry.utils.constants import REQUESTS_TIMEOUT
from poetry.utils.constants import RETRY_AFTER_HEADER
from poetry.utils.constants import STATUS_FORCELIST
from poetry.utils.password_manager import HTTPAuthCredential
from poetry.utils.password_manager import PasswordManager


if TYPE_CHECKING:
    from cleo.io.io import IO


logger = logging.getLogger(__name__)


class FileLockLockFile(lockfile.LockBase):  # type: ignore[misc]
    # The default LockFile from the lockfile package as used by cachecontrol can remain
    # locked if a process exits ungracefully.  See eg
    # <https://github.com/python-poetry/poetry/issues/6030#issuecomment-1189383875>.
    #
    # FileLock from the filelock package does not have this problem, so we use that to
    # construct something compatible with cachecontrol.
    def __init__(
        self, path: str, threaded: bool = True, timeout: float | None = None
    ) -> None:
        super().__init__(path, threaded, timeout)
        self.file_lock = FileLock(self.lock_file)

    def acquire(self, timeout: float | None = None) -> None:
        self.file_lock.acquire(timeout=timeout)

    def release(self) -> None:
        self.file_lock.release()


@dataclasses.dataclass(frozen=True)
class RepositoryCertificateConfig:
    cert: Path | None = dataclasses.field(default=None)
    client_cert: Path | None = dataclasses.field(default=None)
    verify: bool = dataclasses.field(default=True)

    @classmethod
    def create(
        cls, repository: str, config: Config | None
    ) -> RepositoryCertificateConfig:
        config = config if config else Config.create()

        verify: str | bool = config.get(
            f"certificates.{repository}.verify",
            config.get(f"certificates.{repository}.cert", True),
        )
        client_cert: str = config.get(f"certificates.{repository}.client-cert")

        return cls(
            cert=Path(verify) if isinstance(verify, str) else None,
            client_cert=Path(client_cert) if client_cert else None,
            verify=verify if isinstance(verify, bool) else True,
        )


@dataclasses.dataclass
class AuthenticatorRepositoryConfig:
    name: str
    url: str
    netloc: str = dataclasses.field(init=False)
    path: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        parsed_url = urllib.parse.urlsplit(self.url)
        self.netloc = parsed_url.netloc
        self.path = parsed_url.path

    def certs(self, config: Config) -> RepositoryCertificateConfig:
        return RepositoryCertificateConfig.create(self.name, config)

    @property
    def http_credential_keys(self) -> list[str]:
        return [self.url, self.netloc, self.name]

    def get_http_credentials(
        self, password_manager: PasswordManager, username: str | None = None
    ) -> HTTPAuthCredential:
        # try with the repository name via the password manager
        credential = HTTPAuthCredential(
            **(password_manager.get_http_auth(self.name) or {})
        )

        if credential.password is None:
            # fallback to url and netloc based keyring entries
            credential = password_manager.keyring.get_credential(
                self.url, self.netloc, username=credential.username
            )

            if credential.password is not None:
                return HTTPAuthCredential(
                    username=credential.username, password=credential.password
                )

        return credential


class Authenticator:
    def __init__(
        self,
        config: Config | None = None,
        io: IO | None = None,
        cache_id: str | None = None,
        disable_cache: bool = False,
        pool_size: int = 10,
    ) -> None:
        self._config = config or Config.create()
        self._io = io
        self._sessions_for_netloc: dict[str, requests.Session] = {}
        self._credentials: dict[str, HTTPAuthCredential] = {}
        self._certs: dict[str, RepositoryCertificateConfig] = {}
        self._configured_repositories: dict[
            str, AuthenticatorRepositoryConfig
        ] | None = None
        self._password_manager = PasswordManager(self._config)
        self._cache_control = (
            FileCache(
                str(
                    self._config.repository_cache_directory
                    / (cache_id or "_default_cache")
                    / "_http"
                ),
                lock_class=FileLockLockFile,
            )
            if not disable_cache
            else None
        )
        self.get_repository_config_for_url = functools.lru_cache(maxsize=None)(
            self._get_repository_config_for_url
        )
        self._pool_size = pool_size

    def create_session(self) -> requests.Session:
        session = requests.Session()

        if self._cache_control is None:
            return session

        adapter = CacheControlAdapter(
            cache=self._cache_control,
            pool_maxsize=self._pool_size,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_session(self, url: str | None = None) -> requests.Session:
        if not url:
            return self.create_session()

        parsed_url = urllib.parse.urlsplit(url)
        netloc = parsed_url.netloc

        if netloc not in self._sessions_for_netloc:
            logger.debug("Creating new session for %s", netloc)
            self._sessions_for_netloc[netloc] = self.create_session()

        return self._sessions_for_netloc[netloc]

    def close(self) -> None:
        for session in self._sessions_for_netloc.values():
            if session is not None:
                with contextlib.suppress(AttributeError):
                    session.close()

    def __del__(self) -> None:
        self.close()

    def delete_cache(self, url: str) -> None:
        if self._cache_control is not None:
            self._cache_control.delete(key=url)

    def authenticated_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        credential = self.get_credentials_for_url(url)

        if credential.username is not None and credential.password is not None:
            username = urllib.parse.quote(credential.username, safe="")
            password = urllib.parse.quote(credential.password, safe="")

            return (
                f"{parsed.scheme}://{username}:{password}@{parsed.netloc}{parsed.path}"
            )

        return url

    def request(
        self, method: str, url: str, raise_for_status: bool = True, **kwargs: Any
    ) -> requests.Response:
        headers = kwargs.get("headers")
        request = requests.Request(method, url, headers=headers)
        credential = self.get_credentials_for_url(url)

        if credential.username is not None or credential.password is not None:
            request = requests.auth.HTTPBasicAuth(
                credential.username or "", credential.password or ""
            )(request)

        session = self.get_session(url=url)
        prepared_request = session.prepare_request(request)

        proxies: dict[str, str] = kwargs.get("proxies", {})
        stream: bool | None = kwargs.get("stream")

        certs = self.get_certs_for_url(url)
        verify: bool | str | Path = kwargs.get("verify") or certs.cert or certs.verify
        cert: str | Path | None = kwargs.get("cert") or certs.client_cert

        if cert is not None:
            cert = str(cert)

        verify = str(verify) if isinstance(verify, Path) else verify

        settings = session.merge_environment_settings(
            prepared_request.url, proxies, stream, verify, cert
        )

        # Send the request.
        send_kwargs = {
            "timeout": kwargs.get("timeout", REQUESTS_TIMEOUT),
            "allow_redirects": kwargs.get("allow_redirects", True),
        }
        send_kwargs.update(settings)

        attempt = 0
        resp = None

        while True:
            is_last_attempt = attempt >= 5
            try:
                resp = session.send(prepared_request, **send_kwargs)
            except (requests.exceptions.ConnectionError, OSError) as e:
                if is_last_attempt:
                    raise e
            else:
                if resp.status_code not in STATUS_FORCELIST or is_last_attempt:
                    if raise_for_status:
                        resp.raise_for_status()
                    return resp

            if not is_last_attempt:
                attempt += 1
                delay = self._get_backoff(resp, attempt)
                logger.debug("Retrying HTTP request in %s seconds.", delay)
                time.sleep(delay)
                continue

        # this should never really be hit under any sane circumstance
        raise PoetryException("Failed HTTP {} request", method.upper())

    def _get_backoff(self, response: requests.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get(RETRY_AFTER_HEADER, "")
            if retry_after:
                return float(retry_after)

        return 0.5 * attempt

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("get", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("post", url, **kwargs)

    def _get_credentials_for_repository(
        self, repository: AuthenticatorRepositoryConfig, username: str | None = None
    ) -> HTTPAuthCredential:
        # cache repository credentials by repository url to avoid multiple keyring
        # backend queries when packages are being downloaded from the same source
        key = f"{repository.url}#username={username or ''}"

        if key not in self._credentials:
            self._credentials[key] = repository.get_http_credentials(
                password_manager=self._password_manager, username=username
            )

        return self._credentials[key]

    def _get_credentials_for_url(
        self, url: str, exact_match: bool = False
    ) -> HTTPAuthCredential:
        repository = self.get_repository_config_for_url(url, exact_match)

        credential = (
            self._get_credentials_for_repository(repository=repository)
            if repository is not None
            else HTTPAuthCredential()
        )

        if credential.password is None:
            parsed_url = urllib.parse.urlsplit(url)
            netloc = parsed_url.netloc
            credential = self._password_manager.keyring.get_credential(
                url, netloc, username=credential.username
            )

            return HTTPAuthCredential(
                username=credential.username, password=credential.password
            )

        return credential

    def get_credentials_for_git_url(self, url: str) -> HTTPAuthCredential:
        parsed_url = urllib.parse.urlsplit(url)

        if parsed_url.scheme not in {"http", "https"}:
            return HTTPAuthCredential()

        key = f"git+{url}"

        if key not in self._credentials:
            self._credentials[key] = self._get_credentials_for_url(url, True)

        return self._credentials[key]

    def get_credentials_for_url(self, url: str) -> HTTPAuthCredential:
        parsed_url = urllib.parse.urlsplit(url)
        netloc = parsed_url.netloc

        if url not in self._credentials:
            if "@" not in netloc:
                # no credentials were provided in the url, try finding the
                # best repository configuration
                self._credentials[url] = self._get_credentials_for_url(url)
            else:
                # Split from the right because that's how urllib.parse.urlsplit()
                # behaves if more than one @ is present (which can be checked using
                # the password attribute of urlsplit()'s return value).
                auth, netloc = netloc.rsplit("@", 1)
                # Split from the left because that's how urllib.parse.urlsplit()
                # behaves if more than one : is present (which again can be checked
                # using the password attribute of the return value)
                user, password = auth.split(":", 1) if ":" in auth else (auth, "")
                self._credentials[url] = HTTPAuthCredential(
                    urllib.parse.unquote(user),
                    urllib.parse.unquote(password),
                )

        return self._credentials[url]

    def get_pypi_token(self, name: str) -> str | None:
        return self._password_manager.get_pypi_token(name)

    def get_http_auth(
        self, name: str, username: str | None = None
    ) -> HTTPAuthCredential | None:
        if name == "pypi":
            repository = AuthenticatorRepositoryConfig(
                name, "https://upload.pypi.org/legacy/"
            )
        else:
            if name not in self.configured_repositories:
                return None
            repository = self.configured_repositories[name]

        return self._get_credentials_for_repository(
            repository=repository, username=username
        )

    def get_certs_for_repository(self, name: str) -> RepositoryCertificateConfig:
        if name.lower() == "pypi" or name not in self.configured_repositories:
            return RepositoryCertificateConfig()
        return self.configured_repositories[name].certs(self._config)

    @property
    def configured_repositories(self) -> dict[str, AuthenticatorRepositoryConfig]:
        if self._configured_repositories is None:
            self._configured_repositories = {}
            for repository_name in self._config.get("repositories", []):
                url = self._config.get(f"repositories.{repository_name}.url")
                self._configured_repositories[repository_name] = (
                    AuthenticatorRepositoryConfig(repository_name, url)
                )

        return self._configured_repositories

    def reset_credentials_cache(self) -> None:
        self.get_repository_config_for_url.cache_clear()
        self._credentials = {}

    def add_repository(self, name: str, url: str) -> None:
        self.configured_repositories[name] = AuthenticatorRepositoryConfig(name, url)
        self.reset_credentials_cache()

    def get_certs_for_url(self, url: str) -> RepositoryCertificateConfig:
        if url not in self._certs:
            self._certs[url] = self._get_certs_for_url(url)
        return self._certs[url]

    def _get_repository_config_for_url(
        self, url: str, exact_match: bool = False
    ) -> AuthenticatorRepositoryConfig | None:
        parsed_url = urllib.parse.urlsplit(url)
        candidates_netloc_only = []
        candidates_path_match = []

        for repository in self.configured_repositories.values():
            if exact_match:
                if parsed_url.path == repository.path:
                    return repository
                continue

            if repository.netloc == parsed_url.netloc:
                if parsed_url.path.startswith(repository.path) or commonprefix(
                    (parsed_url.path, repository.path)
                ):
                    candidates_path_match.append(repository)
                    continue
                candidates_netloc_only.append(repository)

        if candidates_path_match:
            candidates = candidates_path_match
        elif candidates_netloc_only:
            candidates = candidates_netloc_only
        else:
            return None

        if len(candidates) > 1:
            logger.debug(
                "Multiple source configurations found for %s - %s",
                parsed_url.netloc,
                ", ".join(c.name for c in candidates),
            )
            # prefer the more specific path
            candidates.sort(
                key=lambda c: len(commonprefix([parsed_url.path, c.path])), reverse=True
            )

        return candidates[0]

    def _get_certs_for_url(self, url: str) -> RepositoryCertificateConfig:
        selected = self.get_repository_config_for_url(url)
        if selected:
            return selected.certs(config=self._config)
        return RepositoryCertificateConfig()


_authenticator: Authenticator | None = None


def get_default_authenticator() -> Authenticator:
    global _authenticator

    if _authenticator is None:
        _authenticator = Authenticator()

    return _authenticator
