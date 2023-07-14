from __future__ import annotations

from typing import TYPE_CHECKING

from poetry.core.constraints.generic import AnyConstraint
from poetry.core.constraints.generic import EmptyConstraint
from poetry.core.constraints.generic.base_constraint import BaseConstraint
from poetry.core.constraints.generic.constraint import Constraint


if TYPE_CHECKING:
    from poetry.core.constraints.generic import UnionConstraint


class MultiConstraint(BaseConstraint):
    def __init__(self, *constraints: Constraint) -> None:
        if any(c.operator == "==" for c in constraints):
            raise ValueError(
                "A multi-constraint can only be comprised of negative constraints"
            )

        self._constraints = constraints

    @property
    def constraints(self) -> tuple[Constraint, ...]:
        return self._constraints

    def allows(self, other: BaseConstraint) -> bool:
        return all(constraint.allows(other) for constraint in self._constraints)

    def allows_all(self, other: BaseConstraint) -> bool:
        if other.is_any():
            return False

        if other.is_empty():
            return True

        if not isinstance(other, MultiConstraint):
            return self.allows(other)

        our_constraints = iter(self._constraints)
        their_constraints = iter(other.constraints)
        our_constraint = next(our_constraints, None)
        their_constraint = next(their_constraints, None)

        while our_constraint and their_constraint:
            if our_constraint.allows_all(their_constraint):
                their_constraint = next(their_constraints, None)
            else:
                our_constraint = next(our_constraints, None)

        return their_constraint is None

    def allows_any(self, other: BaseConstraint) -> bool:
        if other.is_any():
            return True

        if other.is_empty():
            return True

        if isinstance(other, Constraint):
            return self.allows(other)

        if isinstance(other, MultiConstraint):
            return any(
                c1.allows(c2) for c1 in self.constraints for c2 in other.constraints
            )

        return False

    def invert(self) -> UnionConstraint:
        from poetry.core.constraints.generic import UnionConstraint

        return UnionConstraint(*(c.invert() for c in self._constraints))

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        if isinstance(other, MultiConstraint):
            ours = set(self.constraints)
            union = list(self.constraints) + [
                c for c in other.constraints if c not in ours
            ]
            return MultiConstraint(*union)

        if not isinstance(other, Constraint):
            return other.intersect(self)

        if other in self._constraints:
            return self

        if other.value in (c.value for c in self._constraints):
            # same value but different operator, e.g. '== "linux"' and '!= "linux"'
            return EmptyConstraint()

        if other.operator == "==":
            return other

        return MultiConstraint(*self._constraints, other)

    def union(self, other: BaseConstraint) -> BaseConstraint:
        if isinstance(other, MultiConstraint):
            theirs = set(other.constraints)
            common = [c for c in self.constraints if c in theirs]
            return MultiConstraint(*common)

        if not isinstance(other, Constraint):
            return other.union(self)

        if other in self._constraints:
            return other

        if other.value not in (c.value for c in self._constraints):
            if other.operator == "!=":
                return AnyConstraint()

            return self

        constraints = [c for c in self._constraints if c.value != other.value]

        if len(constraints) == 1:
            return constraints[0]

        return MultiConstraint(*constraints)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MultiConstraint):
            return False

        return set(self._constraints) == set(other._constraints)

    def __hash__(self) -> int:
        h = hash("multi")
        for constraint in self._constraints:
            h ^= hash(constraint)

        return h

    def __str__(self) -> str:
        constraints = [str(constraint) for constraint in self._constraints]
        return ", ".join(constraints)
