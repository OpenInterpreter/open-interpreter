from __future__ import annotations

import logging

from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Any

import requests

from cachecontrol.controller import logger as cache_control_logger
from html5lib.html5parser import parse
from poetry.core.packages.package import Package
from poetry.core.packages.utils.link import Link
from poetry.core.version.exceptions import InvalidVersion

from poetry.repositories.exceptions import PackageNotFound
from poetry.repositories.http_repository import HTTPRepository
from poetry.repositories.link_sources.json import SimpleJsonPage
from poetry.utils._compat import decode
from poetry.utils.constants import REQUESTS_TIMEOUT


cache_control_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from packaging.utils import NormalizedName
    from poetry.core.constraints.version import Version
    from poetry.core.constraints.version import VersionConstraint

SUPPORTED_PACKAGE_TYPES = {"sdist", "bdist_wheel"}


class PyPiRepository(HTTPRepository):
    def __init__(
        self,
        url: str = "https://pypi.org/",
        disable_cache: bool = False,
        fallback: bool = True,
    ) -> None:
        super().__init__(
            "PyPI", url.rstrip("/") + "/simple/", disable_cache=disable_cache
        )

        self._base_url = url
        self._fallback = fallback

    def search(self, query: str) -> list[Package]:
        results = []

        search = {"q": query}

        response = requests.session().get(
            self._base_url + "search", params=search, timeout=REQUESTS_TIMEOUT
        )
        content = parse(response.content, namespaceHTMLElements=False)
        for result in content.findall(".//*[@class='package-snippet']"):
            name_element = result.find("h3/*[@class='package-snippet__name']")
            version_element = result.find("h3/*[@class='package-snippet__version']")

            if (
                name_element is None
                or version_element is None
                or not name_element.text
                or not version_element.text
            ):
                continue

            name = name_element.text
            version = version_element.text

            description_element = result.find(
                "p[@class='package-snippet__description']"
            )
            description = (
                description_element.text
                if description_element is not None and description_element.text
                else ""
            )

            try:
                package = Package(name, version)
                package.description = decode(description.strip())
                results.append(package)
            except InvalidVersion:
                self._log(
                    (
                        f'Unable to parse version "{version}" for the {name} package,'
                        " skipping"
                    ),
                    level="debug",
                )

        return results

    def get_package_info(self, name: NormalizedName) -> dict[str, Any]:
        """
        Return the package information given its name.

        The information is returned from the cache if it exists
        or retrieved from the remote server.
        """
        return self._get_package_info(name)

    def _find_packages(
        self, name: NormalizedName, constraint: VersionConstraint
    ) -> list[Package]:
        """
        Find packages on the remote server.
        """
        try:
            json_page = self.get_page(name)
        except PackageNotFound:
            self._log(f"No packages found for {name}", level="debug")
            return []

        versions = [
            (version, json_page.yanked(name, version))
            for version in json_page.versions(name)
            if constraint.allows(version)
        ]

        return [Package(name, version, yanked=yanked) for version, yanked in versions]

    def _get_package_info(self, name: str) -> dict[str, Any]:
        headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
        info = self._get(f"simple/{name}/", headers=headers)
        if info is None:
            raise PackageNotFound(f"Package [{name}] not found.")

        return info

    def find_links_for_package(self, package: Package) -> list[Link]:
        json_data = self._get(f"pypi/{package.name}/{package.version}/json")
        if json_data is None:
            return []

        links = []
        for url in json_data["urls"]:
            if url["packagetype"] in SUPPORTED_PACKAGE_TYPES:
                h = f"sha256={url['digests']['sha256']}"
                links.append(Link(url["url"] + "#" + h, yanked=self._get_yanked(url)))

        return links

    def _get_release_info(
        self, name: NormalizedName, version: Version
    ) -> dict[str, Any]:
        from poetry.inspection.info import PackageInfo

        self._log(f"Getting info for {name} ({version}) from PyPI", "debug")

        json_data = self._get(f"pypi/{name}/{version}/json")
        if json_data is None:
            raise PackageNotFound(f"Package [{name}] not found.")

        info = json_data["info"]

        data = PackageInfo(
            name=info["name"],
            version=info["version"],
            summary=info["summary"],
            requires_dist=info["requires_dist"],
            requires_python=info["requires_python"],
            files=info.get("files", []),
            yanked=self._get_yanked(info),
            cache_version=str(self.CACHE_VERSION),
        )

        try:
            version_info = json_data["urls"]
        except KeyError:
            version_info = []

        for file_info in version_info:
            if file_info["packagetype"] in SUPPORTED_PACKAGE_TYPES:
                data.files.append(
                    {
                        "file": file_info["filename"],
                        "hash": "sha256:" + file_info["digests"]["sha256"],
                    }
                )

        if self._fallback and data.requires_dist is None:
            self._log("No dependencies found, downloading archives", level="debug")
            # No dependencies set (along with other information)
            # This might be due to actually no dependencies
            # or badly set metadata when uploading
            # So, we need to make sure there is actually no
            # dependencies by introspecting packages
            urls = defaultdict(list)
            for url in json_data["urls"]:
                # Only get sdist and wheels if they exist
                dist_type = url["packagetype"]
                if dist_type not in SUPPORTED_PACKAGE_TYPES:
                    continue

                urls[dist_type].append(url["url"])

            if not urls:
                return data.asdict()

            info = self._get_info_from_urls(urls)

            data.requires_dist = info.requires_dist

            if not data.requires_python:
                data.requires_python = info.requires_python

        return data.asdict()

    def _get_page(self, name: NormalizedName) -> SimpleJsonPage:
        source = self._base_url + f"simple/{name}/"
        info = self.get_package_info(name)
        return SimpleJsonPage(source, info)

    def _get(
        self, endpoint: str, headers: dict[str, str] | None = None
    ) -> dict[str, Any] | None:
        try:
            json_response = self.session.get(
                self._base_url + endpoint,
                raise_for_status=False,
                timeout=REQUESTS_TIMEOUT,
                headers=headers,
            )
        except requests.exceptions.TooManyRedirects:
            # Cache control redirect loop.
            # We try to remove the cache and try again
            self.session.delete_cache(self._base_url + endpoint)
            json_response = self.session.get(
                self._base_url + endpoint,
                raise_for_status=False,
                timeout=REQUESTS_TIMEOUT,
                headers=headers,
            )

        if json_response.status_code != 200:
            return None

        json: dict[str, Any] = json_response.json()
        return json

    @staticmethod
    def _get_yanked(json_data: dict[str, Any]) -> str | bool:
        if json_data.get("yanked", False):
            return json_data.get("yanked_reason") or True
        return False
