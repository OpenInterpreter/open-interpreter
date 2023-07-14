from __future__ import annotations


class BaseConstraint:
    def allows(self, other: BaseConstraint) -> bool:
        raise NotImplementedError

    def allows_all(self, other: BaseConstraint) -> bool:
        raise NotImplementedError

    def allows_any(self, other: BaseConstraint) -> bool:
        raise NotImplementedError

    def invert(self) -> BaseConstraint:
        raise NotImplementedError()

    def difference(self, other: BaseConstraint) -> BaseConstraint:
        raise NotImplementedError

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        raise NotImplementedError

    def union(self, other: BaseConstraint) -> BaseConstraint:
        raise NotImplementedError

    def is_any(self) -> bool:
        return False

    def is_empty(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"

    def __str__(self) -> str:
        raise NotImplementedError

    def __hash__(self) -> int:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError
