from __future__ import annotations

import logging
import re
import time

from collections import defaultdict
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import cast

from cleo.ui.progress_indicator import ProgressIndicator
from poetry.core.constraints.version import EmptyConstraint
from poetry.core.constraints.version import Version
from poetry.core.packages.utils.utils import get_python_constraint_from_marker
from poetry.core.version.markers import AnyMarker
from poetry.core.version.markers import EmptyMarker
from poetry.core.version.markers import MarkerUnion

from poetry.mixology.incompatibility import Incompatibility
from poetry.mixology.incompatibility_cause import DependencyCause
from poetry.mixology.incompatibility_cause import PythonCause
from poetry.mixology.term import Term
from poetry.packages import DependencyPackage
from poetry.packages.direct_origin import DirectOrigin
from poetry.packages.package_collection import PackageCollection
from poetry.puzzle.exceptions import OverrideNeeded
from poetry.repositories.exceptions import PackageNotFound
from poetry.utils.helpers import get_file_hash


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path

    from cleo.io.io import IO
    from packaging.utils import NormalizedName
    from poetry.core.constraints.version import VersionConstraint
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.directory_dependency import DirectoryDependency
    from poetry.core.packages.file_dependency import FileDependency
    from poetry.core.packages.package import Package
    from poetry.core.packages.url_dependency import URLDependency
    from poetry.core.packages.vcs_dependency import VCSDependency
    from poetry.core.version.markers import BaseMarker

    from poetry.repositories import RepositoryPool
    from poetry.utils.env import Env


logger = logging.getLogger(__name__)


class IncompatibleConstraintsError(Exception):
    """
    Exception when there are duplicate dependencies with incompatible constraints.
    """

    def __init__(self, package: Package, *dependencies: Dependency) -> None:
        constraints = "\n".join(dep.to_pep_508() for dep in dependencies)
        super().__init__(
            f"Incompatible constraints in requirements of {package}:\n{constraints}"
        )


class Indicator(ProgressIndicator):
    CONTEXT: str | None = None

    @staticmethod
    @contextmanager
    def context() -> Iterator[Callable[[str | None], None]]:
        def _set_context(context: str | None) -> None:
            Indicator.CONTEXT = context

        yield _set_context

        _set_context(None)

    def _formatter_context(self) -> str:
        if Indicator.CONTEXT is None:
            return " "
        else:
            return f" <c1>{Indicator.CONTEXT}</> "

    def _formatter_elapsed(self) -> str:
        assert self._start_time is not None
        elapsed = time.time() - self._start_time

        return f"{elapsed:.1f}s"


