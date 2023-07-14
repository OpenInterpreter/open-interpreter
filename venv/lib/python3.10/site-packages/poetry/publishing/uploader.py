from __future__ import annotations

import hashlib
import io

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import requests

from poetry.core.masonry.metadata import Metadata
from poetry.core.masonry.utils.helpers import distribution_name
from requests import adapters
from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests_toolbelt import user_agent
from requests_toolbelt.multipart import MultipartEncoder
from requests_toolbelt.multipart import MultipartEncoderMonitor
from urllib3 import util

from poetry.__version__ import __version__
from poetry.utils.constants import REQUESTS_TIMEOUT
from poetry.utils.constants import STATUS_FORCELIST
from poetry.utils.patterns import wheel_file_re


if TYPE_CHECKING:
    from cleo.io.io import IO

    from poetry.poetry import Poetry

_has_blake2 = hasattr(hashlib, "blake2b")


class UploadError(Exception):
    def __init__(self, error: ConnectionError | HTTPError | str) -> None:
        if isinstance(error, HTTPError):
            message = (
                f"HTTP Error {error.response.status_code}: {error.response.reason} |"
                f" {error.response.content!r}"
            )
        elif isinstance(error, ConnectionError):
            message = (
                "Connection Error: We were unable to connect to the repository, "
                "ensure the url is correct and can be reached."
            )
        else:
            message = str(error)
        super().__init__(message)


