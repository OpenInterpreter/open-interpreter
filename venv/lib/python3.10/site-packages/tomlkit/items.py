from __future__ import annotations

import abc
import copy
import dataclasses
import re
import string

from datetime import date
from datetime import datetime
from datetime import time
from datetime import tzinfo
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import Collection
from typing import Iterable
from typing import Iterator
from typing import Sequence
from typing import TypeVar
from typing import cast
from typing import overload

from tomlkit._compat import PY38
from tomlkit._compat import decode
from tomlkit._utils import CONTROL_CHARS
from tomlkit._utils import escape_string
from tomlkit.exceptions import InvalidStringError


if TYPE_CHECKING:  # pragma: no cover
    # Define _CustomList and _CustomDict as a workaround for:
    # https://github.com/python/mypy/issues/11427
    #
    # According to this issue, the typeshed contains a "lie"
    # (it adds MutableSequence to the ancestry of list and MutableMapping to
    # the ancestry of dict) which completely messes with the type inference for
    # Table, InlineTable, Array and Container.
    #
    # Importing from builtins is preferred over simple assignment, see issues:
    # https://github.com/python/mypy/issues/8715
    # https://github.com/python/mypy/issues/10068
    from builtins import dict as _CustomDict  # noqa: N812, TC004
    from builtins import list as _CustomList  # noqa: N812, TC004

    # Allow type annotations but break circular imports
    from tomlkit import container
else:
    from collections.abc import MutableMapping
    from collections.abc import MutableSequence

    class _CustomList(MutableSequence, list):
        """Adds MutableSequence mixin while pretending to be a builtin list"""

    class _CustomDict(MutableMapping, dict):
        """Adds MutableMapping mixin while pretending to be a builtin dict"""


ItemT = TypeVar("ItemT", bound="Item")


@overload
def item(value: bool, _parent: Item | None = ..., _sort_keys: bool = ...) -> Bool:
    ...


@overload
def item(value: int, _parent: Item | None = ..., _sort_keys: bool = ...) -> Integer:
    ...


@overload
def item(value: float, _parent: Item | None = ..., _sort_keys: bool = ...) -> Float:
    ...


@overload
def item(value: str, _parent: Item | None = ..., _sort_keys: bool = ...) -> String:
    ...


@overload
def item(
    value: datetime, _parent: Item | None = ..., _sort_keys: bool = ...
) -> DateTime:
    ...


@overload
def item(value: date, _parent: Item | None = ..., _sort_keys: bool = ...) -> Date:
    ...


@overload
def item(value: time, _parent: Item | None = ..., _sort_keys: bool = ...) -> Time:
    ...


@overload
def item(
    value: Sequence[dict], _parent: Item | None = ..., _sort_keys: bool = ...
) -> AoT:
    ...


@overload
def item(value: Sequence, _parent: Item | None = ..., _sort_keys: bool = ...) -> Array:
    ...


@overload
def item(value: dict, _parent: Array = ..., _sort_keys: bool = ...) -> InlineTable:
    ...


@overload
def item(value: dict, _parent: Item | None = ..., _sort_keys: bool = ...) -> Table:
    ...


@overload
def item(value: ItemT, _parent: Item | None = ..., _sort_keys: bool = ...) -> ItemT:
    ...


def item(value: Any, _parent: Item | None = None, _sort_keys: bool = False) -> Item:
    """Create a TOML item from a Python object.

    :Example:

    >>> item(42)
    42
    >>> item([1, 2, 3])
    [1, 2, 3]
    >>> item({'a': 1, 'b': 2})
    a = 1
    b = 2
    """

    from tomlkit.container import Container

    if isinstance(value, Item):
        return value

    if isinstance(value, bool):
        return Bool(value, Trivia())
    elif isinstance(value, int):
        return Integer(value, Trivia(), str(value))
    elif isinstance(value, float):
        return Float(value, Trivia(), str(value))
    elif isinstance(value, dict):
        table_constructor = (
            InlineTable if isinstance(_parent, (Array, InlineTable)) else Table
        )
        val = table_constructor(Container(), Trivia(), False)
        for k, v in sorted(
            value.items(),
            key=lambda i: (isinstance(i[1], dict), i[0] if _sort_keys else 1),
        ):
            val[k] = item(v, _parent=val, _sort_keys=_sort_keys)

        return val
    elif isinstance(value, (list, tuple)):
        if (
            value
            and all(isinstance(v, dict) for v in value)
            and (_parent is None or isinstance(_parent, Table))
        ):
            a = AoT([])
            table_constructor = Table
        else:
            a = Array([], Trivia())
            table_constructor = InlineTable

        for v in value:
            if isinstance(v, dict):
                table = table_constructor(Container(), Trivia(), True)

                for k, _v in sorted(
                    v.items(),
                    key=lambda i: (isinstance(i[1], dict), i[0] if _sort_keys else 1),
                ):
                    i = item(_v, _parent=table, _sort_keys=_sort_keys)
                    if isinstance(table, InlineTable):
                        i.trivia.trail = ""

                    table[k] = i

                v = table

            a.append(v)

        return a
    elif isinstance(value, str):
        return String.from_raw(value)
    elif isinstance(value, datetime):
        return DateTime(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            value.tzinfo,
            Trivia(),
            value.isoformat().replace("+00:00", "Z"),
        )
    elif isinstance(value, date):
        return Date(value.year, value.month, value.day, Trivia(), value.isoformat())
    elif isinstance(value, time):
        return Time(
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            value.tzinfo,
            Trivia(),
            value.isoformat(),
        )

    raise ValueError(f"Invalid type {type(value)}")


