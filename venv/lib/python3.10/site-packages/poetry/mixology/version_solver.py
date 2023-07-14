from __future__ import annotations

import collections
import functools
import time

from typing import TYPE_CHECKING
from typing import Optional
from typing import Tuple

from poetry.core.packages.dependency import Dependency

from poetry.mixology.failure import SolveFailure
from poetry.mixology.incompatibility import Incompatibility
from poetry.mixology.incompatibility_cause import ConflictCause
from poetry.mixology.incompatibility_cause import NoVersionsCause
from poetry.mixology.incompatibility_cause import RootCause
from poetry.mixology.partial_solution import PartialSolution
from poetry.mixology.result import SolverResult
from poetry.mixology.set_relation import SetRelation
from poetry.mixology.term import Term


if TYPE_CHECKING:
    from poetry.core.packages.project_package import ProjectPackage

    from poetry.packages import DependencyPackage
    from poetry.puzzle.provider import Provider


_conflict = object()


DependencyCacheKey = Tuple[
    str, Optional[str], Optional[str], Optional[str], Optional[str]
]


class DependencyCache:
    """
    A cache of the valid dependencies.

    The key observation here is that during the search - except at backtracking
    - once we have decided that a dependency is invalid, we never need check it
    again.
    """

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

        # self._cache maps a package name to a stack of cached package lists,
        # ordered by the decision level which added them to the cache. This is
        # done so that when backtracking we can maintain cache entries from
        # previous decision levels, while clearing cache entries from only the
        # rolled back levels.
        #
        # In order to maintain the integrity of the cache, `clear_level()`
        # needs to be called in descending order as decision levels are
        # backtracked so that the correct items can be popped from the stack.
        self._cache: dict[DependencyCacheKey, list[list[DependencyPackage]]] = (
            collections.defaultdict(list)
        )
        self._cached_dependencies_by_level: dict[int, list[DependencyCacheKey]] = (
            collections.defaultdict(list)
        )

        self._search_for_cached = functools.lru_cache(maxsize=128)(self._search_for)

    def _search_for(
        self,
        dependency: Dependency,
        key: DependencyCacheKey,
    ) -> list[DependencyPackage]:
        cache_entries = self._cache[key]
        if cache_entries:
            packages = [
                p
                for p in cache_entries[-1]
                if dependency.constraint.allows(p.package.version)
            ]
        else:
            packages = None

        # provider.search_for() normally does not include pre-release packages
        # (unless requested), but will include them if there are no other
        # eligible package versions for a version constraint.
        #
        # Therefore, if the eligible versions have been filtered down to
        # nothing, we need to call provider.search_for() again as it may return
        # additional results this time.
        if not packages:
            packages = self._provider.search_for(dependency)

        return packages

    def search_for(
        self,
        dependency: Dependency,
        decision_level: int,
    ) -> list[DependencyPackage]:
        key = (
            dependency.complete_name,
            dependency.source_type,
            dependency.source_url,
            dependency.source_reference,
            dependency.source_subdirectory,
        )

        packages = self._search_for_cached(dependency, key)
        if not self._cache[key] or self._cache[key][-1] is not packages:
            self._cache[key].append(packages)
            self._cached_dependencies_by_level[decision_level].append(key)

        return packages

    def clear_level(self, level: int) -> None:
        if level in self._cached_dependencies_by_level:
            self._search_for_cached.cache_clear()
            for key in self._cached_dependencies_by_level.pop(level):
                self._cache[key].pop()


