from __future__ import annotations

import dataclasses

from typing import TYPE_CHECKING

from poetry.core.constraints.version.empty_constraint import EmptyConstraint
from poetry.core.constraints.version.version_range_constraint import (
    VersionRangeConstraint,
)
from poetry.core.constraints.version.version_union import VersionUnion
from poetry.core.version.pep440 import Release
from poetry.core.version.pep440.version import PEP440Version


if TYPE_CHECKING:
    from poetry.core.constraints.version.version_constraint import VersionConstraint
    from poetry.core.version.pep440 import LocalSegmentType
    from poetry.core.version.pep440 import ReleaseTag


@dataclasses.dataclass(frozen=True)
class Version(PEP440Version, VersionRangeConstraint):
    """
    A version constraint representing a single version.
    """

    @property
    def precision(self) -> int:
        return self.release.precision

    @property
    def stable(self) -> Version:
        if self.is_stable():
            return self

        post = self.post if self.pre is None else None
        return Version(release=self.release, post=post, epoch=self.epoch)

    def next_breaking(self) -> Version:
        if self.major > 0 or self.minor is None:
            return self.stable.next_major()

        if self.minor > 0 or self.patch is None:
            return self.stable.next_minor()

        return self.stable.next_patch()

    @property
    def min(self) -> Version:
        return self

    @property
    def max(self) -> Version:
        return self

    @property
    def full_max(self) -> Version:
        return self

    @property
    def include_min(self) -> bool:
        return True

    @property
    def include_max(self) -> bool:
        return True

    def is_any(self) -> bool:
        return False

    def is_empty(self) -> bool:
        return False

    def is_simple(self) -> bool:
        return True

    def allows(self, version: Version | None) -> bool:
        if version is None:
            return False

        _this, _other = self, version

        # allow weak equality to allow `3.0.0+local.1` for `3.0.0`
        if not _this.is_local() and _other.is_local():
            _other = _other.without_local()

        return _this == _other

    def allows_all(self, other: VersionConstraint) -> bool:
        return other.is_empty() or (
            self.allows(other) if isinstance(other, self.__class__) else other == self
        )

    def allows_any(self, other: VersionConstraint) -> bool:
        intersection = self.intersect(other)
        return not intersection.is_empty()

    def intersect(self, other: VersionConstraint) -> VersionConstraint:
        if isinstance(other, Version):
            if self.allows(other):
                return other

            if other.allows(self):
                return self

            return EmptyConstraint()

        return other.intersect(self)

    def union(self, other: VersionConstraint) -> VersionConstraint:
        from poetry.core.constraints.version.version_range import VersionRange

        if other.allows(self):
            return other

        if isinstance(other, VersionRangeConstraint):
            if self.allows(other.min):
                return VersionRange(
                    other.min,
                    other.max,
                    include_min=True,
                    include_max=other.include_max,
                )

            if self.allows(other.max):
                return VersionRange(
                    other.min,
                    other.max,
                    include_min=other.include_min,
                    include_max=True,
                )

        return VersionUnion.of(self, other)

    def difference(self, other: VersionConstraint) -> Version | EmptyConstraint:
        if other.allows(self):
            return EmptyConstraint()

        return self

    def flatten(self) -> list[VersionRangeConstraint]:
        return [self]

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other: object) -> bool:
        from poetry.core.constraints.version.version_range import VersionRange

        if isinstance(other, VersionRange):
            return (
                self == other.min
                and self == other.max
                and (other.include_min or other.include_max)
            )
        return super().__eq__(other)

    @classmethod
    def from_parts(
        cls,
        major: int,
        minor: int | None = None,
        patch: int | None = None,
        extra: int | tuple[int, ...] = (),
        pre: ReleaseTag | None = None,
        post: ReleaseTag | None = None,
        dev: ReleaseTag | None = None,
        local: LocalSegmentType = None,
        *,
        epoch: int = 0,
    ) -> Version:
        if isinstance(extra, int):
            extra = (extra,)
        return cls(
            release=Release(major=major, minor=minor, patch=patch, extra=extra),
            pre=pre,
            post=post,
            dev=dev,
            local=local,
            epoch=epoch,
        )
