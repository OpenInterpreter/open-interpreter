from __future__ import annotations

from poetry.core.constraints.generic.base_constraint import BaseConstraint


class EmptyConstraint(BaseConstraint):
    pretty_string = None

    def is_empty(self) -> bool:
        return True

    def allows(self, other: BaseConstraint) -> bool:
        return False

    def allows_all(self, other: BaseConstraint) -> bool:
        return other.is_empty()

    def allows_any(self, other: BaseConstraint) -> bool:
        return False

    def invert(self) -> BaseConstraint:
        from poetry.core.constraints.generic.any_constraint import AnyConstraint

        return AnyConstraint()

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        return self

    def union(self, other: BaseConstraint) -> BaseConstraint:
        return other

    def difference(self, other: BaseConstraint) -> BaseConstraint:
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseConstraint):
            return False

        return other.is_empty()

    def __hash__(self) -> int:
        return hash("empty")

    def __str__(self) -> str:
        return ""
