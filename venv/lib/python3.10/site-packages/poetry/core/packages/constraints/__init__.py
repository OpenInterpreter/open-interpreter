from __future__ import annotations

import warnings

from poetry.core.constraints.generic import AnyConstraint
from poetry.core.constraints.generic import BaseConstraint
from poetry.core.constraints.generic import Constraint
from poetry.core.constraints.generic import EmptyConstraint
from poetry.core.constraints.generic import MultiConstraint
from poetry.core.constraints.generic import UnionConstraint
from poetry.core.constraints.generic import parse_constraint
from poetry.core.constraints.generic.parser import parse_single_constraint


warnings.warn(
    (
        "poetry.core.packages.constraints is deprecated."
        " Use poetry.core.constraints.generic instead."
    ),
    DeprecationWarning,
    stacklevel=2,
)


__all__ = (
    "AnyConstraint",
    "BaseConstraint",
    "Constraint",
    "EmptyConstraint",
    "MultiConstraint",
    "UnionConstraint",
    "parse_constraint",
    "parse_single_constraint",
)
