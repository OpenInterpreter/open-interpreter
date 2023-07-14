from __future__ import annotations

from poetry.core.constraints.generic.base_constraint import BaseConstraint
from poetry.core.constraints.generic.empty_constraint import EmptyConstraint


class AnyConstraint(BaseConstraint):
    def allows(self, other: BaseConstraint) -> bool:
        return True

    def allows_all(self, other: BaseConstraint) -> bool:
        return True

    def allows_any(self, other: BaseConstraint) -> bool:
        return True

    def invert(self) -> BaseConstraint:
        return EmptyConstraint()

    def difference(self, other: BaseConstraint) -> BaseConstraint:
        if other.is_any():
            return EmptyConstraint()

        raise ValueError("Unimplemented constraint difference")

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        return other

    def union(self, other: BaseConstraint) -> AnyConstraint:
        return AnyConstraint()

    def is_any(self) -> bool:
        return True

    def is_empty(self) -> bool:
        return False

    def __str__(self) -> str:
        return "*"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BaseConstraint) and other.is_any()

    def __hash__(self) -> int:
        return hash("any")
