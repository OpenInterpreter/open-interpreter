from __future__ import annotations

import time

from collections import defaultdict
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import FrozenSet
from typing import Tuple
from typing import TypeVar

from poetry.mixology import resolve_version
from poetry.mixology.failure import SolveFailure
from poetry.puzzle.exceptions import OverrideNeeded
from poetry.puzzle.exceptions import SolverProblemError
from poetry.puzzle.provider import Indicator
from poetry.puzzle.provider import Provider


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterator

    from cleo.io.io import IO
    from packaging.utils import NormalizedName
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.package import Package
    from poetry.core.packages.project_package import ProjectPackage

    from poetry.packages import DependencyPackage
    from poetry.puzzle.transaction import Transaction
    from poetry.repositories import RepositoryPool
    from poetry.utils.env import Env


class Solver:
    def __init__(
        self,
        package: ProjectPackage,
        pool: RepositoryPool,
        installed: list[Package],
        locked: list[Package],
        io: IO,
    ) -> None:
        self._package = package
        self._pool = pool
        self._installed_packages = installed
        self._locked_packages = locked
        self._io = io

        self._provider = Provider(
            self._package, self._pool, self._io, installed=installed, locked=locked
        )
        self._overrides: list[dict[DependencyPackage, dict[str, Dependency]]] = []

    @property
    def provider(self) -> Provider:
        return self._provider

    @contextmanager
    def use_environment(self, env: Env) -> Iterator[None]:
        with self.provider.use_environment(env):
            yield

    def solve(
        self, use_latest: Collection[NormalizedName] | None = None
    ) -> Transaction:
        from poetry.puzzle.transaction import Transaction

        with self._progress(), self._provider.use_latest_for(use_latest or []):
            start = time.time()
            packages, depths = self._solve()
            end = time.time()

            if len(self._overrides) > 1:
                self._provider.debug(
                    # ignore the warning as provider does not do interpolation
                    f"Complete version solving took {end - start:.3f}"
                    f" seconds with {len(self._overrides)} overrides"
                )
                self._provider.debug(
                    # ignore the warning as provider does not do interpolation
                    "Resolved with overrides:"
                    f" {', '.join(f'({b})' for b in self._overrides)}"
                )

        for p in packages:
            if p.yanked:
                message = (
                    f"The locked version {p.pretty_version} for {p.pretty_name} is a"
                    " yanked version."
                )
                if p.yanked_reason:
                    message += f" Reason for being yanked: {p.yanked_reason}"
                self._io.write_error_line(f"<warning>Warning: {message}</warning>")

        return Transaction(
            self._locked_packages,
            list(zip(packages, depths)),
            installed_packages=self._installed_packages,
            root_package=self._package,
        )

    @contextmanager
    def _progress(self) -> Iterator[None]:
        if not self._io.output.is_decorated() or self._provider.is_debugging():
            self._io.write_line("Resolving dependencies...")
            yield
        else:
            indicator = Indicator(
                self._io, "{message}{context}<debug>({elapsed:2s})</debug>"
            )

            with indicator.auto(
                "<info>Resolving dependencies...</info>",
                "<info>Resolving dependencies...</info>",
            ):
                yield

    def _solve_in_compatibility_mode(
        self,
        overrides: tuple[dict[DependencyPackage, dict[str, Dependency]], ...],
    ) -> tuple[list[Package], list[int]]:
        packages = []
        depths = []
        for override in overrides:
            self._provider.debug(
                # ignore the warning as provider does not do interpolation
                "<comment>Retrying dependency resolution "
                f"with the following overrides ({override}).</comment>"
            )
            self._provider.set_overrides(override)
            _packages, _depths = self._solve()
            for index, package in enumerate(_packages):
                if package not in packages:
                    packages.append(package)
                    depths.append(_depths[index])
                    continue
                else:
                    idx = packages.index(package)
                    pkg = packages[idx]
                    depths[idx] = max(depths[idx], _depths[index])

                    for dep in package.requires:
                        if dep not in pkg.requires:
                            pkg.add_dependency(dep)

        return packages, depths

    def _solve(self) -> tuple[list[Package], list[int]]:
        if self._provider._overrides:
            self._overrides.append(self._provider._overrides)

        try:
            result = resolve_version(self._package, self._provider)

            packages = result.packages
        except OverrideNeeded as e:
            return self._solve_in_compatibility_mode(e.overrides)
        except SolveFailure as e:
            raise SolverProblemError(e)

        combined_nodes = depth_first_search(PackageNode(self._package, packages))
        results = dict(aggregate_package_nodes(nodes) for nodes in combined_nodes)

        # Merging feature packages with base packages
        final_packages = []
        depths = []
        for package in packages:
            if package.features:
                for _package in packages:
                    if (
                        not _package.features
                        and _package.name == package.name
                        and _package.version == package.version
                    ):
                        for dep in package.requires:
                            # Prevent adding base package as a dependency to itself
                            if _package.name == dep.name:
                                continue

                            try:
                                index = _package.requires.index(dep)
                            except ValueError:
                                _package.add_dependency(dep)
                            else:
                                _dep = _package.requires[index]
                                if _dep.marker != dep.marker:
                                    # marker of feature package is more accurate
                                    # because it includes relevant extras
                                    _dep.marker = dep.marker
            else:
                final_packages.append(package)
                depths.append(results[package])

        # Return the packages in their original order with associated depths
        return final_packages, depths


