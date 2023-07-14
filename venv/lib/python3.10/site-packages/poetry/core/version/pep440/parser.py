from __future__ import annotations

import functools
import re

from typing import TYPE_CHECKING
from typing import TypeVar

from packaging.version import VERSION_PATTERN

from poetry.core.version.exceptions import InvalidVersion
from poetry.core.version.pep440 import Release
from poetry.core.version.pep440 import ReleaseTag


if TYPE_CHECKING:
    from poetry.core.version.pep440 import LocalSegmentType
    from poetry.core.version.pep440.version import PEP440Version

T = TypeVar("T", bound="PEP440Version")


class PEP440Parser:
    _regex = re.compile(r"^\s*" + VERSION_PATTERN + r"\s*$", re.VERBOSE | re.IGNORECASE)
    _local_version_separators = re.compile(r"[._-]")

    @classmethod
    def _get_release(cls, match: re.Match[str] | None) -> Release:
        if not match or match.group("release") is None:
            return Release(0)
        return Release.from_parts(*(int(i) for i in match.group("release").split(".")))

    @classmethod
    def _get_prerelease(cls, match: re.Match[str] | None) -> ReleaseTag | None:
        if not match or match.group("pre") is None:
            return None
        return ReleaseTag(match.group("pre_l"), int(match.group("pre_n") or 0))

    @classmethod
    def _get_postrelease(cls, match: re.Match[str] | None) -> ReleaseTag | None:
        if not match or match.group("post") is None:
            return None

        return ReleaseTag(
            match.group("post_l") or "post",
            int(match.group("post_n1") or match.group("post_n2") or 0),
        )

    @classmethod
    def _get_devrelease(cls, match: re.Match[str] | None) -> ReleaseTag | None:
        if not match or match.group("dev") is None:
            return None
        return ReleaseTag(match.group("dev_l"), int(match.group("dev_n") or 0))

    @classmethod
    def _get_local(cls, match: re.Match[str] | None) -> LocalSegmentType | None:
        if not match or match.group("local") is None:
            return None

        return tuple(
            part.lower()
            for part in cls._local_version_separators.split(match.group("local"))
        )

    @classmethod
    @functools.lru_cache(maxsize=None)
    def parse(cls, value: str, version_class: type[T]) -> T:
        match = cls._regex.search(value) if value else None
        if not match:
            raise InvalidVersion(f"Invalid PEP 440 version: '{value}'")

        return version_class(
            epoch=int(match.group("epoch")) if match.group("epoch") else 0,
            release=cls._get_release(match),
            pre=cls._get_prerelease(match),
            post=cls._get_postrelease(match),
            dev=cls._get_devrelease(match),
            local=cls._get_local(match),
            text=value,
        )


def parse_pep440(value: str, version_class: type[T]) -> T:
    return PEP440Parser.parse(value, version_class)  # type: ignore[arg-type]