class StringType(Enum):
    # Single Line Basic
    SLB = '"'
    # Multi Line Basic
    MLB = '"""'
    # Single Line Literal
    SLL = "'"
    # Multi Line Literal
    MLL = "'''"

    @classmethod
    def select(cls, literal=False, multiline=False) -> StringType:
        return {
            (False, False): cls.SLB,
            (False, True): cls.MLB,
            (True, False): cls.SLL,
            (True, True): cls.MLL,
        }[(literal, multiline)]

    @property
    def escaped_sequences(self) -> Collection[str]:
        # https://toml.io/en/v1.0.0#string
        escaped_in_basic = CONTROL_CHARS | {"\\"}
        allowed_in_multiline = {"\n", "\r"}
        return {
            StringType.SLB: escaped_in_basic | {'"'},
            StringType.MLB: (escaped_in_basic | {'"""'}) - allowed_in_multiline,
            StringType.SLL: (),
            StringType.MLL: (),
        }[self]

    @property
    def invalid_sequences(self) -> Collection[str]:
        # https://toml.io/en/v1.0.0#string
        forbidden_in_literal = CONTROL_CHARS - {"\t"}
        allowed_in_multiline = {"\n", "\r"}
        return {
            StringType.SLB: (),
            StringType.MLB: (),
            StringType.SLL: forbidden_in_literal | {"'"},
            StringType.MLL: (forbidden_in_literal | {"'''"}) - allowed_in_multiline,
        }[self]

    @property
    def unit(self) -> str:
        return self.value[0]

    def is_basic(self) -> bool:
        return self in {StringType.SLB, StringType.MLB}

    def is_literal(self) -> bool:
        return self in {StringType.SLL, StringType.MLL}

    def is_singleline(self) -> bool:
        return self in {StringType.SLB, StringType.SLL}

    def is_multiline(self) -> bool:
        return self in {StringType.MLB, StringType.MLL}

    def toggle(self) -> StringType:
        return {
            StringType.SLB: StringType.MLB,
            StringType.MLB: StringType.SLB,
            StringType.SLL: StringType.MLL,
            StringType.MLL: StringType.SLL,
        }[self]


class BoolType(Enum):
    TRUE = "true"
    FALSE = "false"

    def __bool__(self):
        return {BoolType.TRUE: True, BoolType.FALSE: False}[self]

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)


@dataclasses.dataclass
class Trivia:
    """
    Trivia information (aka metadata).
    """

    # Whitespace before a value.
    indent: str = ""
    # Whitespace after a value, but before a comment.
    comment_ws: str = ""
    # Comment, starting with # character, or empty string if no comment.
    comment: str = ""
    # Trailing newline.
    trail: str = "\n"

    def copy(self) -> Trivia:
        return dataclasses.replace(self)


class KeyType(Enum):
    """
    The type of a Key.

    Keys can be bare (unquoted), or quoted using basic ("), or literal (')
    quotes following the same escaping rules as single-line StringType.
    """

    Bare = ""
    Basic = '"'
    Literal = "'"


class Key(abc.ABC):
    """Base class for a key"""

    sep: str
    _original: str
    _keys: list[SingleKey]
    _dotted: bool
    key: str

    @abc.abstractmethod
    def __hash__(self) -> int:
        pass

    @abc.abstractmethod
    def __eq__(self, __o: object) -> bool:
        pass

    def is_dotted(self) -> bool:
        """If the key is followed by other keys"""
        return self._dotted

    def __iter__(self) -> Iterator[SingleKey]:
        return iter(self._keys)

    def concat(self, other: Key) -> DottedKey:
        """Concatenate keys into a dotted key"""
        keys = self._keys + other._keys
        return DottedKey(keys, sep=self.sep)

    def is_multi(self) -> bool:
        """Check if the key contains multiple keys"""
        return len(self._keys) > 1

    def as_string(self) -> str:
        """The TOML representation"""
        return self._original

    def __str__(self) -> str:
        return self.as_string()

    def __repr__(self) -> str:
        return f"<Key {self.as_string()}>"


class SingleKey(Key):
    """A single key"""

    def __init__(
        self,
        k: str,
        t: KeyType | None = None,
        sep: str | None = None,
        original: str | None = None,
    ) -> None:
        if t is None:
            if not k or any(
                c not in string.ascii_letters + string.digits + "-" + "_" for c in k
            ):
                t = KeyType.Basic
            else:
                t = KeyType.Bare

        self.t = t
        if sep is None:
            sep = " = "

        self.sep = sep
        self.key = k
        if original is None:
            key_str = escape_string(k) if t == KeyType.Basic else k
            original = f"{t.value}{key_str}{t.value}"

        self._original = original
        self._keys = [self]
        self._dotted = False

    @property
    def delimiter(self) -> str:
        """The delimiter: double quote/single quote/none"""
        return self.t.value

    def is_bare(self) -> bool:
        """Check if the key is bare"""
        return self.t == KeyType.Bare

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Key):
            return isinstance(other, SingleKey) and self.key == other.key

        return self.key == other


class DottedKey(Key):
    def __init__(
        self,
        keys: Iterable[Key],
        sep: str | None = None,
        original: str | None = None,
    ) -> None:
        self._keys = list(keys)
        if original is None:
            original = ".".join(k.as_string() for k in self._keys)

        self.sep = " = " if sep is None else sep
        self._original = original
        self._dotted = False
        self.key = ".".join(k.key for k in self._keys)

    def __hash__(self) -> int:
        return hash(tuple(self._keys))

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, DottedKey) and self._keys == __o._keys


