from __future__ import annotations

import itertools

from poetry.core.constraints.generic import AnyConstraint
from poetry.core.constraints.generic.base_constraint import BaseConstraint
from poetry.core.constraints.generic.constraint import Constraint
from poetry.core.constraints.generic.empty_constraint import EmptyConstraint
from poetry.core.constraints.generic.multi_constraint import MultiConstraint


class UnionConstraint(BaseConstraint):
    def __init__(self, *constraints: BaseConstraint) -> None:
        self._constraints = constraints

    @property
    def constraints(self) -> tuple[BaseConstraint, ...]:
        return self._constraints

    def allows(
        self,
        other: BaseConstraint,
    ) -> bool:
        return any(constraint.allows(other) for constraint in self._constraints)

    def allows_any(self, other: BaseConstraint) -> bool:
        if other.is_empty():
            return False

        if other.is_any():
            return True

        if isinstance(other, (UnionConstraint, MultiConstraint)):
            constraints = other.constraints
        else:
            constraints = (other,)

        return any(
            our_constraint.allows_any(their_constraint)
            for our_constraint in self._constraints
            for their_constraint in constraints
        )

    def allows_all(self, other: BaseConstraint) -> bool:
        if other.is_any():
            return False

        if other.is_empty():
            return True

        if isinstance(other, (UnionConstraint, MultiConstraint)):
            constraints = other.constraints
        else:
            constraints = (other,)

        our_constraints = iter(self._constraints)
        their_constraints = iter(constraints)
        our_constraint = next(our_constraints, None)
        their_constraint = next(their_constraints, None)

        while our_constraint and their_constraint:
            if our_constraint.allows_all(their_constraint):
                their_constraint = next(their_constraints, None)
            else:
                our_constraint = next(our_constraints, None)

        return their_constraint is None

    def invert(self) -> MultiConstraint:
        inverted_constraints = [c.invert() for c in self._constraints]
        if any(not isinstance(c, Constraint) for c in inverted_constraints):
            raise NotImplementedError(
                "Inversion of complex union constraints not implemented"
            )
        return MultiConstraint(*inverted_constraints)  # type: ignore[arg-type]

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        if other.is_any():
            return self

        if other.is_empty():
            return other

        if isinstance(other, Constraint):
            # (A or B) and C => (A and C) or (B and C)
            # just a special case of UnionConstraint
            other = UnionConstraint(other)

        new_constraints = []
        if isinstance(other, UnionConstraint):
            # (A or B) and (C or D) => (A and C) or (A and D) or (B and C) or (B and D)
            for our_constraint in self._constraints:
                for their_constraint in other.constraints:
                    intersection = our_constraint.intersect(their_constraint)

                    if not (intersection.is_empty() or intersection in new_constraints):
                        new_constraints.append(intersection)

        else:
            assert isinstance(other, MultiConstraint)
            # (A or B) and (C and D) => (A and C and D) or (B and C and D)

            for our_constraint in self._constraints:
                intersection = our_constraint
                for their_constraint in other.constraints:
                    intersection = intersection.intersect(their_constraint)

                if not (intersection.is_empty() or intersection in new_constraints):
                    new_constraints.append(intersection)

        if not new_constraints:
            return EmptyConstraint()

        if len(new_constraints) == 1:
            return new_constraints[0]

        return UnionConstraint(*new_constraints)

    def union(self, other: BaseConstraint) -> BaseConstraint:
        if other.is_any():
            return other

        if other.is_empty():
            return self

        if isinstance(other, Constraint):
            # (A or B) or C => A or B or C
            # just a special case of UnionConstraint
            other = UnionConstraint(other)

        new_constraints: list[BaseConstraint] = []
        if isinstance(other, UnionConstraint):
            # (A or B) or (C or D) => A or B or C or D
            our_new_constraints: list[BaseConstraint] = []
            their_new_constraints: list[BaseConstraint] = []
            merged_new_constraints: list[BaseConstraint] = []
            for our_constraint in self._constraints:
                for their_constraint in other.constraints:
                    union = our_constraint.union(their_constraint)
                    if union.is_any():
                        return AnyConstraint()
                    if isinstance(union, Constraint):
                        if union not in merged_new_constraints:
                            merged_new_constraints.append(union)
                    else:
                        if our_constraint not in our_new_constraints:
                            our_new_constraints.append(our_constraint)
                        if their_constraint not in their_new_constraints:
                            their_new_constraints.append(their_constraint)
            new_constraints = our_new_constraints
            for constraint in itertools.chain(
                their_new_constraints, merged_new_constraints
            ):
                if constraint not in new_constraints:
                    new_constraints.append(constraint)

        else:
            assert isinstance(other, MultiConstraint)
            # (A or B) or (C and D) => nothing to do

            new_constraints = [*self._constraints, other]

        if len(new_constraints) == 1:
            return new_constraints[0]

        return UnionConstraint(*new_constraints)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnionConstraint):
            return False

        return set(self._constraints) == set(other._constraints)

    def __hash__(self) -> int:
        h = hash("union")
        for constraint in self._constraints:
            h ^= hash(constraint)

        return h

    def __str__(self) -> str:
        constraints = [str(constraint) for constraint in self._constraints]
        return " || ".join(constraints)
