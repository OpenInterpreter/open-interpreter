# util.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Module for general utility functions"""
# flake8: noqa F401


from abc import ABC, abstractmethod
import warnings
from git.util import IterableList, IterableObj, Actor

import re
from collections import deque

from string import digits
import time
import calendar
from datetime import datetime, timedelta, tzinfo

# typing ------------------------------------------------------------
from typing import (
    Any,
    Callable,
    Deque,
    Iterator,
    Generic,
    NamedTuple,
    overload,
    Sequence,  # NOQA: F401
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from git.types import Has_id_attribute, Literal, _T  # NOQA: F401

if TYPE_CHECKING:
    from io import BytesIO, StringIO
    from .commit import Commit
    from .blob import Blob
    from .tag import TagObject
    from .tree import Tree, TraversedTreeTup
    from subprocess import Popen
    from .submodule.base import Submodule
    from git.types import Protocol, runtime_checkable
else:
    # Protocol = Generic[_T]  # Needed for typing bug #572?
    Protocol = ABC

    def runtime_checkable(f):
        return f


class TraverseNT(NamedTuple):
    depth: int
    item: Union["Traversable", "Blob"]
    src: Union["Traversable", None]


T_TIobj = TypeVar("T_TIobj", bound="TraversableIterableObj")  # for TraversableIterableObj.traverse()

TraversedTup = Union[
    Tuple[Union["Traversable", None], "Traversable"],  # for commit, submodule
    "TraversedTreeTup",
]  # for tree.traverse()

# --------------------------------------------------------------------

__all__ = (
    "get_object_type_by_name",
    "parse_date",
    "parse_actor_and_date",
    "ProcessStreamAdapter",
    "Traversable",
    "altz_to_utctz_str",
    "utctz_to_altz",
    "verify_utctz",
    "Actor",
    "tzoffset",
    "utc",
)

ZERO = timedelta(0)

# { Functions


def mode_str_to_int(modestr: Union[bytes, str]) -> int:
    """
    :param modestr: string like 755 or 644 or 100644 - only the last 6 chars will be used
    :return:
        String identifying a mode compatible to the mode methods ids of the
        stat module regarding the rwx permissions for user, group and other,
        special flags and file system flags, i.e. whether it is a symlink
        for example."""
    mode = 0
    for iteration, char in enumerate(reversed(modestr[-6:])):
        char = cast(Union[str, int], char)
        mode += int(char) << iteration * 3
    # END for each char
    return mode


def get_object_type_by_name(
    object_type_name: bytes,
) -> Union[Type["Commit"], Type["TagObject"], Type["Tree"], Type["Blob"]]:
    """
    :return: type suitable to handle the given object type name.
        Use the type to create new instances.

    :param object_type_name: Member of TYPES

    :raise ValueError: In case object_type_name is unknown"""
    if object_type_name == b"commit":
        from . import commit

        return commit.Commit
    elif object_type_name == b"tag":
        from . import tag

        return tag.TagObject
    elif object_type_name == b"blob":
        from . import blob

        return blob.Blob
    elif object_type_name == b"tree":
        from . import tree

        return tree.Tree
    else:
        raise ValueError("Cannot handle unknown object type: %s" % object_type_name.decode())


def utctz_to_altz(utctz: str) -> int:
    """Convert a git timezone offset into a timezone offset west of
    UTC in seconds (compatible with time.altzone).

    :param utctz: git utc timezone string, i.e. +0200
    """
    int_utctz = int(utctz)
    seconds = ((abs(int_utctz) // 100) * 3600 + (abs(int_utctz) % 100) * 60)
    return seconds if int_utctz < 0 else -seconds


def altz_to_utctz_str(altz: int) -> str:
    """Convert a timezone offset west of UTC in seconds into a git timezone offset string

    :param altz: timezone offset in seconds west of UTC
    """
    hours = abs(altz) // 3600
    minutes = (abs(altz) % 3600) // 60
    sign = "-" if altz >= 60 else "+"
    return "{}{:02}{:02}".format(sign, hours, minutes)


def verify_utctz(offset: str) -> str:
    """:raise ValueError: if offset is incorrect
    :return: offset"""
    fmt_exc = ValueError("Invalid timezone offset format: %s" % offset)
    if len(offset) != 5:
        raise fmt_exc
    if offset[0] not in "+-":
        raise fmt_exc
    if offset[1] not in digits or offset[2] not in digits or offset[3] not in digits or offset[4] not in digits:
        raise fmt_exc
    # END for each char
    return offset


class tzoffset(tzinfo):
    def __init__(self, secs_west_of_utc: float, name: Union[None, str] = None) -> None:
        self._offset = timedelta(seconds=-secs_west_of_utc)
        self._name = name or "fixed"

    def __reduce__(self) -> Tuple[Type["tzoffset"], Tuple[float, str]]:
        return tzoffset, (-self._offset.total_seconds(), self._name)

    def utcoffset(self, dt: Union[datetime, None]) -> timedelta:
        return self._offset

    def tzname(self, dt: Union[datetime, None]) -> str:
        return self._name

    def dst(self, dt: Union[datetime, None]) -> timedelta:
        return ZERO


utc = tzoffset(0, "UTC")


def from_timestamp(timestamp: float, tz_offset: float) -> datetime:
    """Converts a timestamp + tz_offset into an aware datetime instance."""
    utc_dt = datetime.fromtimestamp(timestamp, utc)
    try:
        local_dt = utc_dt.astimezone(tzoffset(tz_offset))
        return local_dt
    except ValueError:
        return utc_dt


def parse_date(string_date: Union[str, datetime]) -> Tuple[int, int]:
    """
    Parse the given date as one of the following

        * aware datetime instance
        * Git internal format: timestamp offset
        * RFC 2822: Thu, 07 Apr 2005 22:13:13 +0200.
        * ISO 8601 2005-04-07T22:13:13
            The T can be a space as well

    :return: Tuple(int(timestamp_UTC), int(offset)), both in seconds since epoch
    :raise ValueError: If the format could not be understood
    :note: Date can also be YYYY.MM.DD, MM/DD/YYYY and DD.MM.YYYY.
    """
    if isinstance(string_date, datetime):
        if string_date.tzinfo:
            utcoffset = cast(timedelta, string_date.utcoffset())  # typeguard, if tzinfoand is not None
            offset = -int(utcoffset.total_seconds())
            return int(string_date.astimezone(utc).timestamp()), offset
        else:
            raise ValueError(f"string_date datetime object without tzinfo, {string_date}")

    # git time
    try:
        if string_date.count(" ") == 1 and string_date.rfind(":") == -1:
            timestamp, offset_str = string_date.split()
            if timestamp.startswith("@"):
                timestamp = timestamp[1:]
            timestamp_int = int(timestamp)
            return timestamp_int, utctz_to_altz(verify_utctz(offset_str))
        else:
            offset_str = "+0000"  # local time by default
            if string_date[-5] in "-+":
                offset_str = verify_utctz(string_date[-5:])
                string_date = string_date[:-6]  # skip space as well
            # END split timezone info
            offset = utctz_to_altz(offset_str)

            # now figure out the date and time portion - split time
            date_formats = []
            splitter = -1
            if "," in string_date:
                date_formats.append("%a, %d %b %Y")
                splitter = string_date.rfind(" ")
            else:
                # iso plus additional
                date_formats.append("%Y-%m-%d")
                date_formats.append("%Y.%m.%d")
                date_formats.append("%m/%d/%Y")
                date_formats.append("%d.%m.%Y")

                splitter = string_date.rfind("T")
                if splitter == -1:
                    splitter = string_date.rfind(" ")
                # END handle 'T' and ' '
            # END handle rfc or iso

            assert splitter > -1

            # split date and time
            time_part = string_date[splitter + 1 :]  # skip space
            date_part = string_date[:splitter]

            # parse time
            tstruct = time.strptime(time_part, "%H:%M:%S")

            for fmt in date_formats:
                try:
                    dtstruct = time.strptime(date_part, fmt)
                    utctime = calendar.timegm(
                        (
                            dtstruct.tm_year,
                            dtstruct.tm_mon,
                            dtstruct.tm_mday,
                            tstruct.tm_hour,
                            tstruct.tm_min,
                            tstruct.tm_sec,
                            dtstruct.tm_wday,
                            dtstruct.tm_yday,
                            tstruct.tm_isdst,
                        )
                    )
                    return int(utctime), offset
                except ValueError:
                    continue
                # END exception handling
            # END for each fmt

            # still here ? fail
            raise ValueError("no format matched")
        # END handle format
    except Exception as e:
        raise ValueError(f"Unsupported date format or type: {string_date}, type={type(string_date)}") from e
    # END handle exceptions


# precompiled regex
_re_actor_epoch = re.compile(r"^.+? (.*) (\d+) ([+-]\d+).*$")
_re_only_actor = re.compile(r"^.+? (.*)$")


def parse_actor_and_date(line: str) -> Tuple[Actor, int, int]:
    """Parse out the actor (author or committer) info from a line like::

        author Tom Preston-Werner <tom@mojombo.com> 1191999972 -0700

    :return: [Actor, int_seconds_since_epoch, int_timezone_offset]"""
    actor, epoch, offset = "", "0", "0"
    m = _re_actor_epoch.search(line)
    if m:
        actor, epoch, offset = m.groups()
    else:
        m = _re_only_actor.search(line)
        actor = m.group(1) if m else line or ""
    return (Actor._from_string(actor), int(epoch), utctz_to_altz(offset))


# } END functions


# { Classes


class ProcessStreamAdapter(object):

    """Class wireing all calls to the contained Process instance.

    Use this type to hide the underlying process to provide access only to a specified
    stream. The process is usually wrapped into an AutoInterrupt class to kill
    it if the instance goes out of scope."""

    __slots__ = ("_proc", "_stream")

    def __init__(self, process: "Popen", stream_name: str) -> None:
        self._proc = process
        self._stream: StringIO = getattr(process, stream_name)  # guessed type

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._stream, attr)


@runtime_checkable
class Traversable(Protocol):

    """Simple interface to perform depth-first or breadth-first traversals
    into one direction.
    Subclasses only need to implement one function.
    Instances of the Subclass must be hashable

    Defined subclasses = [Commit, Tree, SubModule]
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def _get_intermediate_items(cls, item: Any) -> Sequence["Traversable"]:
        """
        Returns:
            Tuple of items connected to the given item.
            Must be implemented in subclass

        class Commit::     (cls, Commit) -> Tuple[Commit, ...]
        class Submodule::  (cls, Submodule) -> Iterablelist[Submodule]
        class Tree::       (cls, Tree) -> Tuple[Tree, ...]
        """
        raise NotImplementedError("To be implemented in subclass")

    @abstractmethod
    def list_traverse(self, *args: Any, **kwargs: Any) -> Any:
        """ """
        warnings.warn(
            "list_traverse() method should only be called from subclasses."
            "Calling from Traversable abstract class will raise NotImplementedError in 3.1.20"
            "Builtin sublclasses are 'Submodule', 'Tree' and 'Commit",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._list_traverse(*args, **kwargs)

    def _list_traverse(
        self, as_edge: bool = False, *args: Any, **kwargs: Any
    ) -> IterableList[Union["Commit", "Submodule", "Tree", "Blob"]]:
        """
        :return: IterableList with the results of the traversal as produced by
            traverse()
            Commit -> IterableList['Commit']
            Submodule ->  IterableList['Submodule']
            Tree -> IterableList[Union['Submodule', 'Tree', 'Blob']]
        """
        # Commit and Submodule have id.__attribute__ as IterableObj
        # Tree has id.__attribute__ inherited from IndexObject
        if isinstance(self, Has_id_attribute):
            id = self._id_attribute_
        else:
            id = ""  # shouldn't reach here, unless Traversable subclass created with no _id_attribute_
            # could add _id_attribute_ to Traversable, or make all Traversable also Iterable?

        if not as_edge:
            out: IterableList[Union["Commit", "Submodule", "Tree", "Blob"]] = IterableList(id)
            out.extend(self.traverse(as_edge=as_edge, *args, **kwargs))
            return out
            # overloads in subclasses (mypy doesn't allow typing self: subclass)
            # Union[IterableList['Commit'], IterableList['Submodule'], IterableList[Union['Submodule', 'Tree', 'Blob']]]
        else:
            # Raise deprecationwarning, doesn't make sense to use this
            out_list: IterableList = IterableList(self.traverse(*args, **kwargs))
            return out_list

    @abstractmethod
    def traverse(self, *args: Any, **kwargs: Any) -> Any:
        """ """
        warnings.warn(
            "traverse() method should only be called from subclasses."
            "Calling from Traversable abstract class will raise NotImplementedError in 3.1.20"
            "Builtin sublclasses are 'Submodule', 'Tree' and 'Commit",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._traverse(*args, **kwargs)

    def _traverse(
        self,
        predicate: Callable[[Union["Traversable", "Blob", TraversedTup], int], bool] = lambda i, d: True,
        prune: Callable[[Union["Traversable", "Blob", TraversedTup], int], bool] = lambda i, d: False,
        depth: int = -1,
        branch_first: bool = True,
        visit_once: bool = True,
        ignore_self: int = 1,
        as_edge: bool = False,
    ) -> Union[Iterator[Union["Traversable", "Blob"]], Iterator[TraversedTup]]:
        """:return: iterator yielding of items found when traversing self
        :param predicate: f(i,d) returns False if item i at depth d should not be included in the result

        :param prune:
            f(i,d) return True if the search should stop at item i at depth d.
            Item i will not be returned.

        :param depth:
            define at which level the iteration should not go deeper
            if -1, there is no limit
            if 0, you would effectively only get self, the root of the iteration
            i.e. if 1, you would only get the first level of predecessors/successors

        :param branch_first:
            if True, items will be returned branch first, otherwise depth first

        :param visit_once:
            if True, items will only be returned once, although they might be encountered
            several times. Loops are prevented that way.

        :param ignore_self:
            if True, self will be ignored and automatically pruned from
            the result. Otherwise it will be the first item to be returned.
            If as_edge is True, the source of the first edge is None

        :param as_edge:
            if True, return a pair of items, first being the source, second the
            destination, i.e. tuple(src, dest) with the edge spanning from
            source to destination"""

        """
            Commit -> Iterator[Union[Commit, Tuple[Commit, Commit]]
            Submodule -> Iterator[Submodule, Tuple[Submodule, Submodule]]
            Tree -> Iterator[Union[Blob, Tree, Submodule,
                                    Tuple[Union[Submodule, Tree], Union[Blob, Tree, Submodule]]]

           ignore_self=True is_edge=True -> Iterator[item]
           ignore_self=True is_edge=False --> Iterator[item]
           ignore_self=False is_edge=True -> Iterator[item] | Iterator[Tuple[src, item]]
           ignore_self=False is_edge=False -> Iterator[Tuple[src, item]]"""

        visited = set()
        stack: Deque[TraverseNT] = deque()
        stack.append(TraverseNT(0, self, None))  # self is always depth level 0

        def addToStack(
            stack: Deque[TraverseNT],
            src_item: "Traversable",
            branch_first: bool,
            depth: int,
        ) -> None:
            lst = self._get_intermediate_items(item)
            if not lst:  # empty list
                return None
            if branch_first:
                stack.extendleft(TraverseNT(depth, i, src_item) for i in lst)
            else:
                reviter = (TraverseNT(depth, lst[i], src_item) for i in range(len(lst) - 1, -1, -1))
                stack.extend(reviter)

        # END addToStack local method

        while stack:
            d, item, src = stack.pop()  # depth of item, item, item_source

            if visit_once and item in visited:
                continue

            if visit_once:
                visited.add(item)

            rval: Union[TraversedTup, "Traversable", "Blob"]
            if as_edge:  # if as_edge return (src, item) unless rrc is None (e.g. for first item)
                rval = (src, item)
            else:
                rval = item

            if prune(rval, d):
                continue

            skipStartItem = ignore_self and (item is self)
            if not skipStartItem and predicate(rval, d):
                yield rval

            # only continue to next level if this is appropriate !
            nd = d + 1
            if depth > -1 and nd > depth:
                continue

            addToStack(stack, item, branch_first, nd)
        # END for each item on work stack


@runtime_checkable
class Serializable(Protocol):

    """Defines methods to serialize and deserialize objects from and into a data stream"""

    __slots__ = ()

    # @abstractmethod
    def _serialize(self, stream: "BytesIO") -> "Serializable":
        """Serialize the data of this object into the given data stream
        :note: a serialized object would ``_deserialize`` into the same object
        :param stream: a file-like object
        :return: self"""
        raise NotImplementedError("To be implemented in subclass")

    # @abstractmethod
    def _deserialize(self, stream: "BytesIO") -> "Serializable":
        """Deserialize all information regarding this object from the stream
        :param stream: a file-like object
        :return: self"""
        raise NotImplementedError("To be implemented in subclass")


class TraversableIterableObj(IterableObj, Traversable):
    __slots__ = ()

    TIobj_tuple = Tuple[Union[T_TIobj, None], T_TIobj]

    def list_traverse(self: T_TIobj, *args: Any, **kwargs: Any) -> IterableList[T_TIobj]:
        return super(TraversableIterableObj, self)._list_traverse(*args, **kwargs)

    @overload  # type: ignore
    def traverse(self: T_TIobj) -> Iterator[T_TIobj]:
        ...

    @overload
    def traverse(
        self: T_TIobj,
        predicate: Callable[[Union[T_TIobj, Tuple[Union[T_TIobj, None], T_TIobj]], int], bool],
        prune: Callable[[Union[T_TIobj, Tuple[Union[T_TIobj, None], T_TIobj]], int], bool],
        depth: int,
        branch_first: bool,
        visit_once: bool,
        ignore_self: Literal[True],
        as_edge: Literal[False],
    ) -> Iterator[T_TIobj]:
        ...

    @overload
    def traverse(
        self: T_TIobj,
        predicate: Callable[[Union[T_TIobj, Tuple[Union[T_TIobj, None], T_TIobj]], int], bool],
        prune: Callable[[Union[T_TIobj, Tuple[Union[T_TIobj, None], T_TIobj]], int], bool],
        depth: int,
        branch_first: bool,
        visit_once: bool,
        ignore_self: Literal[False],
        as_edge: Literal[True],
    ) -> Iterator[Tuple[Union[T_TIobj, None], T_TIobj]]:
        ...

    @overload
    def traverse(
        self: T_TIobj,
        predicate: Callable[[Union[T_TIobj, TIobj_tuple], int], bool],
        prune: Callable[[Union[T_TIobj, TIobj_tuple], int], bool],
        depth: int,
        branch_first: bool,
        visit_once: bool,
        ignore_self: Literal[True],
        as_edge: Literal[True],
    ) -> Iterator[Tuple[T_TIobj, T_TIobj]]:
        ...

    def traverse(
        self: T_TIobj,
        predicate: Callable[[Union[T_TIobj, TIobj_tuple], int], bool] = lambda i, d: True,
        prune: Callable[[Union[T_TIobj, TIobj_tuple], int], bool] = lambda i, d: False,
        depth: int = -1,
        branch_first: bool = True,
        visit_once: bool = True,
        ignore_self: int = 1,
        as_edge: bool = False,
    ) -> Union[Iterator[T_TIobj], Iterator[Tuple[T_TIobj, T_TIobj]], Iterator[TIobj_tuple]]:
        """For documentation, see util.Traversable._traverse()"""

        """
        # To typecheck instead of using cast.
        import itertools
        from git.types import TypeGuard
        def is_commit_traversed(inp: Tuple) -> TypeGuard[Tuple[Iterator[Tuple['Commit', 'Commit']]]]:
            for x in inp[1]:
                if not isinstance(x, tuple) and len(x) != 2:
                    if all(isinstance(inner, Commit) for inner in x):
                        continue
            return True

        ret = super(Commit, self).traverse(predicate, prune, depth, branch_first, visit_once, ignore_self, as_edge)
        ret_tup = itertools.tee(ret, 2)
        assert is_commit_traversed(ret_tup), f"{[type(x) for x in list(ret_tup[0])]}"
        return ret_tup[0]
        """
        return cast(
            Union[Iterator[T_TIobj], Iterator[Tuple[Union[None, T_TIobj], T_TIobj]]],
            super(TraversableIterableObj, self)._traverse(
                predicate, prune, depth, branch_first, visit_once, ignore_self, as_edge  # type: ignore
            ),
        )