class Item:
    """
    An item within a TOML document.
    """

    def __init__(self, trivia: Trivia) -> None:
        self._trivia = trivia

    @property
    def trivia(self) -> Trivia:
        """The trivia element associated with this item"""
        return self._trivia

    @property
    def discriminant(self) -> int:
        raise NotImplementedError()

    def as_string(self) -> str:
        """The TOML representation"""
        raise NotImplementedError()

    @property
    def value(self) -> Any:
        return self

    def unwrap(self) -> Any:
        """Returns as pure python object (ppo)"""
        raise NotImplementedError()

    # Helpers

    def comment(self, comment: str) -> Item:
        """Attach a comment to this item"""
        if not comment.strip().startswith("#"):
            comment = "# " + comment

        self._trivia.comment_ws = " "
        self._trivia.comment = comment

        return self

    def indent(self, indent: int) -> Item:
        """Indent this item with given number of spaces"""
        if self._trivia.indent.startswith("\n"):
            self._trivia.indent = "\n" + " " * indent
        else:
            self._trivia.indent = " " * indent

        return self

    def is_boolean(self) -> bool:
        return isinstance(self, Bool)

    def is_table(self) -> bool:
        return isinstance(self, Table)

    def is_inline_table(self) -> bool:
        return isinstance(self, InlineTable)

    def is_aot(self) -> bool:
        return isinstance(self, AoT)

    def _getstate(self, protocol=3):
        return (self._trivia,)

    def __reduce__(self):
        return self.__reduce_ex__(2)

    def __reduce_ex__(self, protocol):
        return self.__class__, self._getstate(protocol)


class Whitespace(Item):
    """
    A whitespace literal.
    """

    def __init__(self, s: str, fixed: bool = False) -> None:
        self._s = s
        self._fixed = fixed

    @property
    def s(self) -> str:
        return self._s

    @property
    def value(self) -> str:
        """The wrapped string of the whitespace"""
        return self._s

    @property
    def trivia(self) -> Trivia:
        raise RuntimeError("Called trivia on a Whitespace variant.")

    @property
    def discriminant(self) -> int:
        return 0

    def is_fixed(self) -> bool:
        """If the whitespace is fixed, it can't be merged or discarded from the output."""
        return self._fixed

    def as_string(self) -> str:
        return self._s

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {repr(self._s)}>"

    def _getstate(self, protocol=3):
        return self._s, self._fixed


class Comment(Item):
    """
    A comment literal.
    """

    @property
    def discriminant(self) -> int:
        return 1

    def as_string(self) -> str:
        return (
            f"{self._trivia.indent}{decode(self._trivia.comment)}{self._trivia.trail}"
        )

    def __str__(self) -> str:
        return f"{self._trivia.indent}{decode(self._trivia.comment)}"


class Integer(int, Item):
    """
    An integer literal.
    """

    def __new__(cls, value: int, trivia: Trivia, raw: str) -> Integer:
        return super().__new__(cls, value)

    def __init__(self, _: int, trivia: Trivia, raw: str) -> None:
        super().__init__(trivia)

        self._raw = raw
        self._sign = False

        if re.match(r"^[+\-]\d+$", raw):
            self._sign = True

    def unwrap(self) -> int:
        return int(self)

    @property
    def discriminant(self) -> int:
        return 2

    @property
    def value(self) -> int:
        """The wrapped integer value"""
        return self

    def as_string(self) -> str:
        return self._raw

    def __add__(self, other):
        result = super().__add__(other)
        if result is NotImplemented:
            return result
        return self._new(result)

    def __radd__(self, other):
        result = super().__radd__(other)
        if result is NotImplemented:
            return result
        return self._new(result)

    def __sub__(self, other):
        result = super().__sub__(other)
        if result is NotImplemented:
            return result
        return self._new(result)

    def __rsub__(self, other):
        result = super().__rsub__(other)
        if result is NotImplemented:
            return result
        return self._new(result)

    def _new(self, result):
        raw = str(result)
        if self._sign:
            sign = "+" if result >= 0 else "-"
            raw = sign + raw

        return Integer(result, self._trivia, raw)

    def _getstate(self, protocol=3):
        return int(self), self._trivia, self._raw


class Float(float, Item):
    """
    A float literal.
    """

    def __new__(cls, value: float, trivia: Trivia, raw: str) -> Integer:
        return super().__new__(cls, value)

    def __init__(self, _: float, trivia: Trivia, raw: str) -> None:
        super().__init__(trivia)

        self._raw = raw
        self._sign = False

        if re.match(r"^[+\-].+$", raw):
            self._sign = True

    def unwrap(self) -> float:
        return float(self)

    @property
    def discriminant(self) -> int:
        return 3

    @property
    def value(self) -> float:
        """The wrapped float value"""
        return self

    def as_string(self) -> str:
        return self._raw

    def __add__(self, other):
        result = super().__add__(other)

        return self._new(result)

    def __radd__(self, other):
        result = super().__radd__(other)

        if isinstance(other, Float):
            return self._new(result)

        return result

    def __sub__(self, other):
        result = super().__sub__(other)

        return self._new(result)

    def __rsub__(self, other):
        result = super().__rsub__(other)

        if isinstance(other, Float):
            return self._new(result)

        return result

    def _new(self, result):
        raw = str(result)

        if self._sign:
            sign = "+" if result >= 0 else "-"
            raw = sign + raw

        return Float(result, self._trivia, raw)

    def _getstate(self, protocol=3):
        return float(self), self._trivia, self._raw