class VersionSolver:
    """
    The version solver that finds a set of package versions that satisfy the
    root package's dependencies.

    See https://github.com/dart-lang/pub/tree/master/doc/solver.md for details
    on how this solver works.
    """

    def __init__(self, root: ProjectPackage, provider: Provider) -> None:
        self._root = root
        self._provider = provider
        self._dependency_cache = DependencyCache(provider)
        self._incompatibilities: dict[str, list[Incompatibility]] = {}
        self._contradicted_incompatibilities: set[Incompatibility] = set()
        self._contradicted_incompatibilities_by_level: dict[
            int, set[Incompatibility]
        ] = collections.defaultdict(set)
        self._solution = PartialSolution()

    @property
    def solution(self) -> PartialSolution:
        return self._solution

    def solve(self) -> SolverResult:
        """
        Finds a set of dependencies that match the root package's constraints,
        or raises an error if no such set is available.
        """
        start = time.time()
        root_dependency = Dependency(self._root.name, self._root.version)
        root_dependency.is_root = True

        self._add_incompatibility(
            Incompatibility([Term(root_dependency, False)], RootCause())
        )

        try:
            next: str | None = self._root.name
            while next is not None:
                self._propagate(next)
                next = self._choose_package_version()

            return self._result()
        except Exception:
            raise
        finally:
            self._log(
                f"Version solving took {time.time() - start:.3f} seconds.\n"
                f"Tried {self._solution.attempted_solutions} solutions."
            )

    def _propagate(self, package: str) -> None:
        """
        Performs unit propagation on incompatibilities transitively
        related to package to derive new assignments for _solution.
        """
        changed = {package}
        while changed:
            package = changed.pop()

            # Iterate in reverse because conflict resolution tends to produce more
            # general incompatibilities as time goes on. If we look at those first,
            # we can derive stronger assignments sooner and more eagerly find
            # conflicts.
            for incompatibility in reversed(self._incompatibilities[package]):
                if incompatibility in self._contradicted_incompatibilities:
                    continue

                result = self._propagate_incompatibility(incompatibility)

                if result is _conflict:
                    # If the incompatibility is satisfied by the solution, we use
                    # _resolve_conflict() to determine the root cause of the conflict as
                    # a new incompatibility.
                    #
                    # It also backjumps to a point in the solution
                    # where that incompatibility will allow us to derive new assignments
                    # that avoid the conflict.
                    root_cause = self._resolve_conflict(incompatibility)

                    # Back jumping erases all the assignments we did at the previous
                    # decision level, so we clear [changed] and refill it with the
                    # newly-propagated assignment.
                    changed.clear()
                    changed.add(str(self._propagate_incompatibility(root_cause)))
                    break
                elif result is not None:
                    changed.add(str(result))

    def _propagate_incompatibility(
        self, incompatibility: Incompatibility
    ) -> str | object | None:
        """
        If incompatibility is almost satisfied by _solution, adds the
        negation of the unsatisfied term to _solution.

        If incompatibility is satisfied by _solution, returns _conflict. If
        incompatibility is almost satisfied by _solution, returns the
        unsatisfied term's package name.

        Otherwise, returns None.
        """
        # The first entry in incompatibility.terms that's not yet satisfied by
        # _solution, if one exists. If we find more than one, _solution is
        # inconclusive for incompatibility and we can't deduce anything.
        unsatisfied = None

        for term in incompatibility.terms:
            relation = self._solution.relation(term)

            if relation == SetRelation.DISJOINT:
                # If term is already contradicted by _solution, then
                # incompatibility is contradicted as well and there's nothing new we
                # can deduce from it.
                self._contradicted_incompatibilities.add(incompatibility)
                self._contradicted_incompatibilities_by_level[
                    self._solution.decision_level
                ].add(incompatibility)
                return None
            elif relation == SetRelation.OVERLAPPING:
                # If more than one term is inconclusive, we can't deduce anything about
                # incompatibility.
                if unsatisfied is not None:
                    return None

                # If exactly one term in incompatibility is inconclusive, then it's
                # almost satisfied and [term] is the unsatisfied term. We can add the
                # inverse of the term to _solution.
                unsatisfied = term

        # If *all* terms in incompatibility are satisfied by _solution, then
        # incompatibility is satisfied and we have a conflict.
        if unsatisfied is None:
            return _conflict

        self._contradicted_incompatibilities.add(incompatibility)
        self._contradicted_incompatibilities_by_level[
            self._solution.decision_level
        ].add(incompatibility)

        adverb = "not " if unsatisfied.is_positive() else ""
        self._log(f"derived: {adverb}{unsatisfied.dependency}")

        self._solution.derive(
            unsatisfied.dependency, not unsatisfied.is_positive(), incompatibility
        )

        complete_name: str = unsatisfied.dependency.complete_name
        return complete_name

    def _resolve_conflict(self, incompatibility: Incompatibility) -> Incompatibility:
        """
        Given an incompatibility that's satisfied by _solution,
        The `conflict resolution`_ constructs a new incompatibility that encapsulates
        the root cause of the conflict and backtracks _solution until the new
        incompatibility will allow _propagate() to deduce new assignments.

        Adds the new incompatibility to _incompatibilities and returns it.

        .. _conflict resolution:
        https://github.com/dart-lang/pub/tree/master/doc/solver.md#conflict-resolution
        """
        self._log(f"conflict: {incompatibility}")

        new_incompatibility = False
        while not incompatibility.is_failure():
            # The term in incompatibility.terms that was most recently satisfied by
            # _solution.
            most_recent_term = None

            # The earliest assignment in _solution such that incompatibility is
            # satisfied by _solution up to and including this assignment.
            most_recent_satisfier = None

            # The difference between most_recent_satisfier and most_recent_term;
            # that is, the versions that are allowed by most_recent_satisfier and not
            # by most_recent_term. This is None if most_recent_satisfier totally
            # satisfies most_recent_term.
            difference = None

            # The decision level of the earliest assignment in _solution *before*
            # most_recent_satisfier such that incompatibility is satisfied by
            # _solution up to and including this assignment plus
            # most_recent_satisfier.
            #
            # Decision level 1 is the level where the root package was selected. It's
            # safe to go back to decision level 0, but stopping at 1 tends to produce
            # better error messages, because references to the root package end up
            # closer to the final conclusion that no solution exists.
            previous_satisfier_level = 1

            for term in incompatibility.terms:
                satisfier = self._solution.satisfier(term)

                if most_recent_satisfier is None:
                    most_recent_term = term
                    most_recent_satisfier = satisfier
                elif most_recent_satisfier.index < satisfier.index:
                    previous_satisfier_level = max(
                        previous_satisfier_level, most_recent_satisfier.decision_level
                    )
                    most_recent_term = term
                    most_recent_satisfier = satisfier
                    difference = None
                else:
                    previous_satisfier_level = max(
                        previous_satisfier_level, satisfier.decision_level
                    )

                if most_recent_term == term:
                    # If most_recent_satisfier doesn't satisfy most_recent_term on its
                    # own, then the next-most-recent satisfier may be the one that
                    # satisfies the remainder.
                    difference = most_recent_satisfier.difference(most_recent_term)
                    if difference is not None:
                        previous_satisfier_level = max(
                            previous_satisfier_level,
                            self._solution.satisfier(difference.inverse).decision_level,
                        )

            # If most_recent_identifier is the only satisfier left at its decision
            # level, or if it has no cause (indicating that it's a decision rather
            # than a derivation), then incompatibility is the root cause. We then
            # backjump to previous_satisfier_level, where incompatibility is
            # guaranteed to allow _propagate to produce more assignments.

            # using assert to suppress mypy [union-attr]
            assert most_recent_satisfier is not None
            if (
                previous_satisfier_level < most_recent_satisfier.decision_level
                or most_recent_satisfier.cause is None
            ):
                for level in range(
                    self._solution.decision_level, previous_satisfier_level, -1
                ):
                    if level in self._contradicted_incompatibilities_by_level:
                        self._contradicted_incompatibilities.difference_update(
                            self._contradicted_incompatibilities_by_level.pop(level),
                        )
                    self._dependency_cache.clear_level(level)

                self._solution.backtrack(previous_satisfier_level)
                if new_incompatibility:
                    self._add_incompatibility(incompatibility)

                return incompatibility

            # Create a new incompatibility by combining incompatibility with the
            # incompatibility that caused most_recent_satisfier to be assigned. Doing
            # this iteratively constructs an incompatibility that's guaranteed to be
            # true (that is, we know for sure no solution will satisfy the
            # incompatibility) while also approximating the intuitive notion of the
            # "root cause" of the conflict.
            new_terms = [
                term for term in incompatibility.terms if term != most_recent_term
            ]

            for term in most_recent_satisfier.cause.terms:
                if term.dependency != most_recent_satisfier.dependency:
                    new_terms.append(term)

            # The most_recent_satisfier may not satisfy most_recent_term on its own
            # if there are a collection of constraints on most_recent_term that
            # only satisfy it together. For example, if most_recent_term is
            # `foo ^1.0.0` and _solution contains `[foo >=1.0.0,
            # foo <2.0.0]`, then most_recent_satisfier will be `foo <2.0.0` even
            # though it doesn't totally satisfy `foo ^1.0.0`.
            #
            # In this case, we add `not (most_recent_satisfier \ most_recent_term)` to
            # the incompatibility as well, See the `algorithm documentation`_ for
            # details.
            #
            # .. _algorithm documentation:
            # https://github.com/dart-lang/pub/tree/master/doc/solver.md#conflict-resolution  # noqa: E501
            if difference is not None:
                inverse = difference.inverse
                if inverse.dependency != most_recent_satisfier.dependency:
                    new_terms.append(inverse)

            incompatibility = Incompatibility(
                new_terms, ConflictCause(incompatibility, most_recent_satisfier.cause)
            )
            new_incompatibility = True

            partially = "" if difference is None else " partially"
            self._log(
                f"! {most_recent_term} is{partially} satisfied by"
                f" {most_recent_satisfier}"
            )
            self._log(f'! which is caused by "{most_recent_satisfier.cause}"')
            self._log(f"! thus: {incompatibility}")

        raise SolveFailure(incompatibility)

    def _choose_package_version(self) -> str | None:
        """
        Tries to select a version of a required package.

        Returns the name of the package whose incompatibilities should be
        propagated by _propagate(), or None indicating that version solving is
        complete and a solution has been found.
        """
        unsatisfied = self._solution.unsatisfied
        if not unsatisfied:
            return None

        class Preference:
            """
            Preference is one of the criteria for choosing which dependency to solve
            first. A higher value means that there are "more options" to satisfy
            a dependency. A lower value takes precedence.
            """

            DIRECT_ORIGIN = 0
            NO_CHOICE = 1
            USE_LATEST = 2
            LOCKED = 3
            DEFAULT = 4

        # Prefer packages with as few remaining versions as possible,
        # so that if a conflict is necessary it's forced quickly.
        # In order to provide results that are as deterministic as possible
        # and consistent between `poetry lock` and `poetry update`, the return value
        # of two different dependencies should not be equal if possible.
        def _get_min(dependency: Dependency) -> tuple[bool, int, int]:
            # Direct origin dependencies must be handled first: we don't want to resolve
            # a regular dependency for some package only to find later that we had a
            # direct-origin dependency.
            if dependency.is_direct_origin():
                return False, Preference.DIRECT_ORIGIN, 1

            is_specific_marker = not dependency.marker.is_any()

            use_latest = dependency.name in self._provider.use_latest
            if not use_latest:
                locked = self._provider.get_locked(dependency)
                if locked:
                    return is_specific_marker, Preference.LOCKED, 1

            num_packages = len(
                self._dependency_cache.search_for(
                    dependency, self._solution.decision_level
                )
            )

            if num_packages < 2:
                preference = Preference.NO_CHOICE
            elif use_latest:
                preference = Preference.USE_LATEST
            else:
                preference = Preference.DEFAULT
            return is_specific_marker, preference, num_packages

        if len(unsatisfied) == 1:
            dependency = unsatisfied[0]
        else:
            dependency = min(*unsatisfied, key=_get_min)

        locked = self._provider.get_locked(dependency)
        if locked is None:
            packages = self._dependency_cache.search_for(
                dependency, self._solution.decision_level
            )
            package = next(iter(packages), None)

            if package is None:
                # If there are no versions that satisfy the constraint,
                # add an incompatibility that indicates that.
                self._add_incompatibility(
                    Incompatibility([Term(dependency, True)], NoVersionsCause())
                )

                complete_name = dependency.complete_name
                return complete_name
        else:
            package = locked

        package = self._provider.complete_package(package)

        conflict = False
        for incompatibility in self._provider.incompatibilities_for(package):
            self._add_incompatibility(incompatibility)

            # If an incompatibility is already satisfied, then selecting version
            # would cause a conflict.
            #
            # We'll continue adding its dependencies, then go back to
            # unit propagation which will guide us to choose a better version.
            conflict = conflict or all(
                term.dependency.complete_name == dependency.complete_name
                or self._solution.satisfies(term)
                for term in incompatibility.terms
            )

        if not conflict:
            self._solution.decide(package.package)
            self._log(
                f"selecting {package.package.complete_name}"
                f" ({package.package.full_pretty_version})"
            )

        complete_name = dependency.complete_name
        return complete_name

    def _result(self) -> SolverResult:
        """
        Creates a #SolverResult from the decisions in _solution
        """
        decisions = self._solution.decisions

        return SolverResult(
            self._root,
            [p for p in decisions if not p.is_root()],
            self._solution.attempted_solutions,
        )

    def _add_incompatibility(self, incompatibility: Incompatibility) -> None:
        self._log(f"fact: {incompatibility}")

        for term in incompatibility.terms:
            if term.dependency.complete_name not in self._incompatibilities:
                self._incompatibilities[term.dependency.complete_name] = []

            if (
                incompatibility
                in self._incompatibilities[term.dependency.complete_name]
            ):
                continue

            self._incompatibilities[term.dependency.complete_name].append(
                incompatibility
            )

    def _log(self, text: str) -> None:
        self._provider.debug(text, self._solution.attempted_solutions)
