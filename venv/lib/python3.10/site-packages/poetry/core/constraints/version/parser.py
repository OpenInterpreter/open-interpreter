from __future__ import annotations

import functools
import re

from typing import TYPE_CHECKING

from poetry.core.constraints.version.exceptions import ParseConstraintError
from poetry.core.version.exceptions import InvalidVersion


if TYPE_CHECKING:
    from poetry.core.constraints.version.version import Version
    from poetry.core.constraints.version.version_constraint import VersionConstraint


@functools.lru_cache(maxsize=None)
def parse_constraint(constraints: str) -> VersionConstraint:
    return _parse_constraint(constraints=constraints)


def parse_marker_version_constraint(constraints: str) -> VersionConstraint:
    return _parse_constraint(constraints=constraints, is_marker_constraint=True)


def _parse_constraint(
    constraints: str, *, is_marker_constraint: bool = False
) -> VersionConstraint:
    if constraints == "*":
        from poetry.core.constraints.version.version_range import VersionRange

        return VersionRange()

    or_constraints = re.split(r"\s*\|\|?\s*", constraints.strip())
    or_groups = []
    for constraints in or_constraints:
        # allow trailing commas for robustness (even though it may not be
        # standard-compliant it seems to occur in some packages)
        constraints = constraints.rstrip(",").rstrip()
        and_constraints = re.split(
            "(?<!^)(?<![~=>< ,]) *(?<!-)[, ](?!-) *(?!,|$)", constraints
        )
        constraint_objects = []

        if len(and_constraints) > 1:
            for constraint in and_constraints:
                constraint_objects.append(
                    parse_single_constraint(
                        constraint, is_marker_constraint=is_marker_constraint
                    )
                )
        else:
            constraint_objects.append(
                parse_single_constraint(
                    and_constraints[0], is_marker_constraint=is_marker_constraint
                )
            )

        if len(constraint_objects) == 1:
            constraint = constraint_objects[0]
        else:
            constraint = constraint_objects[0]
            for next_constraint in constraint_objects[1:]:
                constraint = constraint.intersect(next_constraint)

        or_groups.append(constraint)

    if len(or_groups) == 1:
        return or_groups[0]
    else:
        from poetry.core.constraints.version.version_union import VersionUnion

        return VersionUnion.of(*or_groups)


def parse_single_constraint(
    constraint: str, *, is_marker_constraint: bool = False
) -> VersionConstraint:
    from poetry.core.constraints.version.patterns import BASIC_CONSTRAINT
    from poetry.core.constraints.version.patterns import CARET_CONSTRAINT
    from poetry.core.constraints.version.patterns import TILDE_CONSTRAINT
    from poetry.core.constraints.version.patterns import TILDE_PEP440_CONSTRAINT
    from poetry.core.constraints.version.patterns import X_CONSTRAINT
    from poetry.core.constraints.version.version import Version
    from poetry.core.constraints.version.version_range import VersionRange
    from poetry.core.constraints.version.version_union import VersionUnion

    m = re.match(r"(?i)^v?[xX*](\.[xX*])*$", constraint)
    if m:
        return VersionRange()

    # Tilde range
    m = TILDE_CONSTRAINT.match(constraint)
    if m:
        try:
            version = Version.parse(m.group("version"))
        except InvalidVersion as e:
            raise ParseConstraintError(
                f"Could not parse version constraint: {constraint}"
            ) from e

        high = version.stable.next_minor()
        if version.release.precision == 1:
            high = version.stable.next_major()

        return VersionRange(version, high, include_min=True)

    # PEP 440 Tilde range (~=)
    m = TILDE_PEP440_CONSTRAINT.match(constraint)
    if m:
        try:
            version = Version.parse(m.group("version"))
        except InvalidVersion as e:
            raise ParseConstraintError(
                f"Could not parse version constraint: {constraint}"
            ) from e

        if version.release.precision == 2:
            high = version.stable.next_major()
        else:
            high = version.stable.next_minor()

        return VersionRange(version, high, include_min=True)

    # Caret range
    m = CARET_CONSTRAINT.match(constraint)
    if m:
        try:
            version = Version.parse(m.group("version"))
        except InvalidVersion as e:
            raise ParseConstraintError(
                f"Could not parse version constraint: {constraint}"
            ) from e

        return VersionRange(version, version.next_breaking(), include_min=True)

    # X Range
    m = X_CONSTRAINT.match(constraint)
    if m:
        op = m.group("op")

        try:
            return _make_x_constraint_range(
                version=Version.parse(m.group("version")),
                invert=op == "!=",
                is_marker_constraint=is_marker_constraint,
            )
        except ValueError:
            raise ValueError(f"Could not parse version constraint: {constraint}")

    # Basic comparator
    m = BASIC_CONSTRAINT.match(constraint)
    if m:
        op = m.group("op")
        version_string = m.group("version")

        if version_string == "dev":
            version_string = "0.0-dev"

        try:
            version = Version.parse(version_string)
        except InvalidVersion as e:
            raise ParseConstraintError(
                f"Could not parse version constraint: {constraint}"
            ) from e

        if op == "<":
            return VersionRange(max=version)
        if op == "<=":
            return VersionRange(max=version, include_max=True)
        if op == ">":
            return VersionRange(min=version)
        if op == ">=":
            return VersionRange(min=version, include_min=True)

        if m.group("wildcard") is not None:
            return _make_x_constraint_range(
                version=version,
                invert=op == "!=",
                is_marker_constraint=is_marker_constraint,
            )

        if op == "!=":
            return VersionUnion(VersionRange(max=version), VersionRange(min=version))

        return version

    raise ParseConstraintError(f"Could not parse version constraint: {constraint}")


def _make_x_constraint_range(
    version: Version, *, invert: bool = False, is_marker_constraint: bool = False
) -> VersionConstraint:
    from poetry.core.constraints.version.version_range import VersionRange

    if version.is_postrelease():
        _next = version.next_postrelease()
    elif version.is_stable():
        _next = version.next_stable()
    elif version.is_prerelease():
        _next = version.next_prerelease()
    elif version.is_devrelease():
        _next = version.next_devrelease()
    else:
        raise RuntimeError("version is neither stable, nor pre-release nor dev-release")

    _min = version
    _max = _next

    if not is_marker_constraint:
        _min = _min.first_devrelease()
        if not _max.is_devrelease():
            _max = _max.first_devrelease()

    result = VersionRange(_min, _max, include_min=True)

    if invert:
        return VersionRange().difference(result)

    return result
