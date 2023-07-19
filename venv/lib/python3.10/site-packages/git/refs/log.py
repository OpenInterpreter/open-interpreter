from mmap import mmap
import re
import time as _time

from git.compat import defenc
from git.objects.util import (
    parse_date,
    Serializable,
    altz_to_utctz_str,
)
from git.util import (
    Actor,
    LockedFD,
    LockFile,
    assure_directory_exists,
    to_native_path,
    bin_to_hex,
    file_contents_ro_filepath,
)

import os.path as osp


# typing ------------------------------------------------------------------

from typing import Iterator, List, Tuple, Union, TYPE_CHECKING

from git.types import PathLike

if TYPE_CHECKING:
    from git.refs import SymbolicReference
    from io import BytesIO
    from git.config import GitConfigParser, SectionConstraint  # NOQA

# ------------------------------------------------------------------------------

__all__ = ["RefLog", "RefLogEntry"]


class RefLogEntry(Tuple[str, str, Actor, Tuple[int, int], str]):

    """Named tuple allowing easy access to the revlog data fields"""

    _re_hexsha_only = re.compile("^[0-9A-Fa-f]{40}$")
    __slots__ = ()

    def __repr__(self) -> str:
        """Representation of ourselves in git reflog format"""
        return self.format()

    def format(self) -> str:
        """:return: a string suitable to be placed in a reflog file"""
        act = self.actor
        time = self.time
        return "{} {} {} <{}> {!s} {}\t{}\n".format(
            self.oldhexsha,
            self.newhexsha,
            act.name,
            act.email,
            time[0],
            altz_to_utctz_str(time[1]),
            self.message,
        )

    @property
    def oldhexsha(self) -> str:
        """The hexsha to the commit the ref pointed to before the change"""
        return self[0]

    @property
    def newhexsha(self) -> str:
        """The hexsha to the commit the ref now points to, after the change"""
        return self[1]

    @property
    def actor(self) -> Actor:
        """Actor instance, providing access"""
        return self[2]

    @property
    def time(self) -> Tuple[int, int]:
        """time as tuple:

        * [0] = int(time)
        * [1] = int(timezone_offset) in time.altzone format"""
        return self[3]

    @property
    def message(self) -> str:
        """Message describing the operation that acted on the reference"""
        return self[4]

    @classmethod
    def new(
        cls,
        oldhexsha: str,
        newhexsha: str,
        actor: Actor,
        time: int,
        tz_offset: int,
        message: str,
    ) -> "RefLogEntry":  # skipcq: PYL-W0621
        """:return: New instance of a RefLogEntry"""
        if not isinstance(actor, Actor):
            raise ValueError("Need actor instance, got %s" % actor)
        # END check types
        return RefLogEntry((oldhexsha, newhexsha, actor, (time, tz_offset), message))

    @classmethod
    def from_line(cls, line: bytes) -> "RefLogEntry":
        """:return: New RefLogEntry instance from the given revlog line.
        :param line: line bytes without trailing newline
        :raise ValueError: If line could not be parsed"""
        line_str = line.decode(defenc)
        fields = line_str.split("\t", 1)
        if len(fields) == 1:
            info, msg = fields[0], None
        elif len(fields) == 2:
            info, msg = fields
        else:
            raise ValueError("Line must have up to two TAB-separated fields." " Got %s" % repr(line_str))
        # END handle first split

        oldhexsha = info[:40]
        newhexsha = info[41:81]
        for hexsha in (oldhexsha, newhexsha):
            if not cls._re_hexsha_only.match(hexsha):
                raise ValueError("Invalid hexsha: %r" % (hexsha,))
            # END if hexsha re doesn't match
        # END for each hexsha

        email_end = info.find(">", 82)
        if email_end == -1:
            raise ValueError("Missing token: >")
        # END handle missing end brace

        actor = Actor._from_string(info[82 : email_end + 1])
        time, tz_offset = parse_date(info[email_end + 2 :])  # skipcq: PYL-W0621

        return RefLogEntry((oldhexsha, newhexsha, actor, (time, tz_offset), msg))