class Bool(Item):
    """
    A boolean literal.
    """

    def __init__(self, t: int, trivia: Trivia) -> None:
        super().__init__(trivia)

        self._value = bool(t)

    def unwrap(self) -> bool:
        return bool(self)

    @property
    def discriminant(self) -> int:
        return 4

    @property
    def value(self) -> bool:
        """The wrapped boolean value"""
        return self._value

    def as_string(self) -> str:
        return str(self._value).lower()

    def _getstate(self, protocol=3):
        return self._value, self._trivia

    def __bool__(self):
        return self._value

    __nonzero__ = __bool__

    def __eq__(self, other):
        if not isinstance(other, bool):
            return NotImplemented

        return other == self._value

    def __hash__(self):
        return hash(self._value)

    def __repr__(self):
        return repr(self._value)


class DateTime(Item, datetime):
    """
    A datetime literal.
    """

    def __new__(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        microsecond: int,
        tzinfo: tzinfo | None,
        *_: Any,
        **kwargs: Any,
    ) -> datetime:
        return datetime.__new__(
            cls,
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo=tzinfo,
            **kwargs,
        )

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        microsecond: int,
        tzinfo: tzinfo | None,
        trivia: Trivia | None = None,
        raw: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(trivia or Trivia())

        self._raw = raw or self.isoformat()

    def unwrap(self) -> datetime:
        (
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo,
            _,
            _,
        ) = self._getstate()
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo)

    @property
    def discriminant(self) -> int:
        return 5

    @property
    def value(self) -> datetime:
        return self

    def as_string(self) -> str:
        return self._raw

    def __add__(self, other):
        if PY38:
            result = datetime(
                self.year,
                self.month,
                self.day,
                self.hour,
                self.minute,
                self.second,
                self.microsecond,
                self.tzinfo,
            ).__add__(other)
        else:
            result = super().__add__(other)

        return self._new(result)

    def __sub__(self, other):
        if PY38:
            result = datetime(
                self.year,
                self.month,
                self.day,
                self.hour,
                self.minute,
                self.second,
                self.microsecond,
                self.tzinfo,
            ).__sub__(other)
        else:
            result = super().__sub__(other)

        if isinstance(result, datetime):
            result = self._new(result)

        return result

    def replace(self, *args: Any, **kwargs: Any) -> datetime:
        return self._new(super().replace(*args, **kwargs))

    def astimezone(self, tz: tzinfo) -> datetime:
        result = super().astimezone(tz)
        if PY38:
            return result
        return self._new(result)

    def _new(self, result) -> DateTime:
        raw = result.isoformat()

        return DateTime(
            result.year,
            result.month,
            result.day,
            result.hour,
            result.minute,
            result.second,
            result.microsecond,
            result.tzinfo,
            self._trivia,
            raw,
        )

    def _getstate(self, protocol=3):
        return (
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
            self.tzinfo,
            self._trivia,
            self._raw,
        )


class Date(Item, date):
    """
    A date literal.
    """

    def __new__(cls, year: int, month: int, day: int, *_: Any) -> date:
        return date.__new__(cls, year, month, day)

    def __init__(
        self, year: int, month: int, day: int, trivia: Trivia, raw: str
    ) -> None:
        super().__init__(trivia)

        self._raw = raw

    def unwrap(self) -> date:
        (year, month, day, _, _) = self._getstate()
        return date(year, month, day)

    @property
    def discriminant(self) -> int:
        return 6

    @property
    def value(self) -> date:
        return self

    def as_string(self) -> str:
        return self._raw

    def __add__(self, other):
        if PY38:
            result = date(self.year, self.month, self.day).__add__(other)
        else:
            result = super().__add__(other)

        return self._new(result)

    def __sub__(self, other):
        if PY38:
            result = date(self.year, self.month, self.day).__sub__(other)
        else:
            result = super().__sub__(other)

        if isinstance(result, date):
            result = self._new(result)

        return result

    def replace(self, *args: Any, **kwargs: Any) -> date:
        return self._new(super().replace(*args, **kwargs))

    def _new(self, result):
        raw = result.isoformat()

        return Date(result.year, result.month, result.day, self._trivia, raw)

    def _getstate(self, protocol=3):
        return (self.year, self.month, self.day, self._trivia, self._raw)


class Time(Item, time):
    """
    A time literal.
    """

    def __new__(
        cls,
        hour: int,
        minute: int,
        second: int,
        microsecond: int,
        tzinfo: tzinfo | None,
        *_: Any,
    ) -> time:
        return time.__new__(cls, hour, minute, second, microsecond, tzinfo)

    def __init__(
        self,
        hour: int,
        minute: int,
        second: int,
        microsecond: int,
        tzinfo: tzinfo | None,
        trivia: Trivia,
        raw: str,
    ) -> None:
        super().__init__(trivia)

        self._raw = raw

    def unwrap(self) -> time:
        (hour, minute, second, microsecond, tzinfo, _, _) = self._getstate()
        return time(hour, minute, second, microsecond, tzinfo)

    @property
    def discriminant(self) -> int:
        return 7

    @property
    def value(self) -> time:
        return self

    def as_string(self) -> str:
        return self._raw

    def replace(self, *args: Any, **kwargs: Any) -> time:
        return self._new(super().replace(*args, **kwargs))

    def _new(self, result):
        raw = result.isoformat()

        return Time(
            result.hour,
            result.minute,
            result.second,
            result.microsecond,
            result.tzinfo,
            self._trivia,
            raw,
        )

    def _getstate(self, protocol: int = 3) -> tuple:
        return (
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
            self.tzinfo,
            self._trivia,
            self._raw,
        )