DFSNodeID = Tuple[str, FrozenSet[str], bool]

T = TypeVar("T", bound="DFSNode")


class DFSNode:
    def __init__(self, id: DFSNodeID, name: str, base_name: str) -> None:
        self.id = id
        self.name = name
        self.base_name = base_name

    def reachable(self: T) -> list[T]:
        return []

    def visit(self, parents: list[PackageNode]) -> None:
        pass

    def __str__(self) -> str:
        return str(self.id)


def depth_first_search(source: PackageNode) -> list[list[PackageNode]]:
    back_edges: dict[DFSNodeID, list[PackageNode]] = defaultdict(list)
    visited: set[DFSNodeID] = set()
    topo_sorted_nodes: list[PackageNode] = []

    dfs_visit(source, back_edges, visited, topo_sorted_nodes)

    # Combine the nodes by name
    combined_nodes: dict[str, list[PackageNode]] = defaultdict(list)
    for node in topo_sorted_nodes:
        node.visit(back_edges[node.id])
        combined_nodes[node.name].append(node)

    combined_topo_sorted_nodes: list[list[PackageNode]] = [
        combined_nodes.pop(node.name)
        for node in topo_sorted_nodes
        if node.name in combined_nodes
    ]

    return combined_topo_sorted_nodes


def dfs_visit(
    node: PackageNode,
    back_edges: dict[DFSNodeID, list[PackageNode]],
    visited: set[DFSNodeID],
    sorted_nodes: list[PackageNode],
) -> None:
    if node.id in visited:
        return
    visited.add(node.id)

    for neighbor in node.reachable():
        back_edges[neighbor.id].append(node)
        dfs_visit(neighbor, back_edges, visited, sorted_nodes)
    sorted_nodes.insert(0, node)


class PackageNode(DFSNode):
    def __init__(
        self,
        package: Package,
        packages: list[Package],
        previous: PackageNode | None = None,
        dep: Dependency | None = None,
    ) -> None:
        self.package = package
        self.packages = packages

        self.dep = dep
        self.depth = -1

        if not previous:
            self.groups: frozenset[str] = frozenset()
            self.optional = True
        elif dep:
            self.groups = dep.groups
            self.optional = dep.is_optional()
        else:
            raise ValueError("Both previous and dep must be passed")

        super().__init__(
            (package.complete_name, self.groups, self.optional),
            package.complete_name,
            package.name,
        )

    def reachable(self) -> list[PackageNode]:
        children: list[PackageNode] = []

        for dependency in self.package.all_requires:
            for pkg in self.packages:
                if pkg.complete_name == dependency.complete_name and (
                    dependency.constraint.allows(pkg.version)
                ):
                    children.append(
                        PackageNode(
                            pkg,
                            self.packages,
                            self,
                            self.dep or dependency,
                        )
                    )

        return children

    def visit(self, parents: list[PackageNode]) -> None:
        # The root package, which has no parents, is defined as having depth -1
        # So that the root package's top-level dependencies have depth 0.
        self.depth = 1 + max(
            [
                parent.depth if parent.base_name != self.base_name else parent.depth - 1
                for parent in parents
            ]
            + [-2]
        )


def aggregate_package_nodes(nodes: list[PackageNode]) -> tuple[Package, int]:
    package = nodes[0].package
    depth = max(node.depth for node in nodes)
    groups: list[str] = []
    for node in nodes:
        groups.extend(node.groups)

    optional = all(node.optional for node in nodes)
    for node in nodes:
        node.depth = depth
        node.optional = optional

    package.optional = optional

    return package, depth
