import logging
import os

from collections import defaultdict
from typing import Dict
from typing import List
from typing import Union

import requests

from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.controller import logger as cache_control_logger
from cachy import CacheManager
from html5lib.html5parser import parse

from poetry.core.packages import Dependency
from poetry.core.packages import Package
from poetry.core.packages import dependency_from_pep_508
from poetry.core.packages.utils.link import Link
from poetry.core.semver import VersionConstraint
from poetry.core.semver import VersionRange
from poetry.core.semver import parse_constraint
from poetry.core.semver.exceptions import ParseVersionError
from poetry.core.version.markers import parse_marker
from poetry.locations import REPOSITORY_CACHE_DIR
from poetry.utils._compat import Path
from poetry.utils._compat import to_str
from poetry.utils.helpers import download_file
from poetry.utils.helpers import temporary_directory
from poetry.utils.patterns import wheel_file_re

from pip._internal.network.session import PipSession
from pip._internal.network.download import Downloader as PipDownloader
from pip._internal.models.link import Link as PipLink

from ..inspection.info import PackageInfo
from .exceptions import PackageNotFound
from .remote_repository import RemoteRepository


try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse


cache_control_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class PyPiRepository(RemoteRepository):

    CACHE_VERSION = parse_constraint("1.0.0")

    def __init__(self, config=None, url="https://pypi.org/", disable_cache=False, fallback=True):
        super(PyPiRepository, self).__init__(url.rstrip("/") + "/simple/")

        self._config = config
        self._base_url = url
        self._disable_cache = disable_cache
        self._fallback = fallback

        release_cache_dir = REPOSITORY_CACHE_DIR / "pypi"
        if self._config:
            release_cache_dir = Path(self._config.get("cache-dir")) / "pypi"
        self._cache = CacheManager(
            {
                "default": "releases",
                "serializer": "json",
                "stores": {
                    "releases": {"driver": "file", "path": str(release_cache_dir)},
                    "packages": {"driver": "dict"},
                },
            }
        )

        self._cache_control_cache = FileCache(str(release_cache_dir / "_http"))
        self._name = "PyPI"

        home_dir = os.getenv('HOME')
        pypi = os.getenv('REPLIT_POETRY_PYPI_REPOSITORY') or 'https://pypi.org/pypi/'
        self._pip_session = PipSession(
            cache='%s/.cache/pip/http' % home_dir,
            retries=None,
            trusted_hosts=[],
            index_urls=['%ssimple/' % pypi]
        )

    @property
    def session(self):
        return CacheControl(requests.session(), cache=self._cache_control_cache)

    def find_packages(self, dependency):  # type: (Dependency) -> List[Package]
        """
        Find packages on the remote server.
        """
        constraint = dependency.constraint
        if constraint is None:
            constraint = "*"

        if not isinstance(constraint, VersionConstraint):
            constraint = parse_constraint(constraint)

        allow_prereleases = dependency.allows_prereleases()
        if isinstance(constraint, VersionRange):
            if (
                constraint.max is not None
                and constraint.max.is_prerelease()
                or constraint.min is not None
                and constraint.min.is_prerelease()
            ):
                allow_prereleases = True

        try:
            info = self.get_package_info(dependency.name)
        except PackageNotFound:
            self._log(
                "No packages found for {} {}".format(dependency.name, str(constraint)),
                level="debug",
            )
            return []

        packages = []
        ignored_pre_release_packages = []

        for version, release in info["releases"].items():
            if not release:
                # Bad release
                self._log(
                    "No release information found for {}-{}, skipping".format(
                        dependency.name, version
                    ),
                    level="debug",
                )
                continue

            try:
                package = Package(info["info"]["name"], version)
            except ParseVersionError:
                self._log(
                    'Unable to parse version "{}" for the {} package, skipping'.format(
                        version, dependency.name
                    ),
                    level="debug",
                )
                continue

            if package.is_prerelease() and not allow_prereleases:
                if constraint.is_any():
                    # we need this when all versions of the package are pre-releases
                    ignored_pre_release_packages.append(package)
                continue

            if not constraint or (constraint and constraint.allows(package.version)):
                packages.append(package)

        self._log(
            "{} packages found for {} {}".format(
                len(packages), dependency.name, str(constraint)
            ),
            level="debug",
        )

        return packages or ignored_pre_release_packages

    def package(
        self,
        name,  # type: str
        version,  # type: str
        extras=None,  # type: (Union[list, None])
    ):  # type: (...) -> Package
        return self.get_release_info(name, version).to_package(name=name, extras=extras)

    def search(self, query):
        results = []

        search = {"q": query}

        response = requests.session().get(self._base_url + "search", params=search)
        content = parse(response.content, namespaceHTMLElements=False)
        for result in content.findall(".//*[@class='package-snippet']"):
            name = result.find("h3/*[@class='package-snippet__name']").text
            version = result.find("h3/*[@class='package-snippet__version']").text

            if not name or not version:
                continue

            description = result.find("p[@class='package-snippet__description']").text
            if not description:
                description = ""

            try:
                result = Package(name, version, description)
                result.description = to_str(description.strip())
                results.append(result)
            except ParseVersionError:
                self._log(
                    'Unable to parse version "{}" for the {} package, skipping'.format(
                        version, name
                    ),
                    level="debug",
                )

        return results

    def get_package_info(self, name):  # type: (str) -> dict
        """
        Return the package information given its name.

        The information is returned from the cache if it exists
        or retrieved from the remote server.
        """
        if self._disable_cache:
            return self._get_package_info(name)

        return self._cache.store("packages").remember_forever(
            name, lambda: self._get_package_info(name)
        )

    def _get_package_info(self, name):  # type: (str) -> dict
        data = self._get("pypi/{}/json".format(name))
        if data is None:
            raise PackageNotFound("Package [{}] not found.".format(name))

        return data

    def get_release_info(self, name, version):  # type: (str, str) -> PackageInfo
        """
        Return the release information given a package name and a version.

        The information is returned from the cache if it exists
        or retrieved from the remote server.
        """
        if self._disable_cache:
            return PackageInfo.load(self._get_release_info(name, version))

        cached = self._cache.remember_forever(
            "{}:{}".format(name, version), lambda: self._get_release_info(name, version)
        )

        cache_version = cached.get("_cache_version", "0.0.0")
        if parse_constraint(cache_version) != self.CACHE_VERSION:
            # The cache must be updated
            self._log(
                "The cache for {} {} is outdated. Refreshing.".format(name, version),
                level="debug",
            )
            cached = self._get_release_info(name, version)

            self._cache.forever("{}:{}".format(name, version), cached)

        return PackageInfo.load(cached)

    def find_links_for_package(self, package):
        json_data = self._get("pypi/{}/{}/json".format(package.name, package.version))
        if json_data is None:
            return []

        links = []
        for url in json_data["urls"]:
            h = "sha256={}".format(url["digests"]["sha256"])
            links.append(Link(url["url"] + "#" + h))

        return links

    def _get_release_info(self, name, version):  # type: (str, str) -> dict
        self._log("Getting info for {} ({}) from PyPI".format(name, version), "debug")

        json_data = self._get("pypi/{}/{}/json".format(name, version))
        if json_data is None:
            raise PackageNotFound("Package [{}] not found.".format(name))

        info = json_data["info"]

        data = PackageInfo(
            name=info["name"],
            version=info["version"],
            summary=info["summary"],
            platform=info["platform"],
            requires_dist=info["requires_dist"],
            requires_python=info["requires_python"],
            files=info.get("files", []),
            cache_version=str(self.CACHE_VERSION),
        )

        try:
            releases = json_data["releases"]
            if releases is not None:
                version_info = releases[version]
            else:
                version_info = []
        except KeyError:
            version_info = []

        for file_info in version_info:
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
                if dist_type not in ["sdist", "bdist_wheel"]:
                    continue

                urls[dist_type].append(url["url"])

            if not urls:
                return data.asdict()

            info = self._get_info_from_urls(urls)

            data.requires_dist = info.requires_dist

            if not data.requires_python:
                data.requires_python = info.requires_python

        return data.asdict()

    def _get(self, endpoint):  # type: (str) -> Union[dict, None]
        try:
            json_response = self.session.get(self._base_url + endpoint)
        except requests.exceptions.TooManyRedirects:
            # Cache control redirect loop.
            # We try to remove the cache and try again
            self._cache_control_cache.delete(self._base_url + endpoint)
            json_response = self.session.get(self._base_url + endpoint)

        if json_response.status_code == 404:
            return None

        json_data = json_response.json()

        return json_data

    def _get_info_from_urls(self, urls):  # type: (Dict[str, List[str]]) -> PackageInfo
        # Checking wheels first as they are more likely to hold
        # the necessary information
        if "bdist_wheel" in urls:
            # Check fo a universal wheel
            wheels = urls["bdist_wheel"]

            universal_wheel = None
            universal_python2_wheel = None
            universal_python3_wheel = None
            platform_specific_wheels = []
            for wheel in wheels:
                link = Link(wheel)
                m = wheel_file_re.match(link.filename)
                if not m:
                    continue

                pyver = m.group("pyver")
                abi = m.group("abi")
                plat = m.group("plat")
                if abi == "none" and plat == "any":
                    # Universal wheel
                    if pyver == "py2.py3":
                        # Any Python
                        universal_wheel = wheel
                    elif pyver == "py2":
                        universal_python2_wheel = wheel
                    else:
                        universal_python3_wheel = wheel
                else:
                    platform_specific_wheels.append(wheel)

            if universal_wheel is not None:
                return self._get_info_from_wheel(universal_wheel)

            info = None
            if universal_python2_wheel and universal_python3_wheel:
                info = self._get_info_from_wheel(universal_python2_wheel)

                py3_info = self._get_info_from_wheel(universal_python3_wheel)
                if py3_info.requires_dist:
                    if not info.requires_dist:
                        info.requires_dist = py3_info.requires_dist

                        return info

                    py2_requires_dist = set(
                        dependency_from_pep_508(r).to_pep_508()
                        for r in info.requires_dist
                    )
                    py3_requires_dist = set(
                        dependency_from_pep_508(r).to_pep_508()
                        for r in py3_info.requires_dist
                    )
                    base_requires_dist = py2_requires_dist & py3_requires_dist
                    py2_only_requires_dist = py2_requires_dist - py3_requires_dist
                    py3_only_requires_dist = py3_requires_dist - py2_requires_dist

                    # Normalizing requires_dist
                    requires_dist = list(base_requires_dist)
                    for requirement in py2_only_requires_dist:
                        dep = dependency_from_pep_508(requirement)
                        dep.marker = dep.marker.intersect(
                            parse_marker("python_version == '2.7'")
                        )
                        requires_dist.append(dep.to_pep_508())

                    for requirement in py3_only_requires_dist:
                        dep = dependency_from_pep_508(requirement)
                        dep.marker = dep.marker.intersect(
                            parse_marker("python_version >= '3'")
                        )
                        requires_dist.append(dep.to_pep_508())

                    info.requires_dist = sorted(list(set(requires_dist)))

            if info:
                return info

            # Prefer non platform specific wheels
            if universal_python3_wheel:
                return self._get_info_from_wheel(universal_python3_wheel)

            if universal_python2_wheel:
                return self._get_info_from_wheel(universal_python2_wheel)

            if platform_specific_wheels:
                # Pick the first wheel available and hope for the best
                return self._get_info_from_wheel(platform_specific_wheels[0])

        return self._get_info_from_sdist(urls["sdist"][0])

    def _get_info_from_wheel(self, url):  # type: (str) -> PackageInfo
        self._log(
            "Downloading wheel: {}".format(urlparse.urlparse(url).path.rsplit("/")[-1]),
            level="debug",
        )

        with temporary_directory() as temp_dir:
            filepath = self._pip_download(url, temp_dir)

            return PackageInfo.from_wheel(Path(filepath))

    def _get_info_from_sdist(self, url):  # type: (str) -> PackageInfo
        self._log(
            "Downloading sdist: {}".format(urlparse.urlparse(url).path.rsplit("/")[-1]),
            level="debug",
        )

        with temporary_directory() as temp_dir:
            filepath = self._pip_download(url, temp_dir)

            return PackageInfo.from_sdist(Path(filepath))

    def _pip_download(self, url, dest_dir):
        downloader = PipDownloader(self._pip_session, "off")
        link = PipLink(url)
        filepath, _ = downloader(link, dest_dir)
        return filepath

    def _download(self, url, dest):  # type: (str, str) -> None
        return download_file(url, dest, session=self.session)

    def _log(self, msg, level="info"):
        getattr(logger, level)("<debug>{}:</debug> {}".format(self._name, msg))