class _ArrayItemGroup:
    __slots__ = ("value", "indent", "comma", "comment")

    def __init__(
        self,
        value: Item | None = None,
        indent: Whitespace | None = None,
        comma: Whitespace | None = None,
        comment: Comment | None = None,
    ) -> None:
        self.value = value
        self.indent = indent
        self.comma = comma
        self.comment = comment

    def __iter__(self) -> Iterator[Item]:
        return filter(
            lambda x: x is not None, (self.indent, self.value, self.comma, self.comment)
        )

    def __repr__(self) -> str:
        return repr(tuple(self))

    def is_whitespace(self) -> bool:
        return self.value is None and self.comment is None

    def __bool__(self) -> bool:
        try:
            next(iter(self))
        except StopIteration:
            return False
        return True


class Array(Item, _CustomList):
    """
    An array literal
    """

    def __init__(
        self, value: list[Item], trivia: Trivia, multiline: bool = False
    ) -> None:
        super().__init__(trivia)
        list.__init__(
            self,
            [v for v in value if not isinstance(v, (Whitespace, Comment, Null))],
        )
        self._index_map: dict[int, int] = {}
        self._value = self._group_values(value)
        self._multiline = multiline
        self._reindex()

    def _group_values(self, value: list[Item]) -> list[_ArrayItemGroup]:
        """Group the values into (indent, value, comma, comment) tuples"""
        groups = []
        this_group = _ArrayItemGroup()
        for item in value:
            if isinstance(item, Whitespace):
                if "," not in item.s:
                    groups.append(this_group)
                    this_group = _ArrayItemGroup(indent=item)
                else:
                    if this_group.value is None:
                        # when comma is met and no value is provided, add a dummy Null
                        this_group.value = Null()
                    this_group.comma = item
            elif isinstance(item, Comment):
                if this_group.value is None:
                    this_group.value = Null()
                this_group.comment = item
            elif this_group.value is None:
                this_group.value = item
            else:
                groups.append(this_group)
                this_group = _ArrayItemGroup(value=item)
        groups.append(this_group)
        return [group for group in groups if group]

    def unwrap(self) -> list[Any]:
        unwrapped = []
        for v in self:
            if hasattr(v, "unwrap"):
                unwrapped.append(v.unwrap())
            else:
                unwrapped.append(v)
        return unwrapped

    @property
    def discriminant(self) -> int:
        return 8

    @property
    def value(self) -> list:
        return self

    def _iter_items(self) -> Iterator[Item]:
        for v in self._value:
            yield from v

    def multiline(self, multiline: bool) -> Array:
        """Change the array to display in multiline or not.

        :Example:

        >>> a = item([1, 2, 3])
        >>> print(a.as_string())
        [1, 2, 3]
        >>> print(a.multiline(True).as_string())
        [
            1,
            2,
            3,
        ]
        """
        self._multiline = multiline

        return self

    def as_string(self) -> str:
        if not self._multiline or not self._value:
            return f'[{"".join(v.as_string() for v in self._iter_items())}]'

        s = "[\n"
        s += "".join(
            self.trivia.indent
            + " " * 4
            + v.value.as_string()
            + ("," if not isinstance(v.value, Null) else "")
            + (v.comment.as_string() if v.comment is not None else "")
            + "\n"
            for v in self._value
            if v.value is not None
        )
        s += self.trivia.indent + "]"

        return s

    def _reindex(self) -> None:
        self._index_map.clear()
        index = 0
        for i, v in enumerate(self._value):
            if v.value is None or isinstance(v.value, Null):
                continue
            self._index_map[index] = i
            index += 1

    def add_line(
        self,
        *items: Any,
        indent: str = "    ",
        comment: str | None = None,
        add_comma: bool = True,
        newline: bool = True,
    ) -> None:
        """Add multiple items in a line to control the format precisely.
        When add_comma is True, only accept actual values and
        ", " will be added between values automatically.

        :Example:

        >>> a = array()
        >>> a.add_line(1, 2, 3)
        >>> a.add_line(4, 5, 6)
        >>> a.add_line(indent="")
        >>> print(a.as_string())
        [
            1, 2, 3,
            4, 5, 6,
        ]
        """
        new_values: list[Item] = []
        first_indent = f"\n{indent}" if newline else indent
        if first_indent:
            new_values.append(Whitespace(first_indent))
        whitespace = ""
        data_values = []
        for i, el in enumerate(items):
            it = item(el, _parent=self)
            if isinstance(it, Comment) or add_comma and isinstance(el, Whitespace):
                raise ValueError(f"item type {type(it)} is not allowed in add_line")
            if not isinstance(it, Whitespace):
                if whitespace:
                    new_values.append(Whitespace(whitespace))
                    whitespace = ""
                new_values.append(it)
                data_values.append(it.value)
                if add_comma:
                    new_values.append(Whitespace(","))
                    if i != len(items) - 1:
                        new_values.append(Whitespace(" "))
            elif "," not in it.s:
                whitespace += it.s
            else:
                new_values.append(it)
        if whitespace:
            new_values.append(Whitespace(whitespace))
        if comment:
            indent = " " if items else ""
            new_values.append(
                Comment(Trivia(indent=indent, comment=f"# {comment}", trail=""))
            )
        list.extend(self, data_values)
        if len(self._value) > 0:
            last_item = self._value[-1]
            last_value_item = next(
                (
                    v
                    for v in self._value[::-1]
                    if v.value is not None and not isinstance(v.value, Null)
                ),
                None,
            )
            if last_value_item is not None:
                last_value_item.comma = Whitespace(",")
            if last_item.is_whitespace():
                self._value[-1:-1] = self._group_values(new_values)
            else:
                self._value.extend(self._group_values(new_values))
        else:
            self._value.extend(self._group_values(new_values))
        self._reindex()

    def clear(self) -> None:
        """Clear the array."""
        list.clear(self)
        self._index_map.clear()
        self._value.clear()

    def __len__(self) -> int:
        return list.__len__(self)

    def __getitem__(self, key: int | slice) -> Any:
        rv = cast(Item, list.__getitem__(self, key))
        if rv.is_boolean():
            return bool(rv)
        return rv

    def __setitem__(self, key: int | slice, value: Any) -> Any:
        it = item(value, _parent=self)
        list.__setitem__(self, key, it)
        if isinstance(key, slice):
            raise ValueError("slice assignment is not supported")
        if key < 0:
            key += len(self)
        self._value[self._index_map[key]].value = it

    def insert(self, pos: int, value: Any) -> None:
        it = item(value, _parent=self)
        length = len(self)
        if not isinstance(it, (Comment, Whitespace)):
            list.insert(self, pos, it)
        if pos < 0:
            pos += length
            if pos < 0:
                pos = 0

        idx = 0  # insert position of the self._value list
        default_indent = " "
        if pos < length:
            try:
                idx = self._index_map[pos]
            except KeyError as e:
                raise IndexError("list index out of range") from e
        else:
            idx = len(self._value)
            if idx >= 1 and self._value[idx - 1].is_whitespace():
                # The last item is a pure whitespace(\n ), insert before it
                idx -= 1
                if (
                    self._value[idx].indent is not None
                    and "\n" in self._value[idx].indent.s
                ):
                    default_indent = "\n    "
        indent: Item | None = None
        comma: Item | None = Whitespace(",") if pos < length else None
        if idx < len(self._value) and not self._value[idx].is_whitespace():
            # Prefer to copy the indentation from the item after
            indent = self._value[idx].indent
        if idx > 0:
            last_item = self._value[idx - 1]
            if indent is None:
                indent = last_item.indent
            if not isinstance(last_item.value, Null) and "\n" in default_indent:
                # Copy the comma from the last item if 1) it contains a value and
                # 2) the array is multiline
                comma = last_item.comma
            if last_item.comma is None and not isinstance(last_item.value, Null):
                # Add comma to the last item to separate it from the following items.
                last_item.comma = Whitespace(",")
        if indent is None and (idx > 0 or "\n" in default_indent):
            # apply default indent if it isn't the first item or the array is multiline.
            indent = Whitespace(default_indent)
        new_item = _ArrayItemGroup(value=it, indent=indent, comma=comma)
        self._value.insert(idx, new_item)
        self._reindex()

    def __delitem__(self, key: int | slice):
        length = len(self)
        list.__delitem__(self, key)

        if isinstance(key, slice):
            indices_to_remove = list(
                range(key.start or 0, key.stop or length, key.step or 1)
            )
        else:
            indices_to_remove = [length + key if key < 0 else key]
        for i in sorted(indices_to_remove, reverse=True):
            try:
                idx = self._index_map[i]
            except KeyError as e:
                if not isinstance(key, slice):
                    raise IndexError("list index out of range") from e
            else:
                del self._value[idx]
                if (
                    idx == 0
                    and len(self._value) > 0
                    and "\n" not in self._value[idx].indent.s
                ):
                    # Remove the indentation of the first item if not newline
                    self._value[idx].indent = None
        if len(self._value) > 0:
            v = self._value[-1]
            if not v.is_whitespace():
                # remove the comma of the last item
                v.comma = None

        self._reindex()

    def _getstate(self, protocol=3):
        return list(self._iter_items()), self._trivia, self._multiline