class RefLog(List[RefLogEntry], Serializable):

    """A reflog contains RefLogEntrys, each of which defines a certain state
    of the head in question. Custom query methods allow to retrieve log entries
    by date or by other criteria.

    Reflog entries are ordered, the first added entry is first in the list, the last
    entry, i.e. the last change of the head or reference, is last in the list."""

    __slots__ = ("_path",)

    def __new__(cls, filepath: Union[PathLike, None] = None) -> "RefLog":
        inst = super(RefLog, cls).__new__(cls)
        return inst

    def __init__(self, filepath: Union[PathLike, None] = None):
        """Initialize this instance with an optional filepath, from which we will
        initialize our data. The path is also used to write changes back using
        the write() method"""
        self._path = filepath
        if filepath is not None:
            self._read_from_file()
        # END handle filepath

    def _read_from_file(self) -> None:
        try:
            fmap = file_contents_ro_filepath(self._path, stream=True, allow_mmap=True)
        except OSError:
            # it is possible and allowed that the file doesn't exist !
            return
        # END handle invalid log

        try:
            self._deserialize(fmap)
        finally:
            fmap.close()
        # END handle closing of handle

    # { Interface

    @classmethod
    def from_file(cls, filepath: PathLike) -> "RefLog":
        """
        :return: a new RefLog instance containing all entries from the reflog
            at the given filepath
        :param filepath: path to reflog
        :raise ValueError: If the file could not be read or was corrupted in some way"""
        return cls(filepath)

    @classmethod
    def path(cls, ref: "SymbolicReference") -> str:
        """
        :return: string to absolute path at which the reflog of the given ref
            instance would be found. The path is not guaranteed to point to a valid
            file though.
        :param ref: SymbolicReference instance"""
        return osp.join(ref.repo.git_dir, "logs", to_native_path(ref.path))

    @classmethod
    def iter_entries(cls, stream: Union[str, "BytesIO", mmap]) -> Iterator[RefLogEntry]:
        """
        :return: Iterator yielding RefLogEntry instances, one for each line read
            sfrom the given stream.
        :param stream: file-like object containing the revlog in its native format
            or string instance pointing to a file to read"""
        new_entry = RefLogEntry.from_line
        if isinstance(stream, str):
            # default args return mmap on py>3
            _stream = file_contents_ro_filepath(stream)
            assert isinstance(_stream, mmap)
        else:
            _stream = stream
        # END handle stream type
        while True:
            line = _stream.readline()
            if not line:
                return
            yield new_entry(line.strip())
        # END endless loop

    @classmethod
    def entry_at(cls, filepath: PathLike, index: int) -> "RefLogEntry":
        """
        :return: RefLogEntry at the given index

        :param filepath: full path to the index file from which to read the entry

        :param index: python list compatible index, i.e. it may be negative to
            specify an entry counted from the end of the list

        :raise IndexError: If the entry didn't exist

        .. note:: This method is faster as it only parses the entry at index, skipping
            all other lines. Nonetheless, the whole file has to be read if
            the index is negative
        """
        with open(filepath, "rb") as fp:
            if index < 0:
                return RefLogEntry.from_line(fp.readlines()[index].strip())
            # read until index is reached

            for i in range(index + 1):
                line = fp.readline()
                if not line:
                    raise IndexError(f"Index file ended at line {i+1}, before given index was reached")
                # END abort on eof
            # END handle runup

            return RefLogEntry.from_line(line.strip())
        # END handle index

    def to_file(self, filepath: PathLike) -> None:
        """Write the contents of the reflog instance to a file at the given filepath.

        :param filepath: path to file, parent directories are assumed to exist"""
        lfd = LockedFD(filepath)
        assure_directory_exists(filepath, is_file=True)

        fp = lfd.open(write=True, stream=True)
        try:
            self._serialize(fp)
            lfd.commit()
        except Exception:
            # on failure it rolls back automatically, but we make it clear
            lfd.rollback()
            raise
        # END handle change

    @classmethod
    def append_entry(
        cls,
        config_reader: Union[Actor, "GitConfigParser", "SectionConstraint", None],
        filepath: PathLike,
        oldbinsha: bytes,
        newbinsha: bytes,
        message: str,
        write: bool = True,
    ) -> "RefLogEntry":
        """Append a new log entry to the revlog at filepath.

        :param config_reader: configuration reader of the repository - used to obtain
            user information. May also be an Actor instance identifying the committer directly or None.
        :param filepath: full path to the log file
        :param oldbinsha: binary sha of the previous commit
        :param newbinsha: binary sha of the current commit
        :param message: message describing the change to the reference
        :param write: If True, the changes will be written right away. Otherwise
            the change will not be written

        :return: RefLogEntry objects which was appended to the log

        :note: As we are append-only, concurrent access is not a problem as we
            do not interfere with readers."""

        if len(oldbinsha) != 20 or len(newbinsha) != 20:
            raise ValueError("Shas need to be given in binary format")
        # END handle sha type
        assure_directory_exists(filepath, is_file=True)
        first_line = message.split("\n")[0]
        if isinstance(config_reader, Actor):
            committer = config_reader  # mypy thinks this is Actor | Gitconfigparser, but why?
        else:
            committer = Actor.committer(config_reader)
        entry = RefLogEntry(
            (
                bin_to_hex(oldbinsha).decode("ascii"),
                bin_to_hex(newbinsha).decode("ascii"),
                committer,
                (int(_time.time()), _time.altzone),
                first_line,
            )
        )

        if write:
            lf = LockFile(filepath)
            lf._obtain_lock_or_raise()
            fd = open(filepath, "ab")
            try:
                fd.write(entry.format().encode(defenc))
            finally:
                fd.close()
                lf._release_lock()
            # END handle write operation
        return entry

    def write(self) -> "RefLog":
        """Write this instance's data to the file we are originating from

        :return: self"""
        if self._path is None:
            raise ValueError("Instance was not initialized with a path, use to_file(...) instead")
        # END assert path
        self.to_file(self._path)
        return self

    # } END interface

    # { Serializable Interface
    def _serialize(self, stream: "BytesIO") -> "RefLog":
        write = stream.write

        # write all entries
        for e in self:
            write(e.format().encode(defenc))
        # END for each entry
        return self

    def _deserialize(self, stream: "BytesIO") -> "RefLog":
        self.extend(self.iter_entries(stream))
        # } END serializable interface
        return self
