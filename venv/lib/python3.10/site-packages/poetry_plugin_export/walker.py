from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name
from poetry.core.constraints.version.util import constraint_regions
from poetry.core.version.markers import AnyMarker
from poetry.core.version.markers import SingleMarker
from poetry.packages import DependencyPackage
from poetry.utils.extras import get_extra_package_names


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable
    from collections.abc import Iterator

    from packaging.utils import NormalizedName
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.package import Package
    from poetry.core.version.markers import BaseMarker
    from poetry.packages import Locker


def get_python_version_region_markers(packages: list[Package]) -> list[BaseMarker]:
    markers = []

    regions = constraint_regions([package.python_constraint for package in packages])
    for region in regions:
        marker: BaseMarker = AnyMarker()
        if region.min is not None:
            min_operator = ">=" if region.include_min else ">"
            marker_name = (
                "python_full_version" if region.min.precision > 2 else "python_version"
            )
            lo = SingleMarker(marker_name, f"{min_operator} {region.min}")
            marker = marker.intersect(lo)

        if region.max is not None:
            max_operator = "<=" if region.include_max else "<"
            marker_name = (
                "python_full_version" if region.max.precision > 2 else "python_version"
            )
            hi = SingleMarker(marker_name, f"{max_operator} {region.max}")
            marker = marker.intersect(hi)

        markers.append(marker)

    return markers


def get_project_dependency_packages(
    locker: Locker,
    project_requires: list[Dependency],
    root_package_name: NormalizedName,
    project_python_marker: BaseMarker | None = None,
    extras: Collection[NormalizedName] = (),
) -> Iterator[DependencyPackage]:
    # Apply the project python marker to all requirements.
    if project_python_marker is not None:
        marked_requires: list[Dependency] = []
        for require in project_requires:
            require = require.clone()
            require.marker = require.marker.intersect(project_python_marker)
            marked_requires.append(require)
        project_requires = marked_requires

    repository = locker.locked_repository()

    # Build a set of all packages required by our selected extras
    locked_extras = {
        canonicalize_name(extra): [
            canonicalize_name(dependency) for dependency in dependencies
        ]
        for extra, dependencies in locker.lock_data.get("extras", {}).items()
    }
    extra_package_names = get_extra_package_names(
        repository.packages,
        locked_extras,
        extras,
    )

    # If a package is optional and we haven't opted in to it, do not select
    selected = []
    for dependency in project_requires:
        try:
            package = repository.find_packages(dependency=dependency)[0]
        except IndexError:
            continue

        if package.optional and package.name not in extra_package_names:
            # a package is locked as optional, but is not activated via extras
            continue

        selected.append(dependency)

    for package, dependency in get_project_dependencies(
        project_requires=selected,
        locked_packages=repository.packages,
        root_package_name=root_package_name,
    ):
        yield DependencyPackage(dependency=dependency, package=package)


def get_project_dependencies(
    project_requires: list[Dependency],
    locked_packages: list[Package],
    root_package_name: NormalizedName,
) -> Iterable[tuple[Package, Dependency]]:
    # group packages entries by name, this is required because requirement might use
    # different constraints.
    packages_by_name: dict[str, list[Package]] = {}
    for pkg in locked_packages:
        if pkg.name not in packages_by_name:
            packages_by_name[pkg.name] = []
        packages_by_name[pkg.name].append(pkg)

    # Put higher versions first so that we prefer them.
    for packages in packages_by_name.values():
        packages.sort(
            key=lambda package: package.version,
            reverse=True,
        )

    nested_dependencies = walk_dependencies(
        dependencies=project_requires,
        packages_by_name=packages_by_name,
        root_package_name=root_package_name,
    )

    return nested_dependencies.items()