AT = TypeVar("AT", bound="AbstractTable")


class AbstractTable(Item, _CustomDict):
    """Common behaviour of both :class:`Table` and :class:`InlineTable`"""

    def __init__(self, value: container.Container, trivia: Trivia):
        Item.__init__(self, trivia)

        self._value = value

        for k, v in self._value.body:
            if k is not None:
                dict.__setitem__(self, k.key, v)

    def unwrap(self) -> dict[str, Any]:
        unwrapped = {}
        for k, v in self.items():
            if isinstance(k, Key):
                k = k.key
            if hasattr(v, "unwrap"):
                v = v.unwrap()
            unwrapped[k] = v

        return unwrapped

    @property
    def value(self) -> container.Container:
        return self._value

    @overload
    def append(self: AT, key: None, value: Comment | Whitespace) -> AT:
        ...

    @overload
    def append(self: AT, key: Key | str, value: Any) -> AT:
        ...

    def append(self, key, value):
        raise NotImplementedError

    @overload
    def add(self: AT, value: Comment | Whitespace) -> AT:
        ...

    @overload
    def add(self: AT, key: Key | str, value: Any) -> AT:
        ...

    def add(self, key, value=None):
        if value is None:
            if not isinstance(key, (Comment, Whitespace)):
                msg = "Non comment/whitespace items must have an associated key"
                raise ValueError(msg)

            key, value = None, key

        return self.append(key, value)

    def remove(self: AT, key: Key | str) -> AT:
        self._value.remove(key)

        if isinstance(key, Key):
            key = key.key

        if key is not None:
            dict.__delitem__(self, key)

        return self

    def setdefault(self, key: Key | str, default: Any) -> Any:
        super().setdefault(key, default)
        return self[key]

    def __str__(self):
        return str(self.value)

    def copy(self: AT) -> AT:
        return copy.copy(self)

    def __repr__(self) -> str:
        return repr(self.value)

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __delitem__(self, key: Key | str) -> None:
        self.remove(key)

    def __getitem__(self, key: Key | str) -> Item:
        return cast(Item, self._value[key])

    def __setitem__(self, key: Key | str, value: Any) -> None:
        if not isinstance(value, Item):
            value = item(value, _parent=self)

        is_replace = key in self
        self._value[key] = value

        if key is not None:
            dict.__setitem__(self, key, value)

        if is_replace:
            return
        m = re.match("(?s)^[^ ]*([ ]+).*$", self._trivia.indent)
        if not m:
            return

        indent = m.group(1)

        if not isinstance(value, Whitespace):
            m = re.match("(?s)^([^ ]*)(.*)$", value.trivia.indent)
            if not m:
                value.trivia.indent = indent
            else:
                value.trivia.indent = m.group(1) + indent + m.group(2)