class Uploader:
    def __init__(self, poetry: Poetry, io: IO) -> None:
        self._poetry = poetry
        self._package = poetry.package
        self._io = io
        self._username: str | None = None
        self._password: str | None = None

    @property
    def user_agent(self) -> str:
        agent: str = user_agent("poetry", __version__)
        return agent

    @property
    def adapter(self) -> adapters.HTTPAdapter:
        retry = util.Retry(
            connect=5,
            total=10,
            allowed_methods=["GET"],
            respect_retry_after_header=True,
            status_forcelist=STATUS_FORCELIST,
        )

        return adapters.HTTPAdapter(max_retries=retry)

    @property
    def files(self) -> list[Path]:
        dist = self._poetry.file.path.parent / "dist"
        version = self._package.version.to_string()
        escaped_name = distribution_name(self._package.name)

        wheels = list(dist.glob(f"{escaped_name}-{version}-*.whl"))
        tars = list(dist.glob(f"{escaped_name}-{version}.tar.gz"))

        return sorted(wheels + tars)

    def auth(self, username: str | None, password: str | None) -> None:
        self._username = username
        self._password = password

    def make_session(self) -> requests.Session:
        session = requests.session()
        auth = self.get_auth()
        if auth is not None:
            session.auth = auth

        session.headers["User-Agent"] = self.user_agent
        for scheme in ("http://", "https://"):
            session.mount(scheme, self.adapter)

        return session

    def get_auth(self) -> tuple[str, str] | None:
        if self._username is None or self._password is None:
            return None

        return (self._username, self._password)

    def upload(
        self,
        url: str,
        cert: Path | bool = True,
        client_cert: Path | None = None,
        dry_run: bool = False,
        skip_existing: bool = False,
    ) -> None:
        session = self.make_session()

        session.verify = str(cert) if isinstance(cert, Path) else cert

        if client_cert:
            session.cert = str(client_cert)

        try:
            self._upload(session, url, dry_run, skip_existing)
        finally:
            session.close()

    def post_data(self, file: Path) -> dict[str, Any]:
        meta = Metadata.from_package(self._package)

        file_type = self._get_type(file)

        if _has_blake2:
            blake2_256_hash = hashlib.blake2b(digest_size=256 // 8)

        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        with file.open("rb") as fp:
            for content in iter(lambda: fp.read(io.DEFAULT_BUFFER_SIZE), b""):
                md5_hash.update(content)
                sha256_hash.update(content)

                if _has_blake2:
                    blake2_256_hash.update(content)

        md5_digest = md5_hash.hexdigest()
        sha2_digest = sha256_hash.hexdigest()
        blake2_256_digest: str | None = None
        if _has_blake2:
            blake2_256_digest = blake2_256_hash.hexdigest()

        py_version: str | None = None
        if file_type == "bdist_wheel":
            wheel_info = wheel_file_re.match(file.name)
            if wheel_info is not None:
                py_version = wheel_info.group("pyver")

        data = {
            # identify release
            "name": meta.name,
            "version": meta.version,
            # file content
            "filetype": file_type,
            "pyversion": py_version,
            # additional meta-data
            "metadata_version": meta.metadata_version,
            "summary": meta.summary,
            "home_page": meta.home_page,
            "author": meta.author,
            "author_email": meta.author_email,
            "maintainer": meta.maintainer,
            "maintainer_email": meta.maintainer_email,
            "license": meta.license,
            "description": meta.description,
            "keywords": meta.keywords,
            "platform": meta.platforms,
            "classifiers": meta.classifiers,
            "download_url": meta.download_url,
            "supported_platform": meta.supported_platforms,
            "comment": None,
            "md5_digest": md5_digest,
            "sha256_digest": sha2_digest,
            "blake2_256_digest": blake2_256_digest,
            # PEP 314
            "provides": meta.provides,
            "requires": meta.requires,
            "obsoletes": meta.obsoletes,
            # Metadata 1.2
            "project_urls": meta.project_urls,
            "provides_dist": meta.provides_dist,
            "obsoletes_dist": meta.obsoletes_dist,
            "requires_dist": meta.requires_dist,
            "requires_external": meta.requires_external,
            "requires_python": meta.requires_python,
        }

        # Metadata 2.1
        if meta.description_content_type:
            data["description_content_type"] = meta.description_content_type

        # TODO: Provides extra

        return data

    def _upload(
        self,
        session: requests.Session,
        url: str,
        dry_run: bool = False,
        skip_existing: bool = False,
    ) -> None:
        for file in self.files:
            self._upload_file(session, url, file, dry_run, skip_existing)

    def _upload_file(
        self,
        session: requests.Session,
        url: str,
        file: Path,
        dry_run: bool = False,
        skip_existing: bool = False,
    ) -> None:
        from cleo.ui.progress_bar import ProgressBar

        if not file.is_file():
            raise UploadError(f"Archive ({file}) does not exist")

        data = self.post_data(file)
        data.update(
            {
                # action
                ":action": "file_upload",
                "protocol_version": "1",
            }
        )

        data_to_send: list[tuple[str, Any]] = self._prepare_data(data)

        with file.open("rb") as fp:
            data_to_send.append(
                ("content", (file.name, fp, "application/octet-stream"))
            )
            encoder = MultipartEncoder(data_to_send)
            bar = ProgressBar(self._io, max=encoder.len)
            bar.set_format(f" - Uploading <c1>{file.name}</c1> <b>%percent%%</b>")
            monitor = MultipartEncoderMonitor(
                encoder, lambda monitor: bar.set_progress(monitor.bytes_read)
            )

            bar.start()

            resp = None

            try:
                if not dry_run:
                    resp = session.post(
                        url,
                        data=monitor,
                        allow_redirects=False,
                        headers={"Content-Type": monitor.content_type},
                        timeout=REQUESTS_TIMEOUT,
                    )
                if resp is None or 200 <= resp.status_code < 300:
                    bar.set_format(
                        f" - Uploading <c1>{file.name}</c1> <fg=green>%percent%%</>"
                    )
                    bar.finish()
                elif 300 <= resp.status_code < 400:
                    if self._io.output.is_decorated():
                        self._io.overwrite(
                            f" - Uploading <c1>{file.name}</c1> <error>FAILED</>"
                        )
                    raise UploadError(
                        "Redirects are not supported. "
                        "Is the URL missing a trailing slash?"
                    )
                elif resp.status_code == 400 and "was ever registered" in resp.text:
                    self._register(session, url)
                    resp.raise_for_status()
                elif skip_existing and self._is_file_exists_error(resp):
                    bar.set_format(
                        f" - Uploading <c1>{file.name}</c1> <warning>File exists."
                        " Skipping</>"
                    )
                    bar.display()
                else:
                    resp.raise_for_status()
            except (requests.ConnectionError, requests.HTTPError) as e:
                if self._io.output.is_decorated():
                    self._io.overwrite(
                        f" - Uploading <c1>{file.name}</c1> <error>FAILED</>"
                    )
                raise UploadError(e)
            finally:
                self._io.write_line("")

    def _register(self, session: requests.Session, url: str) -> requests.Response:
        """
        Register a package to a repository.
        """
        dist = self._poetry.file.path.parent / "dist"
        escaped_name = distribution_name(self._package.name)
        file = dist / f"{escaped_name}-{self._package.version.to_string()}.tar.gz"

        if not file.exists():
            raise RuntimeError(f'"{file.name}" does not exist.')

        data = self.post_data(file)
        data.update({":action": "submit", "protocol_version": "1"})

        data_to_send = self._prepare_data(data)
        encoder = MultipartEncoder(data_to_send)
        resp = session.post(
            url,
            data=encoder,
            allow_redirects=False,
            headers={"Content-Type": encoder.content_type},
            timeout=REQUESTS_TIMEOUT,
        )

        resp.raise_for_status()

        return resp

    def _prepare_data(self, data: dict[str, Any]) -> list[tuple[str, str]]:
        data_to_send = []
        for key, value in data.items():
            if not isinstance(value, (list, tuple)):
                data_to_send.append((key, value))
            else:
                for item in value:
                    data_to_send.append((key, item))

        return data_to_send

    def _get_type(self, file: Path) -> str:
        exts = file.suffixes
        if exts[-1] == ".whl":
            return "bdist_wheel"
        elif len(exts) >= 2 and "".join(exts[-2:]) == ".tar.gz":
            return "sdist"

        raise ValueError("Unknown distribution format " + "".join(exts))

    def _is_file_exists_error(self, response: requests.Response) -> bool:
        # based on https://github.com/pypa/twine/blob/a6dd69c79f7b5abfb79022092a5d3776a499e31b/twine/commands/upload.py#L32  # noqa: E501
        status = response.status_code
        reason = response.reason.lower()
        text = response.text.lower()
        reason_and_text = reason + text

        return (
            # pypiserver (https://pypi.org/project/pypiserver)
            status == 409
            # PyPI / TestPyPI / GCP Artifact Registry
            or (status == 400 and "already exist" in reason_and_text)
            # Nexus Repository OSS (https://www.sonatype.com/nexus-repository-oss)
            or (status == 400 and "updating asset" in reason_and_text)
            # Artifactory (https://jfrog.com/artifactory/)
            or (status == 403 and "overwrite artifact" in reason_and_text)
            # Gitlab Enterprise Edition (https://about.gitlab.com)
            or (status == 400 and "already been taken" in reason_and_text)
        )
