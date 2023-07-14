from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from poetry.core.constraints.version.version import Version
    from poetry.core.constraints.version.version_range_constraint import (
        VersionRangeConstraint,
    )


class VersionConstraint:
    @abstractmethod
    def is_empty(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_any(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_simple(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def allows(self, version: Version) -> bool:
        raise NotImplementedError

    @abstractmethod
    def allows_all(self, other: VersionConstraint) -> bool:
        raise NotImplementedError

    @abstractmethod
    def allows_any(self, other: VersionConstraint) -> bool:
        raise NotImplementedError

    @abstractmethod
    def intersect(self, other: VersionConstraint) -> VersionConstraint:
        raise NotImplementedError

    @abstractmethod
    def union(self, other: VersionConstraint) -> VersionConstraint:
        raise NotImplementedError

    @abstractmethod
    def difference(self, other: VersionConstraint) -> VersionConstraint:
        raise NotImplementedError

    @abstractmethod
    def flatten(self) -> list[VersionRangeConstraint]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"

    def __str__(self) -> str:
        raise NotImplementedError

    def __hash__(self) -> int:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError


def _is_wildcard_candidate(
    min_: Version, max_: Version, *, inverted: bool = False
) -> bool:
    if (
        min_.is_local()
        or max_.is_local()
        or min_.is_prerelease()
        or max_.is_prerelease()
        or min_.is_postrelease() is not max_.is_postrelease()
        or min_.first_devrelease() != min_
        or (max_.is_devrelease() and max_.first_devrelease() != max_)
    ):
        return False

    first = max_ if inverted else min_
    second = min_ if inverted else max_

    parts_first = list(first.parts)
    parts_second = list(second.parts)

    # remove trailing zeros from second
    while parts_second and parts_second[-1] == 0:
        del parts_second[-1]

    # fill up first with zeros
    parts_first += [0] * (len(parts_second) - len(parts_first))

    # all exceeding parts of first must be zero
    if set(parts_first[len(parts_second) :]) not in [set(), {0}]:
        return False

    parts_first = parts_first[: len(parts_second)]

    if first.is_postrelease():
        assert first.post is not None
        return parts_first == parts_second and first.post.next() == second.post

    return (
        parts_first[:-1] == parts_second[:-1]
        and parts_first[-1] + 1 == parts_second[-1]
    )


def _single_wildcard_range_string(first: Version, second: Version) -> str:
    if first.is_postrelease():
        base_version = str(first.without_devrelease())

    else:
        parts = list(second.parts)

        # remove trailing zeros from max
        while parts and parts[-1] == 0:
            del parts[-1]

        parts[-1] = parts[-1] - 1

        base_version = ".".join(str(part) for part in parts)

    return f"{base_version}.*"