class Table(AbstractTable):
    """
    A table literal.
    """

    def __init__(
        self,
        value: container.Container,
        trivia: Trivia,
        is_aot_element: bool,
        is_super_table: bool | None = None,
        name: str | None = None,
        display_name: str | None = None,
    ) -> None:
        super().__init__(value, trivia)

        self.name = name
        self.display_name = display_name
        self._is_aot_element = is_aot_element
        self._is_super_table = is_super_table

    @property
    def discriminant(self) -> int:
        return 9

    def __copy__(self) -> Table:
        return type(self)(
            self._value.copy(),
            self._trivia.copy(),
            self._is_aot_element,
            self._is_super_table,
            self.name,
            self.display_name,
        )

    def append(self, key: Key | str | None, _item: Any) -> Table:
        """
        Appends a (key, item) to the table.
        """
        if not isinstance(_item, Item):
            _item = item(_item, _parent=self)

        self._value.append(key, _item)

        if isinstance(key, Key):
            key = next(iter(key)).key
            _item = self._value[key]

        if key is not None:
            dict.__setitem__(self, key, _item)

        m = re.match(r"(?s)^[^ ]*([ ]+).*$", self._trivia.indent)
        if not m:
            return self

        indent = m.group(1)

        if not isinstance(_item, Whitespace):
            m = re.match("(?s)^([^ ]*)(.*)$", _item.trivia.indent)
            if not m:
                _item.trivia.indent = indent
            else:
                _item.trivia.indent = m.group(1) + indent + m.group(2)

        return self

    def raw_append(self, key: Key | str | None, _item: Any) -> Table:
        """Similar to :meth:`append` but does not copy indentation."""
        if not isinstance(_item, Item):
            _item = item(_item)

        self._value.append(key, _item)

        if isinstance(key, Key):
            key = next(iter(key)).key
            _item = self._value[key]

        if key is not None:
            dict.__setitem__(self, key, _item)

        return self

    def is_aot_element(self) -> bool:
        """True if the table is the direct child of an AOT element."""
        return self._is_aot_element

    def is_super_table(self) -> bool:
        """A super table is the intermediate parent of a nested table as in [a.b.c].
        If true, it won't appear in the TOML representation."""
        if self._is_super_table is not None:
            return self._is_super_table
        # If the table has only one child and that child is a table, then it is a super table.
        if len(self) != 1:
            return False
        only_child = next(iter(self.values()))
        return isinstance(only_child, (Table, AoT))

    def as_string(self) -> str:
        return self._value.as_string()

    # Helpers

    def indent(self, indent: int) -> Table:
        """Indent the table with given number of spaces."""
        super().indent(indent)

        m = re.match("(?s)^[^ ]*([ ]+).*$", self._trivia.indent)
        if not m:
            indent_str = ""
        else:
            indent_str = m.group(1)

        for _, item in self._value.body:
            if not isinstance(item, Whitespace):
                item.trivia.indent = indent_str + item.trivia.indent

        return self

    def invalidate_display_name(self):
        self.display_name = None

        for child in self.values():
            if hasattr(child, "invalidate_display_name"):
                child.invalidate_display_name()

    def _getstate(self, protocol: int = 3) -> tuple:
        return (
            self._value,
            self._trivia,
            self._is_aot_element,
            self._is_super_table,
            self.name,
            self.display_name,
        )


class InlineTable(AbstractTable):
    """
    An inline table literal.
    """

    def __init__(
        self, value: container.Container, trivia: Trivia, new: bool = False
    ) -> None:
        super().__init__(value, trivia)

        self._new = new

    @property
    def discriminant(self) -> int:
        return 10

    def append(self, key: Key | str | None, _item: Any) -> InlineTable:
        """
        Appends a (key, item) to the table.
        """
        if not isinstance(_item, Item):
            _item = item(_item, _parent=self)

        if not isinstance(_item, (Whitespace, Comment)):
            if not _item.trivia.indent and len(self._value) > 0 and not self._new:
                _item.trivia.indent = " "
            if _item.trivia.comment:
                _item.trivia.comment = ""

        self._value.append(key, _item)

        if isinstance(key, Key):
            key = key.key

        if key is not None:
            dict.__setitem__(self, key, _item)

        return self

    def as_string(self) -> str:
        buf = "{"
        last_item_idx = next(
            (
                i
                for i in range(len(self._value.body) - 1, -1, -1)
                if self._value.body[i][0] is not None
            ),
            None,
        )
        for i, (k, v) in enumerate(self._value.body):
            if k is None:
                if i == len(self._value.body) - 1:
                    if self._new:
                        buf = buf.rstrip(", ")
                    else:
                        buf = buf.rstrip(",")

                buf += v.as_string()

                continue

            v_trivia_trail = v.trivia.trail.replace("\n", "")
            buf += (
                f"{v.trivia.indent}"
                f'{k.as_string() + ("." if k.is_dotted() else "")}'
                f"{k.sep}"
                f"{v.as_string()}"
                f"{v.trivia.comment}"
                f"{v_trivia_trail}"
            )

            if last_item_idx is not None and i < last_item_idx:
                buf += ","
                if self._new:
                    buf += " "

        buf += "}"

        return buf

    def __setitem__(self, key: Key | str, value: Any) -> None:
        if hasattr(value, "trivia") and value.trivia.comment:
            value.trivia.comment = ""
        super().__setitem__(key, value)

    def __copy__(self) -> InlineTable:
        return type(self)(self._value.copy(), self._trivia.copy(), self._new)

    def _getstate(self, protocol: int = 3) -> tuple:
        return (self._value, self._trivia)


