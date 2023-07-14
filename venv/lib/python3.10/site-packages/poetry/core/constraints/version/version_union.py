from __future__ import annotations

import operator as op

from functools import reduce
from typing import TYPE_CHECKING

from poetry.core.constraints.version.empty_constraint import EmptyConstraint
from poetry.core.constraints.version.version_constraint import VersionConstraint
from poetry.core.constraints.version.version_constraint import _is_wildcard_candidate
from poetry.core.constraints.version.version_constraint import (
    _single_wildcard_range_string,
)
from poetry.core.constraints.version.version_range_constraint import (
    VersionRangeConstraint,
)
from poetry.core.utils._compat import cached_property


if TYPE_CHECKING:
    from poetry.core.constraints.version.version import Version


class VersionUnion(VersionConstraint):
    """
    A version constraint representing a union of multiple disjoint version
    ranges.

    An instance of this will only be created if the version can't be represented
    as a non-compound value.
    """

    def __init__(self, *ranges: VersionRangeConstraint) -> None:
        self._ranges = list(ranges)

    @property
    def ranges(self) -> list[VersionRangeConstraint]:
        return self._ranges

    @classmethod
    def of(cls, *ranges: VersionConstraint) -> VersionConstraint:
        from poetry.core.constraints.version.version_range import VersionRange

        flattened: list[VersionRangeConstraint] = []
        for constraint in ranges:
            if constraint.is_empty():
                continue

            if isinstance(constraint, VersionUnion):
                flattened += constraint.ranges
                continue

            assert isinstance(constraint, VersionRangeConstraint)
            flattened.append(constraint)

        if not flattened:
            return EmptyConstraint()

        if any(constraint.is_any() for constraint in flattened):
            return VersionRange()

        # Only allow Versions and VersionRanges here so we can more easily reason
        # about everything in flattened. _EmptyVersions and VersionUnions are
        # filtered out above.
        for constraint in flattened:
            if not isinstance(constraint, VersionRangeConstraint):
                raise ValueError(f"Unknown VersionConstraint type {constraint}.")

        flattened.sort()

        merged: list[VersionRangeConstraint] = []
        for constraint in flattened:
            # Merge this constraint with the previous one, but only if they touch.
            if not merged or (
                not merged[-1].allows_any(constraint)
                and not merged[-1].is_adjacent_to(constraint)
            ):
                merged.append(constraint)
            else:
                new_constraint = merged[-1].union(constraint)
                assert isinstance(new_constraint, VersionRangeConstraint)
                merged[-1] = new_constraint

        if len(merged) == 1:
            return merged[0]

        return VersionUnion(*merged)

    def is_empty(self) -> bool:
        return False

    def is_any(self) -> bool:
        return False

    def is_simple(self) -> bool:
        return self.excludes_single_version

    def allows(self, version: Version) -> bool:
        if self.excludes_single_version:
            # when excluded version is local, special handling is required
            # to ensure that a constraint (!=2.0+deadbeef) will allow the
            # provided version (2.0)

            excluded = self._excluded_single_version

            if excluded.is_local():
                return excluded != version

        return any(constraint.allows(version) for constraint in self._ranges)

    def allows_all(self, other: VersionConstraint) -> bool:
        our_ranges = iter(self._ranges)
        their_ranges = iter(other.flatten())

        our_current_range = next(our_ranges, None)
        their_current_range = next(their_ranges, None)

        while our_current_range and their_current_range:
            if our_current_range.allows_all(their_current_range):
                their_current_range = next(their_ranges, None)
            else:
                our_current_range = next(our_ranges, None)

        return their_current_range is None

    def allows_any(self, other: VersionConstraint) -> bool:
        our_ranges = iter(self._ranges)
        their_ranges = iter(other.flatten())

        our_current_range = next(our_ranges, None)
        their_current_range = next(their_ranges, None)

        while our_current_range and their_current_range:
            if our_current_range.allows_any(their_current_range):
                return True

            if their_current_range.allows_higher(our_current_range):
                our_current_range = next(our_ranges, None)
            else:
                their_current_range = next(their_ranges, None)

        return False

    def intersect(self, other: VersionConstraint) -> VersionConstraint:
        our_ranges = iter(self._ranges)
        their_ranges = iter(other.flatten())
        new_ranges = []

        our_current_range = next(our_ranges, None)
        their_current_range = next(their_ranges, None)

        while our_current_range and their_current_range:
            intersection = our_current_range.intersect(their_current_range)

            if not intersection.is_empty():
                new_ranges.append(intersection)

            if their_current_range.allows_higher(our_current_range):
                our_current_range = next(our_ranges, None)
            else:
                their_current_range = next(their_ranges, None)

        return VersionUnion.of(*new_ranges)

    def union(self, other: VersionConstraint) -> VersionConstraint:
        return VersionUnion.of(self, other)

    def difference(self, other: VersionConstraint) -> VersionConstraint:
        our_ranges = iter(self._ranges)
        their_ranges = iter(other.flatten())
        new_ranges: list[VersionConstraint] = []

        state = {
            "current": next(our_ranges, None),
            "their_range": next(their_ranges, None),
        }

        def their_next_range() -> bool:
            state["their_range"] = next(their_ranges, None)
            if state["their_range"]:
                return True

            assert state["current"] is not None
            new_ranges.append(state["current"])
            our_current = next(our_ranges, None)
            while our_current:
                new_ranges.append(our_current)
                our_current = next(our_ranges, None)

            return False

        def our_next_range(include_current: bool = True) -> bool:
            if include_current:
                assert state["current"] is not None
                new_ranges.append(state["current"])

            our_current = next(our_ranges, None)
            if not our_current:
                return False

            state["current"] = our_current

            return True

        while True:
            if state["their_range"] is None:
                break

            assert state["current"] is not None
            if state["their_range"].is_strictly_lower(state["current"]):
                if not their_next_range():
                    break

                continue

            if state["their_range"].is_strictly_higher(state["current"]):
                if not our_next_range():
                    break

                continue

            difference = state["current"].difference(state["their_range"])
            if isinstance(difference, VersionUnion):
                assert len(difference.ranges) == 2
                new_ranges.append(difference.ranges[0])
                state["current"] = difference.ranges[-1]

                if not their_next_range():
                    break
            elif difference.is_empty():
                if not our_next_range(False):
                    break
            else:
                assert isinstance(difference, VersionRangeConstraint)
                state["current"] = difference

                if state["current"].allows_higher(state["their_range"]):
                    if not their_next_range():
                        break
                elif not our_next_range():
                    break

        if not new_ranges:
            return EmptyConstraint()

        if len(new_ranges) == 1:
            return new_ranges[0]

        return VersionUnion.of(*new_ranges)

    def flatten(self) -> list[VersionRangeConstraint]:
        return self.ranges

    @cached_property
    def _exclude_single_wildcard_range_string(self) -> str:
        """
        Helper method to convert this instance into a wild card range
        string.
        """
        if not self.excludes_single_wildcard_range:
            raise ValueError("Not a valid wildcard range")

        idx_order = (0, 1) if self._ranges[0].max else (1, 0)
        one = self._ranges[idx_order[0]]
        two = self._ranges[idx_order[1]]

        assert one.max is not None
        assert two.min is not None
        return f"!={_single_wildcard_range_string(one.max, two.min)}"

    @cached_property
    def excludes_single_wildcard_range(self) -> bool:
        if len(self._ranges) != 2:
            return False

        idx_order = (0, 1) if self._ranges[0].max else (1, 0)
        one = self._ranges[idx_order[0]]
        two = self._ranges[idx_order[1]]

        if (
            one.max is None
            or one.include_max
            or one.min is not None
            or two.min is None
            or not two.include_min
            or two.max is not None
        ):
            return False

        return _is_wildcard_candidate(two.min, one.max, inverted=True)

    @cached_property
    def excludes_single_version(self) -> bool:
        from poetry.core.constraints.version.version import Version

        return isinstance(self._inverted, Version)

    @cached_property
    def _excluded_single_version(self) -> Version:
        from poetry.core.constraints.version.version import Version

        excluded = self._inverted
        assert isinstance(excluded, Version)
        return excluded

    @cached_property
    def _inverted(self) -> VersionConstraint:
        from poetry.core.constraints.version.version_range import VersionRange

        return VersionRange().difference(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionUnion):
            return False

        return self._ranges == other.ranges

    def __hash__(self) -> int:
        return reduce(op.xor, map(hash, self._ranges))

    def __str__(self) -> str:
        if self.excludes_single_version:
            return f"!={self._excluded_single_version}"

        try:
            return self._exclude_single_wildcard_range_string
        except ValueError:
            return " || ".join([str(r) for r in self._ranges])