class Provider:
    UNSAFE_PACKAGES: set[str] = set()

    def __init__(
        self,
        package: Package,
        pool: RepositoryPool,
        io: IO,
        *,
        installed: list[Package] | None = None,
        locked: list[Package] | None = None,
    ) -> None:
        self._package = package
        self._pool = pool
        self._direct_origin = DirectOrigin(self._pool.artifact_cache)
        self._io = io
        self._env: Env | None = None
        self._python_constraint = package.python_constraint
        self._is_debugging: bool = self._io.is_debug() or self._io.is_very_verbose()
        self._overrides: dict[DependencyPackage, dict[str, Dependency]] = {}
        self._deferred_cache: dict[Dependency, Package] = {}
        self._load_deferred = True
        self._source_root: Path | None = None
        self._installed_packages = installed if installed is not None else []
        self._direct_origin_packages: dict[str, Package] = {}
        self._locked: dict[NormalizedName, list[DependencyPackage]] = defaultdict(list)
        self._use_latest: Collection[NormalizedName] = []

        for package in locked or []:
            self._locked[package.name].append(
                DependencyPackage(package.to_dependency(), package)
            )
        for dependency_packages in self._locked.values():
            dependency_packages.sort(
                key=lambda p: p.package.version,
                reverse=True,
            )

    @property
    def pool(self) -> RepositoryPool:
        return self._pool

    @property
    def use_latest(self) -> Collection[NormalizedName]:
        return self._use_latest

    def is_debugging(self) -> bool:
        return self._is_debugging

    def set_overrides(
        self, overrides: dict[DependencyPackage, dict[str, Dependency]]
    ) -> None:
        self._overrides = overrides

    def load_deferred(self, load_deferred: bool) -> None:
        self._load_deferred = load_deferred

    @contextmanager
    def use_source_root(self, source_root: Path) -> Iterator[Provider]:
        original_source_root = self._source_root
        self._source_root = source_root

        try:
            yield self
        finally:
            self._source_root = original_source_root

    @contextmanager
    def use_environment(self, env: Env) -> Iterator[Provider]:
        original_python_constraint = self._python_constraint

        self._env = env
        self._python_constraint = Version.parse(env.marker_env["python_full_version"])

        try:
            yield self
        finally:
            self._env = None
            self._python_constraint = original_python_constraint

    @contextmanager
    def use_latest_for(self, names: Collection[NormalizedName]) -> Iterator[Provider]:
        self._use_latest = names

        try:
            yield self
        finally:
            self._use_latest = []

    @staticmethod
    def validate_package_for_dependency(
        dependency: Dependency, package: Package
    ) -> None:
        if dependency.name != package.name:
            # For now, the dependency's name must match the actual package's name
            raise RuntimeError(
                f"The dependency name for {dependency.name} does not match the actual"
                f" package's name: {package.name}"
            )

    def search_for_installed_packages(
        self,
        dependency: Dependency,
    ) -> list[Package]:
        """
        Search for installed packages, when available, that satisfy the given
        dependency.

        This is useful when dealing with packages that are under development, not
        published on package sources and/or only available via system installations.
        """
        if not self._installed_packages:
            return []

        logger.debug(
            "Falling back to installed packages to discover metadata for <c2>%s</>",
            dependency.complete_name,
        )
        packages = [
            package
            for package in self._installed_packages
            if package.satisfies(dependency, ignore_source_type=True)
        ]
        logger.debug(
            "Found <c2>%d</> compatible packages for <c2>%s</>",
            len(packages),
            dependency.complete_name,
        )
        return packages

    def search_for_direct_origin_dependency(self, dependency: Dependency) -> Package:
        package = self._deferred_cache.get(dependency)
        if package is not None:
            pass

        elif dependency.is_vcs():
            dependency = cast("VCSDependency", dependency)
            package = self._search_for_vcs(dependency)

        elif dependency.is_file():
            dependency = cast("FileDependency", dependency)
            package = self._search_for_file(dependency)

        elif dependency.is_directory():
            dependency = cast("DirectoryDependency", dependency)
            package = self._search_for_directory(dependency)

        elif dependency.is_url():
            dependency = cast("URLDependency", dependency)
            package = self._search_for_url(dependency)

        else:
            raise RuntimeError(
                f"{dependency}: unknown direct dependency type {dependency.source_type}"
            )

        if dependency.is_vcs():
            dependency._source_reference = package.source_reference
            dependency._source_resolved_reference = package.source_resolved_reference
            dependency._source_subdirectory = package.source_subdirectory

        dependency._constraint = package.version
        dependency._pretty_constraint = package.version.text

        self._deferred_cache[dependency] = package

        return package

    def search_for(self, dependency: Dependency) -> list[DependencyPackage]:
        """
        Search for the specifications that match the given dependency.

        The specifications in the returned list will be considered in reverse
        order, so the latest version ought to be last.
        """
        if dependency.is_root:
            return PackageCollection(dependency, [self._package])

        if dependency.is_direct_origin():
            package = self.search_for_direct_origin_dependency(dependency)
            self._direct_origin_packages[dependency.name] = package
            return PackageCollection(dependency, [package])

        # If we've previously found a direct-origin package that meets this dependency,
        # use it.
        #
        # We rely on the VersionSolver resolving direct-origin dependencies first.
        direct_origin_package = self._direct_origin_packages.get(dependency.name)
        if direct_origin_package and direct_origin_package.satisfies(dependency):
            packages = [direct_origin_package]
            return PackageCollection(dependency, packages)

        packages = self._pool.find_packages(dependency)

        packages.sort(
            key=lambda p: (
                not p.yanked,
                not p.is_prerelease() and not dependency.allows_prereleases(),
                p.version,
            ),
            reverse=True,
        )

        if not packages:
            packages = self.search_for_installed_packages(dependency)

        return PackageCollection(dependency, packages)

    def _search_for_vcs(self, dependency: VCSDependency) -> Package:
        """
        Search for the specifications that match the given VCS dependency.

        Basically, we clone the repository in a temporary directory
        and get the information we need by checking out the specified reference.
        """
        package = self._direct_origin.get_package_from_vcs(
            dependency.vcs,
            dependency.source,
            branch=dependency.branch,
            tag=dependency.tag,
            rev=dependency.rev,
            subdirectory=dependency.source_subdirectory,
            source_root=self._source_root
            or (self._env.path.joinpath("src") if self._env else None),
        )

        self.validate_package_for_dependency(dependency=dependency, package=package)

        package.develop = dependency.develop

        return package

    def _search_for_file(self, dependency: FileDependency) -> Package:
        dependency.validate(raise_error=True)
        package = self._direct_origin.get_package_from_file(dependency.full_path)

        self.validate_package_for_dependency(dependency=dependency, package=package)

        if dependency.base is not None:
            package.root_dir = dependency.base

        package.files = [
            {
                "file": dependency.path.name,
                "hash": "sha256:" + get_file_hash(dependency.full_path),
            }
        ]

        return package

    def _search_for_directory(self, dependency: DirectoryDependency) -> Package:
        dependency.validate(raise_error=True)
        package = self._direct_origin.get_package_from_directory(dependency.full_path)

        self.validate_package_for_dependency(dependency=dependency, package=package)

        package.develop = dependency.develop

        if dependency.base is not None:
            package.root_dir = dependency.base

        return package

    def _search_for_url(self, dependency: URLDependency) -> Package:
        package = self._direct_origin.get_package_from_url(dependency.url)

        self.validate_package_for_dependency(dependency=dependency, package=package)

        for extra in dependency.extras:
            if extra in package.extras:
                for dep in package.extras[extra]:
                    dep.activate()

                for extra_dep in package.extras[extra]:
                    package.add_dependency(extra_dep)

        return package

    def _get_dependencies_with_overrides(
        self, dependencies: list[Dependency], package: DependencyPackage
    ) -> list[Dependency]:
        overrides = self._overrides.get(package, {})
        _dependencies = []
        overridden = []
        for dep in dependencies:
            if dep.name in overrides:
                if dep.name in overridden:
                    continue

                # empty constraint is used in overrides to mark that the package has
                # already been handled and is not required for the attached markers
                if not overrides[dep.name].constraint.is_empty():
                    _dependencies.append(overrides[dep.name])
                overridden.append(dep.name)

                continue

            _dependencies.append(dep)
        return _dependencies

    def incompatibilities_for(
        self, dependency_package: DependencyPackage
    ) -> list[Incompatibility]:
        """
        Returns incompatibilities that encapsulate a given package's dependencies,
        or that it can't be safely selected.

        If multiple subsequent versions of this package have the same
        dependencies, this will return incompatibilities that reflect that. It
        won't return incompatibilities that have already been returned by a
        previous call to _incompatibilities_for().
        """
        package = dependency_package.package
        if package.is_root():
            dependencies = package.all_requires
        else:
            dependencies = package.requires

            if not package.python_constraint.allows_all(self._python_constraint):
                transitive_python_constraint = get_python_constraint_from_marker(
                    dependency_package.dependency.transitive_marker
                )
                intersection = package.python_constraint.intersect(
                    transitive_python_constraint
                )
                difference = transitive_python_constraint.difference(intersection)

                # The difference is only relevant if it intersects
                # the root package python constraint
                difference = difference.intersect(self._python_constraint)
                if (
                    transitive_python_constraint.is_any()
                    or self._python_constraint.intersect(
                        dependency_package.dependency.python_constraint
                    ).is_empty()
                    or intersection.is_empty()
                    or not difference.is_empty()
                ):
                    return [
                        Incompatibility(
                            [Term(package.to_dependency(), True)],
                            PythonCause(
                                package.python_versions, str(self._python_constraint)
                            ),
                        )
                    ]

        _dependencies = [
            dep
            for dep in dependencies
            if dep.name not in self.UNSAFE_PACKAGES
            and self._python_constraint.allows_any(dep.python_constraint)
            and (not self._env or dep.marker.validate(self._env.marker_env))
        ]
        dependencies = self._get_dependencies_with_overrides(
            _dependencies, dependency_package
        )

        return [
            Incompatibility(
                [Term(package.to_dependency(), True), Term(dep, False)],
                DependencyCause(),
            )
            for dep in dependencies
        ]

    def complete_package(
        self, dependency_package: DependencyPackage
    ) -> DependencyPackage:
        package = dependency_package.package
        dependency = dependency_package.dependency

        if package.is_root():
            dependency_package = dependency_package.clone()
            package = dependency_package.package
            dependency = dependency_package.dependency
            requires = package.all_requires
        elif package.is_direct_origin():
            requires = package.requires
        else:
            try:
                dependency_package = DependencyPackage(
                    dependency,
                    self._pool.package(
                        package.pretty_name,
                        package.version,
                        extras=list(dependency.extras),
                        repository_name=dependency.source_name,
                    ),
                )
            except PackageNotFound as e:
                try:
                    dependency_package = next(
                        DependencyPackage(dependency, pkg)
                        for pkg in self.search_for_installed_packages(dependency)
                    )
                except StopIteration:
                    raise e from e

            package = dependency_package.package
            dependency = dependency_package.dependency
            requires = package.requires

        optional_dependencies = []
        _dependencies = []

        # If some extras/features were required, we need to
        # add a special dependency representing the base package
        # to the current package
        if dependency.extras:
            for extra in dependency.extras:
                if extra not in package.extras:
                    continue

                optional_dependencies += [d.name for d in package.extras[extra]]

            dependency_package = dependency_package.with_features(
                list(dependency.extras)
            )
            package = dependency_package.package
            dependency = dependency_package.dependency
            new_dependency = package.without_features().to_dependency()

            # When adding dependency foo[extra] -> foo, preserve foo's source, if it's
            # specified. This prevents us from trying to get foo from PyPI
            # when user explicitly set repo for foo[extra].
            if not new_dependency.source_name and dependency.source_name:
                new_dependency.source_name = dependency.source_name

            _dependencies.append(new_dependency)

        for dep in requires:
            if not self._python_constraint.allows_any(dep.python_constraint):
                continue

            if dep.name in self.UNSAFE_PACKAGES:
                continue

            if self._env and not dep.marker.validate(self._env.marker_env):
                continue

            if not package.is_root() and (
                (dep.is_optional() and dep.name not in optional_dependencies)
                or (
                    dep.in_extras
                    and not set(dep.in_extras).intersection(dependency.extras)
                )
            ):
                continue

            _dependencies.append(dep)

        if self._load_deferred:
            # Retrieving constraints for deferred dependencies
            for dep in _dependencies:
                if dep.is_direct_origin():
                    locked = self.get_locked(dep)
                    # If lock file contains exactly the same URL and reference
                    # (commit hash) of dependency as is requested,
                    # do not analyze it again: nothing could have changed.
                    if locked is not None and locked.package.is_same_package_as(dep):
                        continue
                    self.search_for_direct_origin_dependency(dep)

        dependencies = self._get_dependencies_with_overrides(
            _dependencies, dependency_package
        )

        # Searching for duplicate dependencies
        #
        # If the duplicate dependencies have the same constraint,
        # the requirements will be merged.
        #
        # For instance:
        #   • enum34; python_version=="2.7"
        #   • enum34; python_version=="3.3"
        #
        # will become:
        #   • enum34; python_version=="2.7" or python_version=="3.3"
        #
        # If the duplicate dependencies have different constraints
        # we have to split the dependency graph.
        #
        # An example of this is:
        #   • pypiwin32 (220); sys_platform == "win32" and python_version >= "3.6"
        #   • pypiwin32 (219); sys_platform == "win32" and python_version < "3.6"
        duplicates: dict[str, list[Dependency]] = defaultdict(list)
        for dep in dependencies:
            duplicates[dep.complete_name].append(dep)

        dependencies = []
        for dep_name, deps in duplicates.items():
            if len(deps) == 1:
                dependencies.append(deps[0])
                continue

            self.debug(f"<debug>Duplicate dependencies for {dep_name}</debug>")

            # Group dependencies for merging.
            # We must not merge dependencies from different sources!
            dep_groups = self._group_by_source(deps)
            deps = []
            for group in dep_groups:
                # In order to reduce the number of overrides we merge duplicate
                # dependencies by constraint. For instance, if we have:
                #   • foo (>=2.0) ; python_version >= "3.6" and python_version < "3.7"
                #   • foo (>=2.0) ; python_version >= "3.7"
                # we can avoid two overrides by merging them to:
                #   • foo (>=2.0) ; python_version >= "3.6"
                # However, if we want to merge dependencies by constraint we have to
                # merge dependencies by markers first in order to avoid unnecessary
                # solver failures. For instance, if we have:
                #   • foo (>=2.0) ; python_version >= "3.6" and python_version < "3.7"
                #   • foo (>=2.0) ; python_version >= "3.7"
                #   • foo (<2.1) ; python_version >= "3.7"
                # we must not merge the first two constraints but the last two:
                #   • foo (>=2.0) ; python_version >= "3.6" and python_version < "3.7"
                #   • foo (>=2.0,<2.1) ; python_version >= "3.7"
                deps += self._merge_dependencies_by_constraint(
                    self._merge_dependencies_by_marker(group)
                )
            if len(deps) == 1:
                self.debug(f"<debug>Merging requirements for {deps[0]!s}</debug>")
                dependencies.append(deps[0])
                continue

            # We leave dependencies as-is if they have the same
            # python/platform constraints.
            # That way the resolver will pickup the conflict
            # and display a proper error.
            seen = set()
            for dep in deps:
                pep_508_dep = dep.to_pep_508(False)
                if ";" not in pep_508_dep:
                    _requirements = ""
                else:
                    _requirements = pep_508_dep.split(";")[1].strip()

                if _requirements not in seen:
                    seen.add(_requirements)

            if len(deps) != len(seen):
                for dep in deps:
                    dependencies.append(dep)

                continue

            # At this point, we raise an exception that will
            # tell the solver to make new resolutions with specific overrides.
            #
            # For instance, if the foo (1.2.3) package has the following dependencies:
            #   • bar (>=2.0) ; python_version >= "3.6"
            #   • bar (<2.0) ; python_version < "3.6"
            #
            # then the solver will need to make two new resolutions
            # with the following overrides:
            #   • {<Package foo (1.2.3): {"bar": <Dependency bar (>=2.0)>}
            #   • {<Package foo (1.2.3): {"bar": <Dependency bar (<2.0)>}

            def fmt_warning(d: Dependency) -> str:
                dependency_marker = d.marker if not d.marker.is_any() else "*"
                return (
                    f"<c1>{d.name}</c1> <fg=default>(<c2>{d.pretty_constraint}</c2>)</>"
                    f" with markers <b>{dependency_marker}</b>"
                )

            warnings = ", ".join(fmt_warning(d) for d in deps[:-1])
            warnings += f" and {fmt_warning(deps[-1])}"
            self.debug(
                f"<warning>Different requirements found for {warnings}.</warning>"
            )

            deps = self._handle_any_marker_dependencies(package, deps)

            overrides = []
            overrides_marker_intersection: BaseMarker = AnyMarker()
            for dep_overrides in self._overrides.values():
                for dep in dep_overrides.values():
                    overrides_marker_intersection = (
                        overrides_marker_intersection.intersect(dep.marker)
                    )
            for dep in deps:
                if not overrides_marker_intersection.intersect(dep.marker).is_empty():
                    current_overrides = self._overrides.copy()
                    package_overrides = current_overrides.get(
                        dependency_package, {}
                    ).copy()
                    package_overrides.update({dep.name: dep})
                    current_overrides.update({dependency_package: package_overrides})
                    overrides.append(current_overrides)

            if overrides:
                raise OverrideNeeded(*overrides)

        # Modifying dependencies as needed
        clean_dependencies = []
        for dep in dependencies:
            if not dependency.transitive_marker.without_extras().is_any():
                marker_intersection = (
                    dependency.transitive_marker.without_extras().intersect(
                        dep.marker.without_extras()
                    )
                )
                if marker_intersection.is_empty():
                    # The dependency is not needed, since the markers specified
                    # for the current package selection are not compatible with
                    # the markers for the current dependency, so we skip it
                    continue

                dep.transitive_marker = marker_intersection

            if not dependency.python_constraint.is_any():
                python_constraint_intersection = dep.python_constraint.intersect(
                    dependency.python_constraint
                )
                if python_constraint_intersection.is_empty():
                    # This dependency is not needed under current python constraint.
                    continue
                dep.transitive_python_versions = str(python_constraint_intersection)

            clean_dependencies.append(dep)

        package = package.with_dependency_groups([], only=True)
        dependency_package = DependencyPackage(dependency, package)

        for dep in clean_dependencies:
            package.add_dependency(dep)

        return dependency_package

    def get_locked(self, dependency: Dependency) -> DependencyPackage | None:
        if dependency.name in self._use_latest:
            return None

        locked = self._locked.get(dependency.name, [])
        for dependency_package in locked:
            package = dependency_package.package
            if package.satisfies(dependency):
                return DependencyPackage(dependency, package)
        return None

    def debug(self, message: str, depth: int = 0) -> None:
        if not (self._io.is_very_verbose() or self._io.is_debug()):
            return

        if message.startswith("fact:"):
            if "depends on" in message:
                m = re.match(r"fact: (.+?) depends on (.+?) \((.+?)\)", message)
                if m is None:
                    raise ValueError(f"Unable to parse fact: {message}")
                m2 = re.match(r"(.+?) \((.+?)\)", m.group(1))
                if m2:
                    name = m2.group(1)
                    version = f" (<c2>{m2.group(2)}</c2>)"
                else:
                    name = m.group(1)
                    version = ""

                message = (
                    f"<fg=blue>fact</>: <c1>{name}</c1>{version} "
                    f"depends on <c1>{m.group(2)}</c1> (<c2>{m.group(3)}</c2>)"
                )
            elif " is " in message:
                message = re.sub(
                    "fact: (.+) is (.+)",
                    "<fg=blue>fact</>: <c1>\\1</c1> is <c2>\\2</c2>",
                    message,
                )
            else:
                message = re.sub(
                    r"(?<=: )(.+?) \((.+?)\)", "<c1>\\1</c1> (<c2>\\2</c2>)", message
                )
                message = f"<fg=blue>fact</>: {message.split('fact: ')[1]}"
        elif message.startswith("selecting "):
            message = re.sub(
                r"selecting (.+?) \((.+?)\)",
                "<fg=blue>selecting</> <c1>\\1</c1> (<c2>\\2</c2>)",
                message,
            )
        elif message.startswith("derived:"):
            m = re.match(r"derived: (.+?) \((.+?)\)$", message)
            if m:
                message = (
                    f"<fg=blue>derived</>: <c1>{m.group(1)}</c1>"
                    f" (<c2>{m.group(2)}</c2>)"
                )
            else:
                message = (
                    f"<fg=blue>derived</>: <c1>{message.split('derived: ')[1]}</c1>"
                )
        elif message.startswith("conflict:"):
            m = re.match(r"conflict: (.+?) depends on (.+?) \((.+?)\)", message)
            if m:
                m2 = re.match(r"(.+?) \((.+?)\)", m.group(1))
                if m2:
                    name = m2.group(1)
                    version = f" (<c2>{m2.group(2)}</c2>)"
                else:
                    name = m.group(1)
                    version = ""

                message = (
                    f"<fg=red;options=bold>conflict</>: <c1>{name}</c1>{version} "
                    f"depends on <c1>{m.group(2)}</c1> (<c2>{m.group(3)}</c2>)"
                )
            else:
                message = (
                    "<fg=red;options=bold>conflict</>:"
                    f" {message.split('conflict: ')[1]}"
                )

        message = message.replace("! ", "<error>!</error> ")

        if self.is_debugging():
            debug_info = str(message)
            debug_info = (
                "\n".join(
                    [
                        f"<debug>{str(depth).rjust(4)}:</debug> {s}"
                        for s in debug_info.split("\n")
                    ]
                )
                + "\n"
            )

            self._io.write(debug_info)

    def _group_by_source(
        self, dependencies: Iterable[Dependency]
    ) -> list[list[Dependency]]:
        """
        Takes a list of dependencies and returns a list of groups of dependencies,
        each group containing all dependencies from the same source.
        """
        groups: list[list[Dependency]] = []
        for dep in dependencies:
            for group in groups:
                if (
                    dep.is_same_source_as(group[0])
                    and dep.source_name == group[0].source_name
                ):
                    group.append(dep)
                    break
            else:
                groups.append([dep])
        return groups

    def _merge_dependencies_by_constraint(
        self, dependencies: Iterable[Dependency]
    ) -> list[Dependency]:
        """
        Merge dependencies with the same constraint
        by building a union of their markers.
        """
        by_constraint: dict[VersionConstraint, list[Dependency]] = defaultdict(list)
        for dep in dependencies:
            by_constraint[dep.constraint].append(dep)
        for constraint, _deps in by_constraint.items():
            new_markers = [dep.marker for dep in _deps]

            dep = _deps[0]

            # Union with EmptyMarker is to make sure we get the benefit of marker
            # simplifications.
            dep.marker = MarkerUnion(*new_markers).union(EmptyMarker())
            by_constraint[constraint] = [dep]

        return [value[0] for value in by_constraint.values()]

    def _merge_dependencies_by_marker(
        self, dependencies: Iterable[Dependency]
    ) -> list[Dependency]:
        """
        Merge dependencies with the same marker
        by building the intersection of their constraints.
        """
        by_marker: dict[BaseMarker, list[Dependency]] = defaultdict(list)
        for dep in dependencies:
            by_marker[dep.marker].append(dep)
        deps = []
        for _deps in by_marker.values():
            if len(_deps) == 1:
                deps.extend(_deps)
            else:
                new_constraint = _deps[0].constraint
                for dep in _deps[1:]:
                    new_constraint = new_constraint.intersect(dep.constraint)
                if new_constraint.is_empty():
                    # leave dependencies as-is so the resolver will pickup
                    # the conflict and display a proper error.
                    deps.extend(_deps)
                else:
                    self.debug(
                        f"<debug>Merging constraints for {_deps[0].name} for"
                        f" marker {_deps[0].marker}</debug>"
                    )
                    deps.append(_deps[0].with_constraint(new_constraint))
        return deps

    def _handle_any_marker_dependencies(
        self, package: Package, dependencies: list[Dependency]
    ) -> list[Dependency]:
        """
        We need to check if one of the duplicate dependencies
        has no markers. If there is one, we need to change its
        environment markers to the inverse of the union of the
        other dependencies markers.
        For instance, if we have the following dependencies:
          • ipython
          • ipython (1.2.4) ; implementation_name == "pypy"

        the marker for `ipython` will become `implementation_name != "pypy"`.

        Further, we have to merge the constraints of the requirements
        without markers into the constraints of the requirements with markers.
        for instance, if we have the following dependencies:
          • foo (>= 1.2)
          • foo (!= 1.2.1) ; python == 3.10

        the constraint for the second entry will become (!= 1.2.1, >= 1.2).
        """
        any_markers_dependencies = [d for d in dependencies if d.marker.is_any()]
        other_markers_dependencies = [d for d in dependencies if not d.marker.is_any()]

        if any_markers_dependencies:
            for dep_other in other_markers_dependencies:
                new_constraint = dep_other.constraint
                for dep_any in any_markers_dependencies:
                    new_constraint = new_constraint.intersect(dep_any.constraint)
                if new_constraint.is_empty():
                    raise IncompatibleConstraintsError(
                        package, dep_other, *any_markers_dependencies
                    )
                dep_other.constraint = new_constraint

        marker = other_markers_dependencies[0].marker
        for other_dep in other_markers_dependencies[1:]:
            marker = marker.union(other_dep.marker)
        inverted_marker = marker.invert()

        if (
            not inverted_marker.is_empty()
            and self._python_constraint.allows_any(
                get_python_constraint_from_marker(inverted_marker)
            )
            and (not self._env or inverted_marker.validate(self._env.marker_env))
        ):
            if any_markers_dependencies:
                for dep_any in any_markers_dependencies:
                    dep_any.marker = inverted_marker
            else:
                # If there is no any marker dependency
                # and the inverted marker is not empty,
                # a dependency with the inverted union of all markers is required
                # in order to not miss other dependencies later, for instance:
                #   • foo (1.0) ; python == 3.7
                #   • foo (2.0) ; python == 3.8
                #   • bar (2.0) ; python == 3.8
                #   • bar (3.0) ; python == 3.9
                #
                # the last dependency would be missed without this,
                # because the intersection with both foo dependencies is empty.
                inverted_marker_dep = dependencies[0].with_constraint(EmptyConstraint())
                inverted_marker_dep.marker = inverted_marker
                dependencies.append(inverted_marker_dep)
        else:
            dependencies = other_markers_dependencies
        return dependencies
