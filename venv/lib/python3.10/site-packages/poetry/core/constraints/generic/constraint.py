from __future__ import annotations

import operator
import warnings

from poetry.core.constraints.generic.any_constraint import AnyConstraint
from poetry.core.constraints.generic.base_constraint import BaseConstraint
from poetry.core.constraints.generic.empty_constraint import EmptyConstraint


class Constraint(BaseConstraint):
    OP_EQ = operator.eq
    OP_NE = operator.ne

    _trans_op_str = {"=": OP_EQ, "==": OP_EQ, "!=": OP_NE}

    _trans_op_int = {OP_EQ: "==", OP_NE: "!="}

    def __init__(self, value: str, operator: str = "==") -> None:
        if operator == "=":
            operator = "=="

        self._value = value
        self._operator = operator
        self._op = self._trans_op_str[operator]

    @property
    def value(self) -> str:
        return self._value

    @property
    def version(self) -> str:
        warnings.warn(
            (
                "The property 'version' is deprecated and will be removed. "
                "Please use the property 'value' instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return self.value

    @property
    def operator(self) -> str:
        return self._operator

    def allows(self, other: BaseConstraint) -> bool:
        if not isinstance(other, Constraint):
            raise ValueError("Unimplemented comparison of constraints")

        is_equal_op = self._operator == "=="
        is_non_equal_op = self._operator == "!="
        is_other_equal_op = other.operator == "=="
        is_other_non_equal_op = other.operator == "!="

        if is_equal_op and is_other_equal_op:
            return self._value == other.value

        if (
            is_equal_op
            and is_other_non_equal_op
            or is_non_equal_op
            and is_other_equal_op
            or is_non_equal_op
            and is_other_non_equal_op
        ):
            return self._value != other.value

        return False

    def allows_all(self, other: BaseConstraint) -> bool:
        if not isinstance(other, Constraint):
            return other.is_empty()

        return other == self

    def allows_any(self, other: BaseConstraint) -> bool:
        if isinstance(other, Constraint):
            is_non_equal_op = self._operator == "!="
            is_other_non_equal_op = other.operator == "!="

            if is_non_equal_op and is_other_non_equal_op:
                return self._value != other.value

        return other.allows(self)

    def invert(self) -> Constraint:
        return Constraint(self._value, "!=" if self._operator == "==" else "==")

    def difference(self, other: BaseConstraint) -> Constraint | EmptyConstraint:
        if other.allows(self):
            return EmptyConstraint()

        return self

    def intersect(self, other: BaseConstraint) -> BaseConstraint:
        from poetry.core.constraints.generic.multi_constraint import MultiConstraint

        if isinstance(other, Constraint):
            if other == self:
                return self

            if self.operator == "!=" and other.operator == "==" and self.allows(other):
                return other

            if other.operator == "!=" and self.operator == "==" and other.allows(self):
                return self

            if other.operator == "!=" and self.operator == "!=":
                return MultiConstraint(self, other)

            return EmptyConstraint()

        return other.intersect(self)

    def union(self, other: BaseConstraint) -> BaseConstraint:
        if isinstance(other, Constraint):
            from poetry.core.constraints.generic.union_constraint import UnionConstraint

            if other == self:
                return self

            if self.operator == "!=" and other.operator == "==" and self.allows(other):
                return self

            if other.operator == "!=" and self.operator == "==" and other.allows(self):
                return other

            if other.operator == "==" and self.operator == "==":
                return UnionConstraint(self, other)

            return AnyConstraint()

        return other.union(self)

    def is_any(self) -> bool:
        return False

    def is_empty(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Constraint):
            return NotImplemented

        return (self.value, self.operator) == (other.value, other.operator)

    def __hash__(self) -> int:
        return hash((self._operator, self._value))

    def __str__(self) -> str:
        op = self._operator if self._operator != "==" else ""
        return f"{op}{self._value}"
