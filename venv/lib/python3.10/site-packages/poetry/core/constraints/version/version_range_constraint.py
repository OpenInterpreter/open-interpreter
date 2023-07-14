from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from poetry.core.constraints.version.version_constraint import VersionConstraint
from poetry.core.utils._compat import cached_property


if TYPE_CHECKING:
    from poetry.core.constraints.version.version import Version


class VersionRangeConstraint(VersionConstraint):
    @property
    @abstractmethod
    def min(self) -> Version | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def max(self) -> Version | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def include_min(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def include_max(self) -> bool:
        raise NotImplementedError

    @property
    def allowed_min(self) -> Version | None:
        # That is a bit inaccurate because
        # 1) The exclusive ordered comparison >V MUST NOT allow a post-release
        #    of the given version unless V itself is a post release.
        # 2) The exclusive ordered comparison >V MUST NOT match
        #    a local version of the specified version.
        # https://peps.python.org/pep-0440/#exclusive-ordered-comparison
        # However, there is no specific min greater than the greatest post release
        # or greatest local version identifier. These cases have to be handled by
        # the callers of allowed_min.
        return self.min

    @cached_property
    def allowed_max(self) -> Version | None:
        if self.max is None:
            return None

        if self.include_max or self.max.is_unstable():
            return self.max

        if self.min == self.max and (self.include_min or self.include_max):
            # this is an equality range
            return self.max

        # The exclusive ordered comparison <V MUST NOT allow a pre-release
        # of the specified version unless the specified version is itself a pre-release.
        # https://peps.python.org/pep-0440/#exclusive-ordered-comparison
        return self.max.first_devrelease()

    def allows_lower(self, other: VersionRangeConstraint) -> bool:
        _this, _other = self.allowed_min, other.allowed_min

        if _this is None:
            return _other is not None

        if _other is None:
            return False

        if _this < _other:
            return True

        if _this > _other:
            return False

        return self.include_min and not other.include_min

    def allows_higher(self, other: VersionRangeConstraint) -> bool:
        _this, _other = self.allowed_max, other.allowed_max

        if _this is None:
            return _other is not None

        if _other is None:
            return False

        if _this < _other:
            return False

        if _this > _other:
            return True

        return self.include_max and not other.include_max

    def is_strictly_lower(self, other: VersionRangeConstraint) -> bool:
        _this, _other = self.allowed_max, other.allowed_min

        if _this is None or _other is None:
            return False

        if _this < _other:
            return True

        if _this > _other:
            return False

        return not (self.include_max and other.include_min)

    def is_strictly_higher(self, other: VersionRangeConstraint) -> bool:
        return other.is_strictly_lower(self)

    def is_adjacent_to(self, other: VersionRangeConstraint) -> bool:
        if self.max != other.min:
            return False

        return (
            self.include_max
            and not other.include_min
            or not self.include_max
            and other.include_min
        )
