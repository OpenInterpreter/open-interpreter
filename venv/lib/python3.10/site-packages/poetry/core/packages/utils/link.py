from __future__ import annotations

import posixpath
import re
import urllib.parse as urlparse

from poetry.core.packages.utils.utils import path_to_url
from poetry.core.packages.utils.utils import splitext


class Link:
    def __init__(
        self,
        url: str,
        requires_python: str | None = None,
        metadata: str | bool | None = None,
        yanked: str | bool = False,
    ) -> None:
        """
        Object representing a parsed link from https://pypi.python.org/simple/*

        url:
            url of the resource pointed to (href of the link)
        requires_python:
            String containing the `Requires-Python` metadata field, specified
            in PEP 345. This may be specified by a data-requires-python
            attribute in the HTML link tag, as described in PEP 503.
        metadata:
            String of the syntax `<hashname>=<hashvalue>` representing the hash
            of the Core Metadata file. This may be specified by a
            data-dist-info-metadata attribute in the HTML link tag, as described
            in PEP 658.
        yanked:
            False, if the data-yanked attribute is not present.
            A string, if the data-yanked attribute has a string value.
            True, if the data-yanked attribute is present but has no value.
            According to PEP 592.
        """

        # url can be a UNC windows share
        if url.startswith("\\\\"):
            url = path_to_url(url)

        self.url = url
        self.requires_python = requires_python if requires_python else None

        if isinstance(metadata, str):
            metadata = {"true": True, "": False, "false": False}.get(
                metadata.strip().lower(), metadata
            )

        self._metadata = metadata
        self._yanked = yanked

    def __str__(self) -> str:
        if self.requires_python:
            rp = f" (requires-python:{self.requires_python})"
        else:
            rp = ""

        return f"{self.url}{rp}"

    def __repr__(self) -> str:
        return f"<Link {self!s}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url == other.url

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url != other.url

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url < other.url

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url <= other.url

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url > other.url

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return NotImplemented
        return self.url >= other.url

    def __hash__(self) -> int:
        return hash(self.url)

    @property
    def filename(self) -> str:
        _, netloc, path, _, _ = urlparse.urlsplit(self.url)
        name = posixpath.basename(path.rstrip("/")) or netloc
        name = urlparse.unquote(name)

        return name

    @property
    def scheme(self) -> str:
        return urlparse.urlsplit(self.url)[0]

    @property
    def netloc(self) -> str:
        return urlparse.urlsplit(self.url)[1]

    @property
    def path(self) -> str:
        return urlparse.unquote(urlparse.urlsplit(self.url)[2])

    def splitext(self) -> tuple[str, str]:
        return splitext(posixpath.basename(self.path.rstrip("/")))

    @property
    def ext(self) -> str:
        return self.splitext()[1]

    @property
    def url_without_fragment(self) -> str:
        scheme, netloc, path, query, fragment = urlparse.urlsplit(self.url)
        return urlparse.urlunsplit((scheme, netloc, path, query, None))

    _egg_fragment_re = re.compile(r"[#&]egg=([^&]*)")

    @property
    def egg_fragment(self) -> str | None:
        match = self._egg_fragment_re.search(self.url)
        if not match:
            return None
        return match.group(1)

    _subdirectory_fragment_re = re.compile(r"[#&]subdirectory=([^&]*)")

    @property
    def subdirectory_fragment(self) -> str | None:
        match = self._subdirectory_fragment_re.search(self.url)
        if not match:
            return None
        return match.group(1)

    _hash_re = re.compile(r"(sha1|sha224|sha384|sha256|sha512|md5)=([a-f0-9]+)")

    @property
    def has_metadata(self) -> bool:
        if self._metadata is None:
            return False
        return bool(self._metadata) and (self.is_wheel or self.is_sdist)

    @property
    def metadata_url(self) -> str | None:
        if self.has_metadata:
            return f"{self.url_without_fragment.split('?', 1)[0]}.metadata"
        return None

    @property
    def metadata_hash(self) -> str | None:
        if self.has_metadata and isinstance(self._metadata, str):
            match = self._hash_re.search(self._metadata)
            if match:
                return match.group(2)
        return None

    @property
    def metadata_hash_name(self) -> str | None:
        if self.has_metadata and isinstance(self._metadata, str):
            match = self._hash_re.search(self._metadata)
            if match:
                return match.group(1)
        return None

    @property
    def hash(self) -> str | None:
        match = self._hash_re.search(self.url)
        if match:
            return match.group(2)
        return None

    @property
    def hash_name(self) -> str | None:
        match = self._hash_re.search(self.url)
        if match:
            return match.group(1)
        return None

    @property
    def show_url(self) -> str:
        return posixpath.basename(self.url.split("#", 1)[0].split("?", 1)[0])

    @property
    def is_wheel(self) -> bool:
        return self.ext == ".whl"

    @property
    def is_wininst(self) -> bool:
        return self.ext == ".exe"

    @property
    def is_egg(self) -> bool:
        return self.ext == ".egg"

    @property
    def is_sdist(self) -> bool:
        return self.ext in {".tar.bz2", ".tar.gz", ".zip"}

    @property
    def is_artifact(self) -> bool:
        """
        Determines if this points to an actual artifact (e.g. a tarball) or if
        it points to an "abstract" thing like a path or a VCS location.
        """
        if self.scheme in ("ssh", "git", "hg", "bzr", "sftp", "svn"):
            return False

        return True

    @property
    def yanked(self) -> bool:
        return isinstance(self._yanked, str) or bool(self._yanked)

    @property
    def yanked_reason(self) -> str:
        if isinstance(self._yanked, str):
            return self._yanked
        return ""