def walk_dependencies(
    dependencies: list[Dependency],
    packages_by_name: dict[str, list[Package]],
    root_package_name: NormalizedName,
) -> dict[Package, Dependency]:
    nested_dependencies: dict[Package, Dependency] = {}

    visited: set[tuple[Dependency, BaseMarker]] = set()
    while dependencies:
        requirement = dependencies.pop(0)
        if (requirement, requirement.marker) in visited:
            continue
        if requirement.name == root_package_name:
            continue
        visited.add((requirement, requirement.marker))

        locked_package = get_locked_package(
            requirement, packages_by_name, nested_dependencies
        )

        if not locked_package:
            raise RuntimeError(f"Dependency walk failed at {requirement}")

        if requirement.extras:
            locked_package = locked_package.with_features(requirement.extras)

        # create dependency from locked package to retain dependency metadata
        # if this is not done, we can end-up with incorrect nested dependencies
        constraint = requirement.constraint
        marker = requirement.marker
        requirement = locked_package.to_dependency()
        requirement.marker = requirement.marker.intersect(marker)

        requirement.constraint = constraint

        for require in locked_package.requires:
            if require.is_optional() and not any(
                require in locked_package.extras.get(feature, ())
                for feature in locked_package.features
            ):
                continue

            base_marker = require.marker.intersect(requirement.marker.without_extras())

            if not base_marker.is_empty():
                # So as to give ourselves enough flexibility in choosing a solution,
                # we need to split the world up into the python version ranges that
                # this package might care about.
                #
                # We create a marker for all of the possible regions, and add a
                # requirement for each separately.
                candidates = packages_by_name.get(require.name, [])
                region_markers = get_python_version_region_markers(candidates)
                for region_marker in region_markers:
                    marker = region_marker.intersect(base_marker)
                    if not marker.is_empty():
                        require2 = require.clone()
                        require2.marker = marker
                        dependencies.append(require2)

        key = locked_package
        if key not in nested_dependencies:
            nested_dependencies[key] = requirement
        else:
            nested_dependencies[key].marker = nested_dependencies[key].marker.union(
                requirement.marker
            )

    return nested_dependencies


def get_locked_package(
    dependency: Dependency,
    packages_by_name: dict[str, list[Package]],
    decided: dict[Package, Dependency] | None = None,
) -> Package | None:
    """
    Internal helper to identify corresponding locked package using dependency
    version constraints.
    """
    decided = decided or {}

    candidates = packages_by_name.get(dependency.name, [])

    # If we've previously chosen a version of this package that is compatible with
    # the current requirement, we are forced to stick with it.  (Else we end up with
    # different versions of the same package at the same time.)
    overlapping_candidates = set()
    for package in candidates:
        old_decision = decided.get(package)
        if (
            old_decision is not None
            and not old_decision.marker.intersect(dependency.marker).is_empty()
        ):
            overlapping_candidates.add(package)

    # If we have more than one overlapping candidate, we've run into trouble.
    if len(overlapping_candidates) > 1:
        return None

    # Get the packages that are consistent with this dependency.
    compatible_candidates = [
        package
        for package in candidates
        if package.python_constraint.allows_all(dependency.python_constraint)
        and dependency.constraint.allows(package.version)
        and (dependency.source_type is None or dependency.is_same_source_as(package))
    ]

    # If we have an overlapping candidate, we must use it.
    if overlapping_candidates:
        filtered_compatible_candidates = [
            package
            for package in compatible_candidates
            if package in overlapping_candidates
        ]

        if not filtered_compatible_candidates:
            # TODO: Support this case:
            # https://github.com/python-poetry/poetry-plugin-export/issues/183
            raise DependencyWalkerError(
                f"The `{dependency.name}` package has the following compatible"
                f" candidates `{compatible_candidates}`;  but, the exporter dependency"
                f" walker previously elected `{overlapping_candidates.pop()}` which is"
                f" not compatible with the dependency `{dependency}`. Please contribute"
                " to `poetry-plugin-export` to solve this problem."
            )

        compatible_candidates = filtered_compatible_candidates

    return next(iter(compatible_candidates), None)


class DependencyWalkerError(Exception):
    pass
