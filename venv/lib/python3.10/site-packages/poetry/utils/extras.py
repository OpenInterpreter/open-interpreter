from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable
    from collections.abc import Mapping

    from packaging.utils import NormalizedName
    from poetry.core.packages.package import Package


def get_extra_package_names(
    packages: Iterable[Package],
    extras: Mapping[NormalizedName, Iterable[NormalizedName]],
    extra_names: Collection[NormalizedName],
) -> set[NormalizedName]:
    """
    Returns all package names required by the given extras.

    :param packages: A collection of packages, such as from Repository.packages
    :param extras: A mapping of `extras` names to lists of package names, as defined
        in the `extras` section of `poetry.lock`.
    :param extra_names: A list of strings specifying names of extra groups to resolve.
    """
    from packaging.utils import canonicalize_name

    if not extra_names:
        return set()

    # lookup for packages by name, faster than looping over packages repeatedly
    packages_by_name = {package.name: package for package in packages}

    # Depth-first search, with our entry points being the packages directly required by
    # extras.
    seen_package_names = set()
    stack = [
        canonicalize_name(extra_package_name)
        for extra_name in extra_names
        for extra_package_name in extras.get(extra_name, ())
    ]

    while stack:
        package_name = stack.pop()

        # We expect to find all packages, but can just carry on if we don't.
        package = packages_by_name.get(package_name)
        if package is None or package.name in seen_package_names:
            continue

        seen_package_names.add(package.name)

        stack += [dependency.name for dependency in package.requires]

    return seen_package_names