class String(str, Item):
    """
    A string literal.
    """

    def __new__(cls, t, value, original, trivia):
        return super().__new__(cls, value)

    def __init__(self, t: StringType, _: str, original: str, trivia: Trivia) -> None:
        super().__init__(trivia)

        self._t = t
        self._original = original

    def unwrap(self) -> str:
        return str(self)

    @property
    def discriminant(self) -> int:
        return 11

    @property
    def value(self) -> str:
        return self

    def as_string(self) -> str:
        return f"{self._t.value}{decode(self._original)}{self._t.value}"

    def __add__(self: ItemT, other: str) -> ItemT:
        if not isinstance(other, str):
            return NotImplemented
        result = super().__add__(other)
        original = self._original + getattr(other, "_original", other)

        return self._new(result, original)

    def _new(self, result: str, original: str) -> String:
        return String(self._t, result, original, self._trivia)

    def _getstate(self, protocol=3):
        return self._t, str(self), self._original, self._trivia

    @classmethod
    def from_raw(cls, value: str, type_=StringType.SLB, escape=True) -> String:
        value = decode(value)

        invalid = type_.invalid_sequences
        if any(c in value for c in invalid):
            raise InvalidStringError(value, invalid, type_.value)

        escaped = type_.escaped_sequences
        string_value = escape_string(value, escaped) if escape and escaped else value

        return cls(type_, decode(value), string_value, Trivia())


class AoT(Item, _CustomList):
    """
    An array of table literal
    """

    def __init__(
        self, body: list[Table], name: str | None = None, parsed: bool = False
    ) -> None:
        self.name = name
        self._body: list[Table] = []
        self._parsed = parsed

        super().__init__(Trivia(trail=""))

        for table in body:
            self.append(table)

    def unwrap(self) -> list[dict[str, Any]]:
        unwrapped = []
        for t in self._body:
            if hasattr(t, "unwrap"):
                unwrapped.append(t.unwrap())
            else:
                unwrapped.append(t)
        return unwrapped

    @property
    def body(self) -> list[Table]:
        return self._body

    @property
    def discriminant(self) -> int:
        return 12

    @property
    def value(self) -> list[dict[Any, Any]]:
        return [v.value for v in self._body]

    def __len__(self) -> int:
        return len(self._body)

    @overload
    def __getitem__(self, key: slice) -> list[Table]:
        ...

    @overload
    def __getitem__(self, key: int) -> Table:
        ...

    def __getitem__(self, key):
        return self._body[key]

    def __setitem__(self, key: slice | int, value: Any) -> None:
        raise NotImplementedError

    def __delitem__(self, key: slice | int) -> None:
        del self._body[key]
        list.__delitem__(self, key)

    def insert(self, index: int, value: dict) -> None:
        value = item(value, _parent=self)
        if not isinstance(value, Table):
            raise ValueError(f"Unsupported insert value type: {type(value)}")
        length = len(self)
        if index < 0:
            index += length
        if index < 0:
            index = 0
        elif index >= length:
            index = length
        m = re.match("(?s)^[^ ]*([ ]+).*$", self._trivia.indent)
        if m:
            indent = m.group(1)

            m = re.match("(?s)^([^ ]*)(.*)$", value.trivia.indent)
            if not m:
                value.trivia.indent = indent
            else:
                value.trivia.indent = m.group(1) + indent + m.group(2)
        prev_table = self._body[index - 1] if 0 < index and length else None
        next_table = self._body[index + 1] if index < length - 1 else None
        if not self._parsed:
            if prev_table and "\n" not in value.trivia.indent:
                value.trivia.indent = "\n" + value.trivia.indent
            if next_table and "\n" not in next_table.trivia.indent:
                next_table.trivia.indent = "\n" + next_table.trivia.indent
        self._body.insert(index, value)
        list.insert(self, index, value)

    def invalidate_display_name(self):
        """Call ``invalidate_display_name`` on the contained tables"""
        for child in self:
            if hasattr(child, "invalidate_display_name"):
                child.invalidate_display_name()

    def as_string(self) -> str:
        b = ""
        for table in self._body:
            b += table.as_string()

        return b

    def __repr__(self) -> str:
        return f"<AoT {self.value}>"

    def _getstate(self, protocol=3):
        return self._body, self.name, self._parsed


class Null(Item):
    """
    A null item.
    """

    def __init__(self) -> None:
        pass

    def unwrap(self) -> None:
        return None

    @property
    def discriminant(self) -> int:
        return -1

    @property
    def value(self) -> None:
        return None

    def as_string(self) -> str:
        return ""

    def _getstate(self, protocol=3) -> tuple:
        return ()
