# pack.py -- For dealing with packed git objects.
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
# Copyright (C) 2008-2013 Jelmer Vernooij <jelmer@jelmer.uk>
#
# Dulwich is dual-licensed under the Apache License, Version 2.0 and the GNU
# General Public License as public by the Free Software Foundation; version 2.0
# or (at your option) any later version. You can redistribute it and/or
# modify it under the terms of either of these two licenses.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# You should have received a copy of the licenses; if not, see
# <http://www.gnu.org/licenses/> for a copy of the GNU General Public License
# and <http://www.apache.org/licenses/LICENSE-2.0> for a copy of the Apache
# License, Version 2.0.
#

"""Classes for dealing with packed git objects.

A pack is a compact representation of a bunch of objects, stored
using deltas where possible.

They have two parts, the pack file, which stores the data, and an index
that tells you where the data is.

To find an object you look in all of the index files 'til you find a
match for the object name. You then use the pointer got from this as
a pointer in to the corresponding packfile.
"""

import binascii
from collections import defaultdict, deque
from contextlib import suppress
from io import BytesIO, UnsupportedOperation

try:
    from cdifflib import CSequenceMatcher as SequenceMatcher
except ModuleNotFoundError:
    from difflib import SequenceMatcher

import os
import struct
import sys
from itertools import chain
from typing import (BinaryIO, Callable, Deque, Dict, Generic, Iterable,
                    Iterator, List, Optional, Sequence, Set, Tuple, TypeVar,
                    Union)

try:
    from typing import Protocol
except ImportError:  # python << 3.8
    from typing_extensions import Protocol   # type: ignore

import warnings
import zlib
from hashlib import sha1
from os import SEEK_CUR, SEEK_END
from struct import unpack_from

try:
    import mmap
except ImportError:
    has_mmap = False
else:
    has_mmap = True

# For some reason the above try, except fails to set has_mmap = False for plan9
if sys.platform == "Plan9":
    has_mmap = False

from .errors import ApplyDeltaError, ChecksumMismatch
from .file import GitFile
from .lru_cache import LRUSizeCache
from .objects import ObjectID, ShaFile, hex_to_sha, object_header, sha_to_hex

OFS_DELTA = 6
REF_DELTA = 7

DELTA_TYPES = (OFS_DELTA, REF_DELTA)


DEFAULT_PACK_DELTA_WINDOW_SIZE = 10

# Keep pack files under 16Mb in memory, otherwise write them out to disk
PACK_SPOOL_FILE_MAX_SIZE = 16 * 1024 * 1024


OldUnpackedObject = Union[Tuple[Union[bytes, int], List[bytes]], List[bytes]]
ResolveExtRefFn = Callable[[bytes], Tuple[int, OldUnpackedObject]]
ProgressFn = Callable[[int, str], None]
PackHint = Tuple[int, Optional[bytes]]


class ObjectContainer(Protocol):

    def add_object(self, obj: ShaFile) -> None:
        """Add a single object to this object store."""

    def add_objects(
            self, objects: Sequence[Tuple[ShaFile, Optional[str]]],
            progress: Optional[Callable[[str], None]] = None) -> None:
        """Add a set of objects to this object store.

        Args:
          objects: Iterable over a list of (object, path) tuples
        """

    def __contains__(self, sha1: bytes) -> bool:
        """Check if a hex sha is present."""

    def __getitem__(self, sha1: bytes) -> ShaFile:
        """Retrieve an object."""


class PackedObjectContainer(ObjectContainer):

    def get_unpacked_object(self, sha1: bytes, *, include_comp: bool = False) -> "UnpackedObject":
        """Get a raw unresolved object."""
        raise NotImplementedError(self.get_unpacked_object)

    def iterobjects_subset(self, shas: Iterable[bytes], *, allow_missing: bool = False) -> Iterator[ShaFile]:
        raise NotImplementedError(self.iterobjects_subset)

    def iter_unpacked_subset(
            self, shas: Set[bytes], include_comp: bool = False, allow_missing: bool = False,
            convert_ofs_delta: bool = True) -> Iterator["UnpackedObject"]:
        raise NotImplementedError(self.iter_unpacked_subset)


class UnpackedObjectStream:

    def __iter__(self) -> Iterator["UnpackedObject"]:
        raise NotImplementedError(self.__iter__)

    def __len__(self) -> int:
        raise NotImplementedError(self.__len__)


def take_msb_bytes(read: Callable[[int], bytes], crc32: Optional[int] = None) -> Tuple[List[int], Optional[int]]:
    """Read bytes marked with most significant bit.

    Args:
      read: Read function
    """
    ret: List[int] = []
    while len(ret) == 0 or ret[-1] & 0x80:
        b = read(1)
        if crc32 is not None:
            crc32 = binascii.crc32(b, crc32)
        ret.append(ord(b[:1]))
    return ret, crc32


class PackFileDisappeared(Exception):
    def __init__(self, obj):
        self.obj = obj


class UnpackedObject:
    """Class encapsulating an object unpacked from a pack file.

    These objects should only be created from within unpack_object. Most
    members start out as empty and are filled in at various points by
    read_zlib_chunks, unpack_object, DeltaChainIterator, etc.

    End users of this object should take care that the function they're getting
    this object from is guaranteed to set the members they need.
    """

    __slots__ = [
        "offset",  # Offset in its pack.
        "_sha",  # Cached binary SHA.
        "obj_type_num",  # Type of this object.
        "obj_chunks",  # Decompressed and delta-resolved chunks.
        "pack_type_num",  # Type of this object in the pack (may be a delta).
        "delta_base",  # Delta base offset or SHA.
        "comp_chunks",  # Compressed object chunks.
        "decomp_chunks",  # Decompressed object chunks.
        "decomp_len",  # Decompressed length of this object.
        "crc32",  # CRC32.
    ]

    obj_type_num: Optional[int]
    obj_chunks: Optional[List[bytes]]
    delta_base: Union[None, bytes, int]
    decomp_chunks: List[bytes]

    # TODO(dborowitz): read_zlib_chunks and unpack_object could very well be
    # methods of this object.
    def __init__(self, pack_type_num, *, delta_base=None, decomp_len=None, crc32=None, sha=None, decomp_chunks=None, offset=None):
        self.offset = offset
        self._sha = sha
        self.pack_type_num = pack_type_num
        self.delta_base = delta_base
        self.comp_chunks = None
        self.decomp_chunks: List[bytes] = decomp_chunks or []
        if decomp_chunks is not None and decomp_len is None:
            self.decomp_len = sum(map(len, decomp_chunks))
        else:
            self.decomp_len = decomp_len
        self.crc32 = crc32

        if pack_type_num in DELTA_TYPES:
            self.obj_type_num = None
            self.obj_chunks = None
        else:
            self.obj_type_num = pack_type_num
            self.obj_chunks = self.decomp_chunks
            self.delta_base = delta_base

    def sha(self):
        """Return the binary SHA of this object."""
        if self._sha is None:
            self._sha = obj_sha(self.obj_type_num, self.obj_chunks)
        return self._sha

    def sha_file(self):
        """Return a ShaFile from this object."""
        assert self.obj_type_num is not None and self.obj_chunks is not None
        return ShaFile.from_raw_chunks(self.obj_type_num, self.obj_chunks)

    # Only provided for backwards compatibility with code that expects either
    # chunks or a delta tuple.
    def _obj(self) -> OldUnpackedObject:
        """Return the decompressed chunks, or (delta base, delta chunks)."""
        if self.pack_type_num in DELTA_TYPES:
            assert isinstance(self.delta_base, (bytes, int))
            return (self.delta_base, self.decomp_chunks)
        else:
            return self.decomp_chunks

    def __eq__(self, other):
        if not isinstance(other, UnpackedObject):
            return False
        for slot in self.__slots__:
            if getattr(self, slot) != getattr(other, slot):
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        data = ["{}={!r}".format(s, getattr(self, s)) for s in self.__slots__]
        return "{}({})".format(self.__class__.__name__, ", ".join(data))


_ZLIB_BUFSIZE = 4096


def read_zlib_chunks(
        read_some: Callable[[int], bytes],
        unpacked: UnpackedObject, include_comp: bool = False,
        buffer_size: int = _ZLIB_BUFSIZE
) -> bytes:
    """Read zlib data from a buffer.

    This function requires that the buffer have additional data following the
    compressed data, which is guaranteed to be the case for git pack files.

    Args:
      read_some: Read function that returns at least one byte, but may
        return less than the requested size.
      unpacked: An UnpackedObject to write result data to. If its crc32
        attr is not None, the CRC32 of the compressed bytes will be computed
        using this starting CRC32.
        After this function, will have the following attrs set:
        * comp_chunks    (if include_comp is True)
        * decomp_chunks
        * decomp_len
        * crc32
      include_comp: If True, include compressed data in the result.
      buffer_size: Size of the read buffer.
    Returns: Leftover unused data from the decompression.
    Raises:
      zlib.error: if a decompression error occurred.
    """
    if unpacked.decomp_len <= -1:
        raise ValueError("non-negative zlib data stream size expected")
    decomp_obj = zlib.decompressobj()

    comp_chunks = []
    decomp_chunks = unpacked.decomp_chunks
    decomp_len = 0
    crc32 = unpacked.crc32

    while True:
        add = read_some(buffer_size)
        if not add:
            raise zlib.error("EOF before end of zlib stream")
        comp_chunks.append(add)
        decomp = decomp_obj.decompress(add)
        decomp_len += len(decomp)
        decomp_chunks.append(decomp)
        unused = decomp_obj.unused_data
        if unused:
            left = len(unused)
            if crc32 is not None:
                crc32 = binascii.crc32(add[:-left], crc32)
            if include_comp:
                comp_chunks[-1] = add[:-left]
            break
        elif crc32 is not None:
            crc32 = binascii.crc32(add, crc32)
    if crc32 is not None:
        crc32 &= 0xFFFFFFFF

    if decomp_len != unpacked.decomp_len:
        raise zlib.error("decompressed data does not match expected size")

    unpacked.crc32 = crc32
    if include_comp:
        unpacked.comp_chunks = comp_chunks
    return unused


def iter_sha1(iter):
    """Return the hexdigest of the SHA1 over a set of names.

    Args:
      iter: Iterator over string objects
    Returns: 40-byte hex sha1 digest
    """
    sha = sha1()
    for name in iter:
        sha.update(name)
    return sha.hexdigest().encode("ascii")


def load_pack_index(path):
    """Load an index file by path.

    Args:
      path: Path to the index file
    Returns: A PackIndex loaded from the given path
    """
    with GitFile(path, "rb") as f:
        return load_pack_index_file(path, f)


def _load_file_contents(f, size=None):
    try:
        fd = f.fileno()
    except (UnsupportedOperation, AttributeError):
        fd = None
    # Attempt to use mmap if possible
    if fd is not None:
        if size is None:
            size = os.fstat(fd).st_size
        if has_mmap:
            try:
                contents = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
            except OSError:
                # Perhaps a socket?
                pass
            else:
                return contents, size
    contents = f.read()
    size = len(contents)
    return contents, size


def load_pack_index_file(path, f):
    """Load an index file from a file-like object.

    Args:
      path: Path for the index file
      f: File-like object
    Returns: A PackIndex loaded from the given file
    """
    contents, size = _load_file_contents(f)
    if contents[:4] == b"\377tOc":
        version = struct.unpack(b">L", contents[4:8])[0]
        if version == 2:
            return PackIndex2(path, file=f, contents=contents, size=size)
        else:
            raise KeyError("Unknown pack index format %d" % version)
    else:
        return PackIndex1(path, file=f, contents=contents, size=size)


def bisect_find_sha(start, end, sha, unpack_name):
    """Find a SHA in a data blob with sorted SHAs.

    Args:
      start: Start index of range to search
      end: End index of range to search
      sha: Sha to find
      unpack_name: Callback to retrieve SHA by index
    Returns: Index of the SHA, or None if it wasn't found
    """
    assert start <= end
    while start <= end:
        i = (start + end) // 2
        file_sha = unpack_name(i)
        if file_sha < sha:
            start = i + 1
        elif file_sha > sha:
            end = i - 1
        else:
            return i
    return None


PackIndexEntry = Tuple[bytes, int, Optional[int]]


class PackIndex:
    """An index in to a packfile.

    Given a sha id of an object a pack index can tell you the location in the
    packfile of that object if it has it.
    """

    def __eq__(self, other):
        if not isinstance(other, PackIndex):
            return False

        for (name1, _, _), (name2, _, _) in zip(
            self.iterentries(), other.iterentries()
        ):
            if name1 != name2:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self) -> int:
        """Return the number of entries in this pack index."""
        raise NotImplementedError(self.__len__)

    def __iter__(self) -> Iterator[bytes]:
        """Iterate over the SHAs in this pack."""
        return map(sha_to_hex, self._itersha())

    def iterentries(self) -> Iterator[PackIndexEntry]:
        """Iterate over the entries in this pack index.

        Returns: iterator over tuples with object name, offset in packfile and
            crc32 checksum.
        """
        raise NotImplementedError(self.iterentries)

    def get_pack_checksum(self) -> bytes:
        """Return the SHA1 checksum stored for the corresponding packfile.

        Returns: 20-byte binary digest
        """
        raise NotImplementedError(self.get_pack_checksum)

    def object_index(self, sha: bytes) -> int:
        warnings.warn('Please use object_offset instead', DeprecationWarning, stacklevel=2)
        return self.object_offset(sha)

    def object_offset(self, sha: bytes) -> int:
        """Return the offset in to the corresponding packfile for the object.

        Given the name of an object it will return the offset that object
        lives at within the corresponding pack file. If the pack file doesn't
        have the object then None will be returned.
        """
        raise NotImplementedError(self.object_offset)

    def object_sha1(self, index: int) -> bytes:
        """Return the SHA1 corresponding to the index in the pack file."""
        for (name, offset, crc32) in self.iterentries():
            if offset == index:
                return name
        else:
            raise KeyError(index)

    def _object_offset(self, sha: bytes) -> int:
        """See object_offset.

        Args:
          sha: A *binary* SHA string. (20 characters long)_
        """
        raise NotImplementedError(self._object_offset)

    def objects_sha1(self) -> bytes:
        """Return the hex SHA1 over all the shas of all objects in this pack.

        Note: This is used for the filename of the pack.
        """
        return iter_sha1(self._itersha())

    def _itersha(self) -> Iterator[bytes]:
        """Yield all the SHA1's of the objects in the index, sorted."""
        raise NotImplementedError(self._itersha)

    def close(self):
        pass

    def check(self) -> None:
        pass


class MemoryPackIndex(PackIndex):
    """Pack index that is stored entirely in memory."""

    def __init__(self, entries, pack_checksum=None):
        """Create a new MemoryPackIndex.

        Args:
          entries: Sequence of name, idx, crc32 (sorted)
          pack_checksum: Optional pack checksum
        """
        self._by_sha = {}
        self._by_offset = {}
        for name, offset, crc32 in entries:
            self._by_sha[name] = offset
            self._by_offset[offset] = name
        self._entries = entries
        self._pack_checksum = pack_checksum

    def get_pack_checksum(self):
        return self._pack_checksum

    def __len__(self):
        return len(self._entries)

    def object_offset(self, sha):
        if len(sha) == 40:
            sha = hex_to_sha(sha)
        return self._by_sha[sha]

    def object_sha1(self, offset):
        return self._by_offset[offset]

    def _itersha(self):
        return iter(self._by_sha)

    def iterentries(self):
        return iter(self._entries)

    @classmethod
    def for_pack(cls, pack):
        return MemoryPackIndex(pack.sorted_entries(), pack.calculate_checksum())

    @classmethod
    def clone(cls, other_index):
        return cls(other_index.iterentries(), other_index.get_pack_checksum())


class FilePackIndex(PackIndex):
    """Pack index that is based on a file.

    To do the loop it opens the file, and indexes first 256 4 byte groups
    with the first byte of the sha id. The value in the four byte group indexed
    is the end of the group that shares the same starting byte. Subtract one
    from the starting byte and index again to find the start of the group.
    The values are sorted by sha id within the group, so do the math to find
    the start and end offset and then bisect in to find if the value is
    present.
    """

    _fan_out_table: List[int]

    def __init__(self, filename, file=None, contents=None, size=None):
        """Create a pack index object.

        Provide it with the name of the index file to consider, and it will map
        it whenever required.
        """
        self._filename = filename
        # Take the size now, so it can be checked each time we map the file to
        # ensure that it hasn't changed.
        if file is None:
            self._file = GitFile(filename, "rb")
        else:
            self._file = file
        if contents is None:
            self._contents, self._size = _load_file_contents(self._file, size)
        else:
            self._contents, self._size = (contents, size)

    @property
    def path(self) -> str:
        return self._filename

    def __eq__(self, other):
        # Quick optimization:
        if (
            isinstance(other, FilePackIndex)
            and self._fan_out_table != other._fan_out_table
        ):
            return False

        return super().__eq__(other)

    def close(self) -> None:
        self._file.close()
        if getattr(self._contents, "close", None) is not None:
            self._contents.close()

    def __len__(self) -> int:
        """Return the number of entries in this pack index."""
        return self._fan_out_table[-1]

    def _unpack_entry(self, i: int) -> PackIndexEntry:
        """Unpack the i-th entry in the index file.

        Returns: Tuple with object name (SHA), offset in pack file and CRC32
            checksum (if known).
        """
        raise NotImplementedError(self._unpack_entry)

    def _unpack_name(self, i):
        """Unpack the i-th name from the index file."""
        raise NotImplementedError(self._unpack_name)

    def _unpack_offset(self, i):
        """Unpack the i-th object offset from the index file."""
        raise NotImplementedError(self._unpack_offset)

    def _unpack_crc32_checksum(self, i):
        """Unpack the crc32 checksum for the ith object from the index file."""
        raise NotImplementedError(self._unpack_crc32_checksum)

    def _itersha(self) -> Iterator[bytes]:
        for i in range(len(self)):
            yield self._unpack_name(i)

    def iterentries(self) -> Iterator[PackIndexEntry]:
        """Iterate over the entries in this pack index.

        Returns: iterator over tuples with object name, offset in packfile and
            crc32 checksum.
        """
        for i in range(len(self)):
            yield self._unpack_entry(i)

    def _read_fan_out_table(self, start_offset: int):
        ret = []
        for i in range(0x100):
            fanout_entry = self._contents[
                start_offset + i * 4 : start_offset + (i + 1) * 4
            ]
            ret.append(struct.unpack(">L", fanout_entry)[0])
        return ret

    def check(self) -> None:
        """Check that the stored checksum matches the actual checksum."""
        actual = self.calculate_checksum()
        stored = self.get_stored_checksum()
        if actual != stored:
            raise ChecksumMismatch(stored, actual)

    def calculate_checksum(self) -> bytes:
        """Calculate the SHA1 checksum over this pack index.

        Returns: This is a 20-byte binary digest
        """
        return sha1(self._contents[:-20]).digest()

    def get_pack_checksum(self) -> bytes:
        """Return the SHA1 checksum stored for the corresponding packfile.

        Returns: 20-byte binary digest
        """
        return bytes(self._contents[-40:-20])

    def get_stored_checksum(self) -> bytes:
        """Return the SHA1 checksum stored for this index.

        Returns: 20-byte binary digest
        """
        return bytes(self._contents[-20:])

    def object_offset(self, sha: bytes) -> int:
        """Return the offset in to the corresponding packfile for the object.

        Given the name of an object it will return the offset that object
        lives at within the corresponding pack file. If the pack file doesn't
        have the object then None will be returned.
        """
        if len(sha) == 40:
            sha = hex_to_sha(sha)
        try:
            return self._object_offset(sha)
        except ValueError as exc:
            closed = getattr(self._contents, "closed", None)
            if closed in (None, True):
                raise PackFileDisappeared(self) from exc
            raise

    def _object_offset(self, sha: bytes) -> int:
        """See object_offset.

        Args:
          sha: A *binary* SHA string. (20 characters long)_
        """
        assert len(sha) == 20
        idx = ord(sha[:1])
        if idx == 0:
            start = 0
        else:
            start = self._fan_out_table[idx - 1]
        end = self._fan_out_table[idx]
        i = bisect_find_sha(start, end, sha, self._unpack_name)
        if i is None:
            raise KeyError(sha)
        return self._unpack_offset(i)


class PackIndex1(FilePackIndex):
    """Version 1 Pack Index file."""

    def __init__(self, filename: str, file=None, contents=None, size=None):
        super().__init__(filename, file, contents, size)
        self.version = 1
        self._fan_out_table = self._read_fan_out_table(0)

    def _unpack_entry(self, i):
        (offset, name) = unpack_from(">L20s", self._contents, (0x100 * 4) + (i * 24))
        return (name, offset, None)

    def _unpack_name(self, i):
        offset = (0x100 * 4) + (i * 24) + 4
        return self._contents[offset : offset + 20]

    def _unpack_offset(self, i):
        offset = (0x100 * 4) + (i * 24)
        return unpack_from(">L", self._contents, offset)[0]

    def _unpack_crc32_checksum(self, i):
        # Not stored in v1 index files
        return None


class PackIndex2(FilePackIndex):
    """Version 2 Pack Index file."""

    def __init__(self, filename: str, file=None, contents=None, size=None):
        super().__init__(filename, file, contents, size)
        if self._contents[:4] != b"\377tOc":
            raise AssertionError("Not a v2 pack index file")
        (self.version,) = unpack_from(b">L", self._contents, 4)
        if self.version != 2:
            raise AssertionError("Version was %d" % self.version)
        self._fan_out_table = self._read_fan_out_table(8)
        self._name_table_offset = 8 + 0x100 * 4
        self._crc32_table_offset = self._name_table_offset + 20 * len(self)
        self._pack_offset_table_offset = self._crc32_table_offset + 4 * len(self)
        self._pack_offset_largetable_offset = self._pack_offset_table_offset + 4 * len(
            self
        )

    def _unpack_entry(self, i):
        return (
            self._unpack_name(i),
            self._unpack_offset(i),
            self._unpack_crc32_checksum(i),
        )

    def _unpack_name(self, i):
        offset = self._name_table_offset + i * 20
        return self._contents[offset : offset + 20]

    def _unpack_offset(self, i):
        offset = self._pack_offset_table_offset + i * 4
        offset = unpack_from(">L", self._contents, offset)[0]
        if offset & (2 ** 31):
            offset = self._pack_offset_largetable_offset + (offset & (2 ** 31 - 1)) * 8
            offset = unpack_from(">Q", self._contents, offset)[0]
        return offset

    def _unpack_crc32_checksum(self, i):
        return unpack_from(">L", self._contents, self._crc32_table_offset + i * 4)[0]


def read_pack_header(read) -> Tuple[int, int]:
    """Read the header of a pack file.

    Args:
      read: Read function
    Returns: Tuple of (pack version, number of objects). If no data is
        available to read, returns (None, None).
    """
    header = read(12)
    if not header:
        raise AssertionError("file too short to contain pack")
    if header[:4] != b"PACK":
        raise AssertionError("Invalid pack header %r" % header)
    (version,) = unpack_from(b">L", header, 4)
    if version not in (2, 3):
        raise AssertionError("Version was %d" % version)
    (num_objects,) = unpack_from(b">L", header, 8)
    return (version, num_objects)


def chunks_length(chunks: Union[bytes, Iterable[bytes]]) -> int:
    if isinstance(chunks, bytes):
        return len(chunks)
    else:
        return sum(map(len, chunks))


def unpack_object(
    read_all: Callable[[int], bytes],
    read_some: Optional[Callable[[int], bytes]] = None,
    compute_crc32=False,
    include_comp=False,
    zlib_bufsize=_ZLIB_BUFSIZE,
) -> Tuple[UnpackedObject, bytes]:
    """Unpack a Git object.

    Args:
      read_all: Read function that blocks until the number of requested
        bytes are read.
      read_some: Read function that returns at least one byte, but may not
        return the number of bytes requested.
      compute_crc32: If True, compute the CRC32 of the compressed data. If
        False, the returned CRC32 will be None.
      include_comp: If True, include compressed data in the result.
      zlib_bufsize: An optional buffer size for zlib operations.
    Returns: A tuple of (unpacked, unused), where unused is the unused data
        leftover from decompression, and unpacked in an UnpackedObject with
        the following attrs set:

        * obj_chunks     (for non-delta types)
        * pack_type_num
        * delta_base     (for delta types)
        * comp_chunks    (if include_comp is True)
        * decomp_chunks
        * decomp_len
        * crc32          (if compute_crc32 is True)
    """
    if read_some is None:
        read_some = read_all
    if compute_crc32:
        crc32 = 0
    else:
        crc32 = None

    raw, crc32 = take_msb_bytes(read_all, crc32=crc32)
    type_num = (raw[0] >> 4) & 0x07
    size = raw[0] & 0x0F
    for i, byte in enumerate(raw[1:]):
        size += (byte & 0x7F) << ((i * 7) + 4)

    delta_base: Union[int, bytes, None]
    raw_base = len(raw)
    if type_num == OFS_DELTA:
        raw, crc32 = take_msb_bytes(read_all, crc32=crc32)
        raw_base += len(raw)
        if raw[-1] & 0x80:
            raise AssertionError
        delta_base_offset = raw[0] & 0x7F
        for byte in raw[1:]:
            delta_base_offset += 1
            delta_base_offset <<= 7
            delta_base_offset += byte & 0x7F
        delta_base = delta_base_offset
    elif type_num == REF_DELTA:
        delta_base_obj = read_all(20)
        if crc32 is not None:
            crc32 = binascii.crc32(delta_base_obj, crc32)
        delta_base = delta_base_obj
        raw_base += 20
    else:
        delta_base = None

    unpacked = UnpackedObject(type_num, delta_base=delta_base, decomp_len=size, crc32=crc32)
    unused = read_zlib_chunks(
        read_some,
        unpacked,
        buffer_size=zlib_bufsize,
        include_comp=include_comp,
    )
    return unpacked, unused


def _compute_object_size(value):
    """Compute the size of a unresolved object for use with LRUSizeCache."""
    (num, obj) = value
    if num in DELTA_TYPES:
        return chunks_length(obj[1])
    return chunks_length(obj)


class PackStreamReader:
    """Class to read a pack stream.

    The pack is read from a ReceivableProtocol using read() or recv() as
    appropriate.
    """

    def __init__(self, read_all, read_some=None, zlib_bufsize=_ZLIB_BUFSIZE) -> None:
        self.read_all = read_all
        if read_some is None:
            self.read_some = read_all
        else:
            self.read_some = read_some
        self.sha = sha1()
        self._offset = 0
        self._rbuf = BytesIO()
        # trailer is a deque to avoid memory allocation on small reads
        self._trailer: Deque[bytes] = deque()
        self._zlib_bufsize = zlib_bufsize

    def _read(self, read, size):
        """Read up to size bytes using the given callback.

        As a side effect, update the verifier's hash (excluding the last 20
        bytes read).

        Args:
          read: The read callback to read from.
          size: The maximum number of bytes to read; the particular
            behavior is callback-specific.
        """
        data = read(size)

        # maintain a trailer of the last 20 bytes we've read
        n = len(data)
        self._offset += n
        tn = len(self._trailer)
        if n >= 20:
            to_pop = tn
            to_add = 20
        else:
            to_pop = max(n + tn - 20, 0)
            to_add = n
        self.sha.update(
            bytes(bytearray([self._trailer.popleft() for _ in range(to_pop)]))
        )
        self._trailer.extend(data[-to_add:])

        # hash everything but the trailer
        self.sha.update(data[:-to_add])
        return data

    def _buf_len(self):
        buf = self._rbuf
        start = buf.tell()
        buf.seek(0, SEEK_END)
        end = buf.tell()
        buf.seek(start)
        return end - start

    @property
    def offset(self):
        return self._offset - self._buf_len()

    def read(self, size):
        """Read, blocking until size bytes are read."""
        buf_len = self._buf_len()
        if buf_len >= size:
            return self._rbuf.read(size)
        buf_data = self._rbuf.read()
        self._rbuf = BytesIO()
        return buf_data + self._read(self.read_all, size - buf_len)

    def recv(self, size):
        """Read up to size bytes, blocking until one byte is read."""
        buf_len = self._buf_len()
        if buf_len:
            data = self._rbuf.read(size)
            if size >= buf_len:
                self._rbuf = BytesIO()
            return data
        return self._read(self.read_some, size)

    def __len__(self):
        return self._num_objects

    def read_objects(self, compute_crc32=False) -> Iterator[UnpackedObject]:
        """Read the objects in this pack file.

        Args:
          compute_crc32: If True, compute the CRC32 of the compressed
            data. If False, the returned CRC32 will be None.
        Returns: Iterator over UnpackedObjects with the following members set:
            offset
            obj_type_num
            obj_chunks (for non-delta types)
            delta_base (for delta types)
            decomp_chunks
            decomp_len
            crc32 (if compute_crc32 is True)
        Raises:
          ChecksumMismatch: if the checksum of the pack contents does not
            match the checksum in the pack trailer.
          zlib.error: if an error occurred during zlib decompression.
          IOError: if an error occurred writing to the output file.
        """
        pack_version, self._num_objects = read_pack_header(self.read)

        for i in range(self._num_objects):
            offset = self.offset
            unpacked, unused = unpack_object(
                self.read,
                read_some=self.recv,
                compute_crc32=compute_crc32,
                zlib_bufsize=self._zlib_bufsize,
            )
            unpacked.offset = offset

            # prepend any unused data to current read buffer
            buf = BytesIO()
            buf.write(unused)
            buf.write(self._rbuf.read())
            buf.seek(0)
            self._rbuf = buf

            yield unpacked

        if self._buf_len() < 20:
            # If the read buffer is full, then the last read() got the whole
            # trailer off the wire. If not, it means there is still some of the
            # trailer to read. We need to read() all 20 bytes; N come from the
            # read buffer and (20 - N) come from the wire.
            self.read(20)

        pack_sha = bytearray(self._trailer)  # type: ignore
        if pack_sha != self.sha.digest():
            raise ChecksumMismatch(sha_to_hex(pack_sha), self.sha.hexdigest())


class PackStreamCopier(PackStreamReader):
    """Class to verify a pack stream as it is being read.

    The pack is read from a ReceivableProtocol using read() or recv() as
    appropriate and written out to the given file-like object.
    """

    def __init__(self, read_all, read_some, outfile, delta_iter=None):
        """Initialize the copier.

        Args:
          read_all: Read function that blocks until the number of
            requested bytes are read.
          read_some: Read function that returns at least one byte, but may
            not return the number of bytes requested.
          outfile: File-like object to write output through.
          delta_iter: Optional DeltaChainIterator to record deltas as we
            read them.
        """
        super().__init__(read_all, read_some=read_some)
        self.outfile = outfile
        self._delta_iter = delta_iter

    def _read(self, read, size):
        """Read data from the read callback and write it to the file."""
        data = super()._read(read, size)
        self.outfile.write(data)
        return data

    def verify(self, progress=None):
        """Verify a pack stream and write it to the output file.

        See PackStreamReader.iterobjects for a list of exceptions this may
        throw.
        """
        i = 0  # default count of entries if read_objects() is empty
        for i, unpacked in enumerate(self.read_objects()):
            if self._delta_iter:
                self._delta_iter.record(unpacked)
            if progress is not None:
                progress(("copying pack entries: %d/%d\r" % (i, len(self))).encode('ascii'))
        if progress is not None:
            progress(("copied %d pack entries\n" % i).encode('ascii'))


def obj_sha(type, chunks):
    """Compute the SHA for a numeric type and object chunks."""
    sha = sha1()
    sha.update(object_header(type, chunks_length(chunks)))
    if isinstance(chunks, bytes):
        sha.update(chunks)
    else:
        for chunk in chunks:
            sha.update(chunk)
    return sha.digest()


def compute_file_sha(f, start_ofs=0, end_ofs=0, buffer_size=1 << 16):
    """Hash a portion of a file into a new SHA.

    Args:
      f: A file-like object to read from that supports seek().
      start_ofs: The offset in the file to start reading at.
      end_ofs: The offset in the file to end reading at, relative to the
        end of the file.
      buffer_size: A buffer size for reading.
    Returns: A new SHA object updated with data read from the file.
    """
    sha = sha1()
    f.seek(0, SEEK_END)
    length = f.tell()
    if (end_ofs < 0 and length + end_ofs < start_ofs) or end_ofs > length:
        raise AssertionError(
            "Attempt to read beyond file length. "
            "start_ofs: %d, end_ofs: %d, file length: %d" % (start_ofs, end_ofs, length)
        )
    todo = length + end_ofs - start_ofs
    f.seek(start_ofs)
    while todo:
        data = f.read(min(todo, buffer_size))
        sha.update(data)
        todo -= len(data)
    return sha


class PackData:
    """The data contained in a packfile.

    Pack files can be accessed both sequentially for exploding a pack, and
    directly with the help of an index to retrieve a specific object.

    The objects within are either complete or a delta against another.

    The header is variable length. If the MSB of each byte is set then it
    indicates that the subsequent byte is still part of the header.
    For the first byte the next MS bits are the type, which tells you the type
    of object, and whether it is a delta. The LS byte is the lowest bits of the
    size. For each subsequent byte the LS 7 bits are the next MS bits of the
    size, i.e. the last byte of the header contains the MS bits of the size.

    For the complete objects the data is stored as zlib deflated data.
    The size in the header is the uncompressed object size, so to uncompress
    you need to just keep feeding data to zlib until you get an object back,
    or it errors on bad data. This is done here by just giving the complete
    buffer from the start of the deflated object on. This is bad, but until I
    get mmap sorted out it will have to do.

    Currently there are no integrity checks done. Also no attempt is made to
    try and detect the delta case, or a request for an object at the wrong
    position.  It will all just throw a zlib or KeyError.
    """

    def __init__(self, filename, file=None, size=None):
        """Create a PackData object representing the pack in the given filename.

        The file must exist and stay readable until the object is disposed of.
        It must also stay the same size. It will be mapped whenever needed.

        Currently there is a restriction on the size of the pack as the python
        mmap implementation is flawed.
        """
        self._filename = filename
        self._size = size
        self._header_size = 12
        if file is None:
            self._file = GitFile(self._filename, "rb")
        else:
            self._file = file
        (version, self._num_objects) = read_pack_header(self._file.read)
        self._offset_cache = LRUSizeCache(
            1024 * 1024 * 20, compute_size=_compute_object_size
        )

    @property
    def filename(self):
        return os.path.basename(self._filename)

    @property
    def path(self):
        return self._filename

    @classmethod
    def from_file(cls, file, size=None):
        return cls(str(file), file=file, size=size)

    @classmethod
    def from_path(cls, path):
        return cls(filename=path)

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __eq__(self, other):
        if isinstance(other, PackData):
            return self.get_stored_checksum() == other.get_stored_checksum()
        return False

    def _get_size(self):
        if self._size is not None:
            return self._size
        self._size = os.path.getsize(self._filename)
        if self._size < self._header_size:
            errmsg = "%s is too small for a packfile (%d < %d)" % (
                self._filename,
                self._size,
                self._header_size,
            )
            raise AssertionError(errmsg)
        return self._size

    def __len__(self):
        """Returns the number of objects in this pack."""
        return self._num_objects

    def calculate_checksum(self):
        """Calculate the checksum for this pack.

        Returns: 20-byte binary SHA1 digest
        """
        return compute_file_sha(self._file, end_ofs=-20).digest()

    def iter_unpacked(self, *, include_comp: bool = False):
        self._file.seek(self._header_size)

        if self._num_objects is None:
            return

        for _ in range(self._num_objects):
            offset = self._file.tell()
            unpacked, unused = unpack_object(self._file.read, compute_crc32=False, include_comp=include_comp)
            unpacked.offset = offset
            yield unpacked
            # Back up over unused data.
            self._file.seek(-len(unused), SEEK_CUR)

    def iterentries(self, progress: Optional[ProgressFn] = None, resolve_ext_ref: Optional[ResolveExtRefFn] = None):
        """Yield entries summarizing the contents of this pack.

        Args:
          progress: Progress function, called with current and total
            object count.
        Returns: iterator of tuples with (sha, offset, crc32)
        """
        num_objects = self._num_objects
        indexer = PackIndexer.for_pack_data(self, resolve_ext_ref=resolve_ext_ref)
        for i, result in enumerate(indexer):
            if progress is not None:
                progress(i, num_objects)
            yield result

    def sorted_entries(self, progress: Optional[ProgressFn] = None, resolve_ext_ref: Optional[ResolveExtRefFn] = None):
        """Return entries in this pack, sorted by SHA.

        Args:
          progress: Progress function, called with current and total
            object count
        Returns: Iterator of tuples with (sha, offset, crc32)
        """
        return sorted(self.iterentries(
            progress=progress, resolve_ext_ref=resolve_ext_ref))

    def create_index_v1(self, filename, progress=None, resolve_ext_ref=None):
        """Create a version 1 file for this data file.

        Args:
          filename: Index filename.
          progress: Progress report function
        Returns: Checksum of index file
        """
        entries = self.sorted_entries(
            progress=progress, resolve_ext_ref=resolve_ext_ref)
        with GitFile(filename, "wb") as f:
            return write_pack_index_v1(f, entries, self.calculate_checksum())

    def create_index_v2(self, filename, progress=None, resolve_ext_ref=None):
        """Create a version 2 index file for this data file.

        Args:
          filename: Index filename.
          progress: Progress report function
        Returns: Checksum of index file
        """
        entries = self.sorted_entries(
            progress=progress, resolve_ext_ref=resolve_ext_ref)
        with GitFile(filename, "wb") as f:
            return write_pack_index_v2(f, entries, self.calculate_checksum())

    def create_index(self, filename, progress=None, version=2, resolve_ext_ref=None):
        """Create an  index file for this data file.

        Args:
          filename: Index filename.
          progress: Progress report function
        Returns: Checksum of index file
        """
        if version == 1:
            return self.create_index_v1(
                filename, progress, resolve_ext_ref=resolve_ext_ref)
        elif version == 2:
            return self.create_index_v2(
                filename, progress, resolve_ext_ref=resolve_ext_ref)
        else:
            raise ValueError("unknown index format %d" % version)

    def get_stored_checksum(self):
        """Return the expected checksum stored in this pack."""
        self._file.seek(-20, SEEK_END)
        return self._file.read(20)

    def check(self):
        """Check the consistency of this pack."""
        actual = self.calculate_checksum()
        stored = self.get_stored_checksum()
        if actual != stored:
            raise ChecksumMismatch(stored, actual)

    def get_unpacked_object_at(self, offset: int, *, include_comp: bool = False) -> UnpackedObject:
        """Given offset in the packfile return a UnpackedObject.
        """
        assert offset >= self._header_size
        self._file.seek(offset)
        unpacked, _ = unpack_object(self._file.read, include_comp=include_comp)
        unpacked.offset = offset
        return unpacked

    def get_object_at(self, offset: int) -> Tuple[int, OldUnpackedObject]:
        """Given an offset in to the packfile return the object that is there.

        Using the associated index the location of an object can be looked up,
        and then the packfile can be asked directly for that object using this
        function.
        """
        try:
            return self._offset_cache[offset]
        except KeyError:
            pass
        unpacked = self.get_unpacked_object_at(offset, include_comp=False)
        return (unpacked.pack_type_num, unpacked._obj())


T = TypeVar('T')


class DeltaChainIterator(Generic[T]):
    """Abstract iterator over pack data based on delta chains.

    Each object in the pack is guaranteed to be inflated exactly once,
    regardless of how many objects reference it as a delta base. As a result,
    memory usage is proportional to the length of the longest delta chain.

    Subclasses can override _result to define the result type of the iterator.
    By default, results are UnpackedObjects with the following members set:

    * offset
    * obj_type_num
    * obj_chunks
    * pack_type_num
    * delta_base     (for delta types)
    * comp_chunks    (if _include_comp is True)
    * decomp_chunks
    * decomp_len
    * crc32          (if _compute_crc32 is True)
    """

    _compute_crc32 = False
    _include_comp = False

    def __init__(self, file_obj, *, resolve_ext_ref=None) -> None:
        self._file = file_obj
        self._resolve_ext_ref = resolve_ext_ref
        self._pending_ofs: Dict[int, List[int]] = defaultdict(list)
        self._pending_ref: Dict[bytes, List[int]] = defaultdict(list)
        self._full_ofs: List[Tuple[int, int]] = []
        self._ext_refs: List[bytes] = []

    @classmethod
    def for_pack_data(cls, pack_data: PackData, resolve_ext_ref=None):
        walker = cls(None, resolve_ext_ref=resolve_ext_ref)
        walker.set_pack_data(pack_data)
        for unpacked in pack_data.iter_unpacked(include_comp=False):
            walker.record(unpacked)
        return walker

    @classmethod
    def for_pack_subset(
            cls, pack: "Pack", shas: Iterable[bytes], *,
            allow_missing: bool = False, resolve_ext_ref=None):
        walker = cls(None, resolve_ext_ref=resolve_ext_ref)
        walker.set_pack_data(pack.data)
        todo = set()
        for sha in shas:
            assert isinstance(sha, bytes)
            try:
                off = pack.index.object_offset(sha)
            except KeyError:
                if not allow_missing:
                    raise
            else:
                todo.add(off)
        done = set()
        while todo:
            off = todo.pop()
            unpacked = pack.data.get_unpacked_object_at(off)
            walker.record(unpacked)
            done.add(off)
            base_ofs = None
            if unpacked.pack_type_num == OFS_DELTA:
                base_ofs = unpacked.offset - unpacked.delta_base
            elif unpacked.pack_type_num == REF_DELTA:
                with suppress(KeyError):
                    assert isinstance(unpacked.delta_base, bytes)
                    base_ofs = pack.index.object_index(unpacked.delta_base)
            if base_ofs is not None and base_ofs not in done:
                todo.add(base_ofs)
        return walker

    def record(self, unpacked: UnpackedObject) -> None:
        type_num = unpacked.pack_type_num
        offset = unpacked.offset
        if type_num == OFS_DELTA:
            base_offset = offset - unpacked.delta_base
            self._pending_ofs[base_offset].append(offset)
        elif type_num == REF_DELTA:
            assert isinstance(unpacked.delta_base, bytes)
            self._pending_ref[unpacked.delta_base].append(offset)
        else:
            self._full_ofs.append((offset, type_num))

    def set_pack_data(self, pack_data: PackData) -> None:
        self._file = pack_data._file

    def _walk_all_chains(self):
        for offset, type_num in self._full_ofs:
            yield from self._follow_chain(offset, type_num, None)
        yield from self._walk_ref_chains()
        assert not self._pending_ofs, repr(self._pending_ofs)

    def _ensure_no_pending(self) -> None:
        if self._pending_ref:
            raise KeyError([sha_to_hex(s) for s in self._pending_ref])

    def _walk_ref_chains(self):
        if not self._resolve_ext_ref:
            self._ensure_no_pending()
            return

        for base_sha, pending in sorted(self._pending_ref.items()):
            if base_sha not in self._pending_ref:
                continue
            try:
                type_num, chunks = self._resolve_ext_ref(base_sha)
            except KeyError:
                # Not an external ref, but may depend on one. Either it will
                # get popped via a _follow_chain call, or we will raise an
                # error below.
                continue
            self._ext_refs.append(base_sha)
            self._pending_ref.pop(base_sha)
            for new_offset in pending:
                yield from self._follow_chain(new_offset, type_num, chunks)

        self._ensure_no_pending()

    def _result(self, unpacked: UnpackedObject) -> T:
        raise NotImplementedError

    def _resolve_object(self, offset: int, obj_type_num: int, base_chunks: List[bytes]) -> UnpackedObject:
        self._file.seek(offset)
        unpacked, _ = unpack_object(
            self._file.read,
            include_comp=self._include_comp,
            compute_crc32=self._compute_crc32,
        )
        unpacked.offset = offset
        if base_chunks is None:
            assert unpacked.pack_type_num == obj_type_num
        else:
            assert unpacked.pack_type_num in DELTA_TYPES
            unpacked.obj_type_num = obj_type_num
            unpacked.obj_chunks = apply_delta(base_chunks, unpacked.decomp_chunks)
        return unpacked

    def _follow_chain(self, offset: int, obj_type_num: int, base_chunks: List[bytes]):
        # Unlike PackData.get_object_at, there is no need to cache offsets as
        # this approach by design inflates each object exactly once.
        todo = [(offset, obj_type_num, base_chunks)]
        while todo:
            (offset, obj_type_num, base_chunks) = todo.pop()
            unpacked = self._resolve_object(offset, obj_type_num, base_chunks)
            yield self._result(unpacked)

            unblocked = chain(
                self._pending_ofs.pop(unpacked.offset, []),
                self._pending_ref.pop(unpacked.sha(), []),
            )
            todo.extend(
                (new_offset, unpacked.obj_type_num, unpacked.obj_chunks)  # type: ignore
                for new_offset in unblocked
            )

    def __iter__(self) -> Iterator[T]:
        return self._walk_all_chains()

    def ext_refs(self):
        return self._ext_refs


class UnpackedObjectIterator(DeltaChainIterator[UnpackedObject]):
    """Delta chain iterator that yield unpacked objects."""

    def _result(self, unpacked):
        return unpacked


class PackIndexer(DeltaChainIterator[PackIndexEntry]):
    """Delta chain iterator that yields index entries."""

    _compute_crc32 = True

    def _result(self, unpacked):
        return unpacked.sha(), unpacked.offset, unpacked.crc32


class PackInflater(DeltaChainIterator[ShaFile]):
    """Delta chain iterator that yields ShaFile objects."""

    def _result(self, unpacked):
        return unpacked.sha_file()


class SHA1Reader:
    """Wrapper for file-like object that remembers the SHA1 of its data."""

    def __init__(self, f):
        self.f = f
        self.sha1 = sha1(b"")

    def read(self, num=None):
        data = self.f.read(num)
        self.sha1.update(data)
        return data

    def check_sha(self):
        stored = self.f.read(20)
        if stored != self.sha1.digest():
            raise ChecksumMismatch(self.sha1.hexdigest(), sha_to_hex(stored))

    def close(self):
        return self.f.close()

    def tell(self):
        return self.f.tell()


class SHA1Writer:
    """Wrapper for file-like object that remembers the SHA1 of its data."""

    def __init__(self, f):
        self.f = f
        self.length = 0
        self.sha1 = sha1(b"")

    def write(self, data):
        self.sha1.update(data)
        self.f.write(data)
        self.length += len(data)

    def write_sha(self):
        sha = self.sha1.digest()
        assert len(sha) == 20
        self.f.write(sha)
        self.length += len(sha)
        return sha

    def close(self):
        sha = self.write_sha()
        self.f.close()
        return sha

    def offset(self):
        return self.length

    def tell(self):
        return self.f.tell()


def pack_object_header(type_num, delta_base, size):
    """Create a pack object header for the given object info.

    Args:
      type_num: Numeric type of the object.
      delta_base: Delta base offset or ref, or None for whole objects.
      size: Uncompressed object size.
    Returns: A header for a packed object.
    """
    header = []
    c = (type_num << 4) | (size & 15)
    size >>= 4
    while size:
        header.append(c | 0x80)
        c = size & 0x7F
        size >>= 7
    header.append(c)
    if type_num == OFS_DELTA:
        ret = [delta_base & 0x7F]
        delta_base >>= 7
        while delta_base:
            delta_base -= 1
            ret.insert(0, 0x80 | (delta_base & 0x7F))
            delta_base >>= 7
        header.extend(ret)
    elif type_num == REF_DELTA:
        assert len(delta_base) == 20
        header += delta_base
    return bytearray(header)


def pack_object_chunks(type, object, compression_level=-1):
    """Generate chunks for a pack object.

    Args:
      type: Numeric type of the object
      object: Object to write
      compression_level: the zlib compression level
    Returns: Chunks
    """
    if type in DELTA_TYPES:
        delta_base, object = object
    else:
        delta_base = None
    if isinstance(object, bytes):
        object = [object]
    yield bytes(pack_object_header(type, delta_base, sum(map(len, object))))
    compressor = zlib.compressobj(level=compression_level)
    for data in object:
        yield compressor.compress(data)
    yield compressor.flush()


def write_pack_object(write, type, object, sha=None, compression_level=-1):
    """Write pack object to a file.

    Args:
      write: Write function to use
      type: Numeric type of the object
      object: Object to write
      compression_level: the zlib compression level
    Returns: Tuple with offset at which the object was written, and crc32
    """
    crc32 = 0
    for chunk in pack_object_chunks(
            type, object, compression_level=compression_level):
        write(chunk)
        if sha is not None:
            sha.update(chunk)
        crc32 = binascii.crc32(chunk, crc32)
    return crc32 & 0xFFFFFFFF


def write_pack(
        filename,
        objects: Union[Sequence[ShaFile], Sequence[Tuple[ShaFile, Optional[bytes]]]],
        *,
        deltify: Optional[bool] = None,
        delta_window_size: Optional[int] = None,
        compression_level: int = -1):
    """Write a new pack data file.

    Args:
      filename: Path to the new pack file (without .pack extension)
      container: PackedObjectContainer
      entries: Sequence of (object_id, path) tuples to write
      delta_window_size: Delta window size
      deltify: Whether to deltify pack objects
      compression_level: the zlib compression level
    Returns: Tuple with checksum of pack file and index file
    """
    with GitFile(filename + ".pack", "wb") as f:
        entries, data_sum = write_pack_objects(
            f.write,
            objects,
            delta_window_size=delta_window_size,
            deltify=deltify,
            compression_level=compression_level,
        )
    entries = sorted([(k, v[0], v[1]) for (k, v) in entries.items()])
    with GitFile(filename + ".idx", "wb") as f:
        return data_sum, write_pack_index_v2(f, entries, data_sum)


def pack_header_chunks(num_objects):
    """Yield chunks for a pack header."""
    yield b"PACK"  # Pack header
    yield struct.pack(b">L", 2)  # Pack version
    yield struct.pack(b">L", num_objects)  # Number of objects in pack


def write_pack_header(write, num_objects):
    """Write a pack header for the given number of objects."""
    if hasattr(write, 'write'):
        write = write.write
        warnings.warn(
            'write_pack_header() now takes a write rather than file argument',
            DeprecationWarning, stacklevel=2)
    for chunk in pack_header_chunks(num_objects):
        write(chunk)


def find_reusable_deltas(
        container: PackedObjectContainer,
        object_ids: Set[bytes],
        *, other_haves: Optional[Set[bytes]] = None, progress=None) -> Iterator[UnpackedObject]:
    if other_haves is None:
        other_haves = set()
    reused = 0
    for i, unpacked in enumerate(container.iter_unpacked_subset(object_ids, allow_missing=True, convert_ofs_delta=True)):
        if progress is not None and i % 1000 == 0:
            progress(("checking for reusable deltas: %d/%d\r" % (i, len(object_ids))).encode('utf-8'))
        if unpacked.pack_type_num == REF_DELTA:
            hexsha = sha_to_hex(unpacked.delta_base)
            if hexsha in object_ids or hexsha in other_haves:
                yield unpacked
                reused += 1
    if progress is not None:
        progress(("found %d deltas to reuse\n" % (reused, )).encode('utf-8'))


def deltify_pack_objects(
        objects: Union[Iterator[bytes], Iterator[Tuple[ShaFile, Optional[bytes]]]],
        *, window_size: Optional[int] = None,
        progress=None) -> Iterator[UnpackedObject]:
    """Generate deltas for pack objects.

    Args:
      objects: An iterable of (object, path) tuples to deltify.
      window_size: Window size; None for default
    Returns: Iterator over type_num, object id, delta_base, content
        delta_base is None for full text entries
    """
    def objects_with_hints():
        for e in objects:
            if isinstance(e, ShaFile):
                yield (e, (e.type_num, None))
            else:
                yield (e[0], (e[0].type_num, e[1]))
    yield from deltas_from_sorted_objects(
        sort_objects_for_delta(objects_with_hints()),
        window_size=window_size,
        progress=progress)


def sort_objects_for_delta(objects: Union[Iterator[ShaFile], Iterator[Tuple[ShaFile, Optional[PackHint]]]]) -> Iterator[ShaFile]:
    magic = []
    for entry in objects:
        if isinstance(entry, tuple):
            obj, hint = entry
            if hint is None:
                type_num = None
                path = None
            else:
                (type_num, path) = hint
        else:
            obj = entry
        magic.append((type_num, path, -obj.raw_length(), obj))
    # Build a list of objects ordered by the magic Linus heuristic
    # This helps us find good objects to diff against us
    magic.sort()
    return (x[3] for x in magic)


def deltas_from_sorted_objects(objects, window_size: Optional[int] = None, progress=None):
    # TODO(jelmer): Use threads
    if window_size is None:
        window_size = DEFAULT_PACK_DELTA_WINDOW_SIZE

    possible_bases: Deque[Tuple[bytes, int, List[bytes]]] = deque()
    for i, o in enumerate(objects):
        if progress is not None and i % 1000 == 0:
            progress(("generating deltas: %d\r" % (i, )).encode('utf-8'))
        raw = o.as_raw_chunks()
        winner = raw
        winner_len = sum(map(len, winner))
        winner_base = None
        for base_id, base_type_num, base in possible_bases:
            if base_type_num != o.type_num:
                continue
            delta_len = 0
            delta = []
            for chunk in create_delta(base, raw):
                delta_len += len(chunk)
                if delta_len >= winner_len:
                    break
                delta.append(chunk)
            else:
                winner_base = base_id
                winner = delta
                winner_len = sum(map(len, winner))
        yield UnpackedObject(o.type_num, sha=o.sha().digest(), delta_base=winner_base, decomp_len=winner_len, decomp_chunks=winner)
        possible_bases.appendleft((o.sha().digest(), o.type_num, raw))
        while len(possible_bases) > window_size:
            possible_bases.pop()


def pack_objects_to_data(
        objects: Union[Sequence[ShaFile], Sequence[Tuple[ShaFile, Optional[bytes]]]],
        *,
        deltify: Optional[bool] = None,
        delta_window_size: Optional[int] = None,
        ofs_delta: bool = True,
        progress=None) -> Tuple[int, Iterator[UnpackedObject]]:
    """Create pack data from objects

    Args:
      objects: Pack objects
    Returns: Tuples with (type_num, hexdigest, delta base, object chunks)
    """
    # TODO(jelmer): support deltaifying
    count = len(objects)
    if deltify is None:
        # PERFORMANCE/TODO(jelmer): This should be enabled but is *much* too
        # slow at the moment.
        deltify = False
    if deltify:
        return (
            count,
            deltify_pack_objects(iter(objects), window_size=delta_window_size, progress=progress))  # type: ignore
    else:
        def iter_without_path():
            for o in objects:
                if isinstance(o, tuple):
                    yield full_unpacked_object(o[0])
                else:
                    yield full_unpacked_object(o)
        return (
            count,
            iter_without_path()
        )


def generate_unpacked_objects(
        container: PackedObjectContainer,
        object_ids: Sequence[Tuple[ObjectID, Optional[PackHint]]],
        delta_window_size: Optional[int] = None,
        deltify: Optional[bool] = None,
        reuse_deltas: bool = True,
        ofs_delta: bool = True,
        other_haves: Optional[Set[bytes]] = None,
        progress=None) -> Iterator[UnpackedObject]:
    """Create pack data from objects

    Args:
      objects: Pack objects
    Returns: Tuples with (type_num, hexdigest, delta base, object chunks)
    """
    todo = dict(object_ids)
    if reuse_deltas:
        for unpack in find_reusable_deltas(container, set(todo), other_haves=other_haves, progress=progress):
            del todo[sha_to_hex(unpack.sha())]
            yield unpack
    if deltify is None:
        # PERFORMANCE/TODO(jelmer): This should be enabled but is *much* too
        # slow at the moment.
        deltify = False
    if deltify:
        objects_to_delta = container.iterobjects_subset(todo.keys(), allow_missing=False)
        yield from deltas_from_sorted_objects(
            sort_objects_for_delta(
                (o, todo[o.id])
                for o in objects_to_delta),
            window_size=delta_window_size,
            progress=progress)
    else:
        for oid in todo:
            yield full_unpacked_object(container[oid])


def full_unpacked_object(o: ShaFile) -> UnpackedObject:
    return UnpackedObject(
        o.type_num, delta_base=None, crc32=None,
        decomp_chunks=o.as_raw_chunks(),
        sha=o.sha().digest())


def write_pack_from_container(
        write,
        container: PackedObjectContainer,
        object_ids: Sequence[Tuple[ObjectID, Optional[PackHint]]],
        delta_window_size: Optional[int] = None,
        deltify: Optional[bool] = None,
        reuse_deltas: bool = True,
        compression_level: int = -1,
        other_haves: Optional[Set[bytes]] = None
):
    """Write a new pack data file.

    Args:
      write: write function to use
      container: PackedObjectContainer
      entries: Sequence of (object_id, path) tuples to write
      delta_window_size: Sliding window size for searching for deltas;
                         Set to None for default window size.
      deltify: Whether to deltify objects
      compression_level: the zlib compression level to use
    Returns: Dict mapping id -> (offset, crc32 checksum), pack checksum
    """
    pack_contents_count = len(object_ids)
    pack_contents = generate_unpacked_objects(
        container, object_ids, delta_window_size=delta_window_size,
        deltify=deltify,
        reuse_deltas=reuse_deltas,
        other_haves=other_haves)

    return write_pack_data(
        write,
        pack_contents,
        num_records=pack_contents_count,
        compression_level=compression_level,
    )


def write_pack_objects(
        write,
        objects: Union[Sequence[ShaFile], Sequence[Tuple[ShaFile, Optional[bytes]]]],
        *,
        delta_window_size: Optional[int] = None,
        deltify: Optional[bool] = None,
        compression_level: int = -1
):
    """Write a new pack data file.

    Args:
      write: write function to use
      objects: Sequence of (object, path) tuples to write
      delta_window_size: Sliding window size for searching for deltas;
                         Set to None for default window size.
      deltify: Whether to deltify objects
      compression_level: the zlib compression level to use
    Returns: Dict mapping id -> (offset, crc32 checksum), pack checksum
    """
    pack_contents_count, pack_contents = pack_objects_to_data(
        objects, deltify=deltify)

    return write_pack_data(
        write,
        pack_contents,
        num_records=pack_contents_count,
        compression_level=compression_level,
    )


class PackChunkGenerator:

    def __init__(self, num_records=None, records=None, progress=None, compression_level=-1, reuse_compressed=True):
        self.cs = sha1(b"")
        self.entries = {}
        self._it = self._pack_data_chunks(
            num_records=num_records, records=records, progress=progress, compression_level=compression_level, reuse_compressed=reuse_compressed)

    def sha1digest(self):
        return self.cs.digest()

    def __iter__(self):
        return self._it

    def _pack_data_chunks(self, records: Iterator[UnpackedObject], *, num_records=None, progress=None, compression_level: int = -1, reuse_compressed: bool = True) -> Iterator[bytes]:
        """Iterate pack data file chunks.

        Args:
          records: Iterator over UnpackedObject
          num_records: Number of records (defaults to len(records) if not specified)
          progress: Function to report progress to
          compression_level: the zlib compression level
        Returns: Dict mapping id -> (offset, crc32 checksum), pack checksum
        """
        # Write the pack
        if num_records is None:
            num_records = len(records)   # type: ignore
        offset = 0
        for chunk in pack_header_chunks(num_records):
            yield chunk
            self.cs.update(chunk)
            offset += len(chunk)
        actual_num_records = 0
        for i, unpacked in enumerate(records):
            type_num = unpacked.pack_type_num
            if progress is not None and i % 1000 == 0:
                progress(("writing pack data: %d/%d\r" % (i, num_records)).encode("ascii"))
            raw: Union[List[bytes], Tuple[int, List[bytes]], Tuple[bytes, List[bytes]]]
            if unpacked.delta_base is not None:
                try:
                    base_offset, base_crc32 = self.entries[unpacked.delta_base]
                except KeyError:
                    type_num = REF_DELTA
                    assert isinstance(unpacked.delta_base, bytes)
                    raw = (unpacked.delta_base, unpacked.decomp_chunks)
                else:
                    type_num = OFS_DELTA
                    raw = (offset - base_offset, unpacked.decomp_chunks)
            else:
                raw = unpacked.decomp_chunks
            if unpacked.comp_chunks is not None and reuse_compressed:
                chunks = unpacked.comp_chunks
            else:
                chunks = pack_object_chunks(type_num, raw, compression_level=compression_level)
            crc32 = 0
            object_size = 0
            for chunk in chunks:
                yield chunk
                crc32 = binascii.crc32(chunk, crc32)
                self.cs.update(chunk)
                object_size += len(chunk)
            actual_num_records += 1
            self.entries[unpacked.sha()] = (offset, crc32)
            offset += object_size
        if actual_num_records != num_records:
            raise AssertionError(
                'actual records written differs: %d != %d' % (
                    actual_num_records, num_records))

        yield self.cs.digest()


def write_pack_data(write, records: Iterator[UnpackedObject], *, num_records=None, progress=None, compression_level=-1):
    """Write a new pack data file.

    Args:
      write: Write function to use
      num_records: Number of records (defaults to len(records) if None)
      records: Iterator over type_num, object_id, delta_base, raw
      progress: Function to report progress to
      compression_level: the zlib compression level
    Returns: Dict mapping id -> (offset, crc32 checksum), pack checksum
    """
    chunk_generator = PackChunkGenerator(
        num_records=num_records, records=records, progress=progress,
        compression_level=compression_level)
    for chunk in chunk_generator:
        write(chunk)
    return chunk_generator.entries, chunk_generator.sha1digest()


def write_pack_index_v1(f, entries, pack_checksum):
    """Write a new pack index file.

    Args:
      f: A file-like object to write to
      entries: List of tuples with object name (sha), offset_in_pack,
        and crc32_checksum.
      pack_checksum: Checksum of the pack file.
    Returns: The SHA of the written index file
    """
    f = SHA1Writer(f)
    fan_out_table = defaultdict(lambda: 0)
    for (name, offset, entry_checksum) in entries:
        fan_out_table[ord(name[:1])] += 1
    # Fan-out table
    for i in range(0x100):
        f.write(struct.pack(">L", fan_out_table[i]))
        fan_out_table[i + 1] += fan_out_table[i]
    for (name, offset, entry_checksum) in entries:
        if not (offset <= 0xFFFFFFFF):
            raise TypeError("pack format 1 only supports offsets < 2Gb")
        f.write(struct.pack(">L20s", offset, name))
    assert len(pack_checksum) == 20
    f.write(pack_checksum)
    return f.write_sha()


def _delta_encode_size(size) -> bytes:
    ret = bytearray()
    c = size & 0x7F
    size >>= 7
    while size:
        ret.append(c | 0x80)
        c = size & 0x7F
        size >>= 7
    ret.append(c)
    return bytes(ret)


# The length of delta compression copy operations in version 2 packs is limited
# to 64K.  To copy more, we use several copy operations.  Version 3 packs allow
# 24-bit lengths in copy operations, but we always make version 2 packs.
_MAX_COPY_LEN = 0xFFFF


def _encode_copy_operation(start, length):
    scratch = bytearray([0x80])
    for i in range(4):
        if start & 0xFF << i * 8:
            scratch.append((start >> i * 8) & 0xFF)
            scratch[0] |= 1 << i
    for i in range(2):
        if length & 0xFF << i * 8:
            scratch.append((length >> i * 8) & 0xFF)
            scratch[0] |= 1 << (4 + i)
    return bytes(scratch)


def create_delta(base_buf, target_buf):
    """Use python difflib to work out how to transform base_buf to target_buf.

    Args:
      base_buf: Base buffer
      target_buf: Target buffer
    """
    if isinstance(base_buf, list):
        base_buf = b''.join(base_buf)
    if isinstance(target_buf, list):
        target_buf = b''.join(target_buf)
    assert isinstance(base_buf, bytes)
    assert isinstance(target_buf, bytes)
    # write delta header
    yield _delta_encode_size(len(base_buf))
    yield _delta_encode_size(len(target_buf))
    # write out delta opcodes
    seq = SequenceMatcher(isjunk=None, a=base_buf, b=target_buf)
    for opcode, i1, i2, j1, j2 in seq.get_opcodes():
        # Git patch opcodes don't care about deletes!
        # if opcode == 'replace' or opcode == 'delete':
        #    pass
        if opcode == "equal":
            # If they are equal, unpacker will use data from base_buf
            # Write out an opcode that says what range to use
            copy_start = i1
            copy_len = i2 - i1
            while copy_len > 0:
                to_copy = min(copy_len, _MAX_COPY_LEN)
                yield _encode_copy_operation(copy_start, to_copy)
                copy_start += to_copy
                copy_len -= to_copy
        if opcode == "replace" or opcode == "insert":
            # If we are replacing a range or adding one, then we just
            # output it to the stream (prefixed by its size)
            s = j2 - j1
            o = j1
            while s > 127:
                yield bytes([127])
                yield memoryview(target_buf)[o:o + 127]
                s -= 127
                o += 127
            yield bytes([s])
            yield memoryview(target_buf)[o:o + s]


def apply_delta(src_buf, delta):
    """Based on the similar function in git's patch-delta.c.

    Args:
      src_buf: Source buffer
      delta: Delta instructions
    """
    if not isinstance(src_buf, bytes):
        src_buf = b"".join(src_buf)
    if not isinstance(delta, bytes):
        delta = b"".join(delta)
    out = []
    index = 0
    delta_length = len(delta)

    def get_delta_header_size(delta, index):
        size = 0
        i = 0
        while delta:
            cmd = ord(delta[index : index + 1])
            index += 1
            size |= (cmd & ~0x80) << i
            i += 7
            if not cmd & 0x80:
                break
        return size, index

    src_size, index = get_delta_header_size(delta, index)
    dest_size, index = get_delta_header_size(delta, index)
    assert src_size == len(src_buf), "%d vs %d" % (src_size, len(src_buf))
    while index < delta_length:
        cmd = ord(delta[index : index + 1])
        index += 1
        if cmd & 0x80:
            cp_off = 0
            for i in range(4):
                if cmd & (1 << i):
                    x = ord(delta[index : index + 1])
                    index += 1
                    cp_off |= x << (i * 8)
            cp_size = 0
            # Version 3 packs can contain copy sizes larger than 64K.
            for i in range(3):
                if cmd & (1 << (4 + i)):
                    x = ord(delta[index : index + 1])
                    index += 1
                    cp_size |= x << (i * 8)
            if cp_size == 0:
                cp_size = 0x10000
            if (
                cp_off + cp_size < cp_size
                or cp_off + cp_size > src_size
                or cp_size > dest_size
            ):
                break
            out.append(src_buf[cp_off : cp_off + cp_size])
        elif cmd != 0:
            out.append(delta[index : index + cmd])
            index += cmd
        else:
            raise ApplyDeltaError("Invalid opcode 0")

    if index != delta_length:
        raise ApplyDeltaError("delta not empty: %r" % delta[index:])

    if dest_size != chunks_length(out):
        raise ApplyDeltaError("dest size incorrect")

    return out


def write_pack_index_v2(
        f, entries: Iterable[PackIndexEntry], pack_checksum: bytes) -> bytes:
    """Write a new pack index file.

    Args:
      f: File-like object to write to
      entries: List of tuples with object name (sha), offset_in_pack, and
        crc32_checksum.
      pack_checksum: Checksum of the pack file.
    Returns: The SHA of the index file written
    """
    f = SHA1Writer(f)
    f.write(b"\377tOc")  # Magic!
    f.write(struct.pack(">L", 2))
    fan_out_table: Dict[int, int] = defaultdict(lambda: 0)
    for (name, offset, entry_checksum) in entries:
        fan_out_table[ord(name[:1])] += 1
    # Fan-out table
    largetable: List[int] = []
    for i in range(0x100):
        f.write(struct.pack(b">L", fan_out_table[i]))
        fan_out_table[i + 1] += fan_out_table[i]
    for (name, offset, entry_checksum) in entries:
        f.write(name)
    for (name, offset, entry_checksum) in entries:
        f.write(struct.pack(b">L", entry_checksum))
    for (name, offset, entry_checksum) in entries:
        if offset < 2 ** 31:
            f.write(struct.pack(b">L", offset))
        else:
            f.write(struct.pack(b">L", 2 ** 31 + len(largetable)))
            largetable.append(offset)
    for offset in largetable:
        f.write(struct.pack(b">Q", offset))
    assert len(pack_checksum) == 20
    f.write(pack_checksum)
    return f.write_sha()


write_pack_index = write_pack_index_v2


class Pack:
    """A Git pack object."""

    _data_load: Optional[Callable[[], PackData]]
    _idx_load: Optional[Callable[[], PackIndex]]

    _data: Optional[PackData]
    _idx: Optional[PackIndex]

    def __init__(self, basename, resolve_ext_ref: Optional[ResolveExtRefFn] = None):
        self._basename = basename
        self._data = None
        self._idx = None
        self._idx_path = self._basename + ".idx"
        self._data_path = self._basename + ".pack"
        self._data_load = lambda: PackData(self._data_path)
        self._idx_load = lambda: load_pack_index(self._idx_path)
        self.resolve_ext_ref = resolve_ext_ref

    @classmethod
    def from_lazy_objects(cls, data_fn, idx_fn):
        """Create a new pack object from callables to load pack data and
        index objects."""
        ret = cls("")
        ret._data_load = data_fn
        ret._idx_load = idx_fn
        return ret

    @classmethod
    def from_objects(cls, data, idx):
        """Create a new pack object from pack data and index objects."""
        ret = cls("")
        ret._data = data
        ret._data_load = None
        ret._idx = idx
        ret._idx_load = None
        ret.check_length_and_checksum()
        return ret

    def name(self):
        """The SHA over the SHAs of the objects in this pack."""
        return self.index.objects_sha1()

    @property
    def data(self) -> PackData:
        """The pack data object being used."""
        if self._data is None:
            assert self._data_load
            self._data = self._data_load()
            self.check_length_and_checksum()
        return self._data

    @property
    def index(self) -> PackIndex:
        """The index being used.

        Note: This may be an in-memory index
        """
        if self._idx is None:
            assert self._idx_load
            self._idx = self._idx_load()
        return self._idx

    def close(self):
        if self._data is not None:
            self._data.close()
        if self._idx is not None:
            self._idx.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.index == other.index

    def __len__(self):
        """Number of entries in this pack."""
        return len(self.index)

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self._basename)

    def __iter__(self):
        """Iterate over all the sha1s of the objects in this pack."""
        return iter(self.index)

    def check_length_and_checksum(self) -> None:
        """Sanity check the length and checksum of the pack index and data."""
        assert len(self.index) == len(self.data), f"Length mismatch: {len(self.index)} (index) != {len(self.data)} (data)"
        idx_stored_checksum = self.index.get_pack_checksum()
        data_stored_checksum = self.data.get_stored_checksum()
        if idx_stored_checksum != data_stored_checksum:
            raise ChecksumMismatch(
                sha_to_hex(idx_stored_checksum),
                sha_to_hex(data_stored_checksum),
            )

    def check(self) -> None:
        """Check the integrity of this pack.

        Raises:
          ChecksumMismatch: if a checksum for the index or data is wrong
        """
        self.index.check()
        self.data.check()
        for obj in self.iterobjects():
            obj.check()
        # TODO: object connectivity checks

    def get_stored_checksum(self) -> bytes:
        return self.data.get_stored_checksum()

    def pack_tuples(self):
        return [(o, None) for o in self.iterobjects()]

    def __contains__(self, sha1: bytes) -> bool:
        """Check whether this pack contains a particular SHA1."""
        try:
            self.index.object_offset(sha1)
            return True
        except KeyError:
            return False

    def get_raw(self, sha1: bytes) -> Tuple[int, bytes]:
        offset = self.index.object_offset(sha1)
        obj_type, obj = self.data.get_object_at(offset)
        type_num, chunks = self.resolve_object(offset, obj_type, obj)
        return type_num, b"".join(chunks)

    def __getitem__(self, sha1: bytes) -> ShaFile:
        """Retrieve the specified SHA1."""
        type, uncomp = self.get_raw(sha1)
        return ShaFile.from_raw_string(type, uncomp, sha=sha1)

    def iterobjects(self) -> Iterator[ShaFile]:
        """Iterate over the objects in this pack."""
        return iter(
            PackInflater.for_pack_data(self.data, resolve_ext_ref=self.resolve_ext_ref)
        )

    def iterobjects_subset(self, shas: Iterable[ObjectID], *, allow_missing: bool = False) -> Iterator[ShaFile]:
        return (
            uo
            for uo in
            PackInflater.for_pack_subset(
                self, shas, allow_missing=allow_missing,
                resolve_ext_ref=self.resolve_ext_ref)
            if uo.id in shas)

    def iter_unpacked_subset(self, shas: Iterable[ObjectID], *, include_comp: bool = False, allow_missing: bool = False, convert_ofs_delta: bool = False) -> Iterator[UnpackedObject]:
        ofs_pending: Dict[int, List[UnpackedObject]] = defaultdict(list)
        ofs: Dict[bytes, int] = {}
        todo = set(shas)
        for unpacked in self.iter_unpacked(include_comp=include_comp):
            sha = unpacked.sha()
            ofs[unpacked.offset] = sha
            hexsha = sha_to_hex(sha)
            if hexsha in todo:
                if unpacked.pack_type_num == OFS_DELTA:
                    assert isinstance(unpacked.delta_base, int)
                    base_offset = unpacked.offset - unpacked.delta_base
                    try:
                        unpacked.delta_base = ofs[base_offset]
                    except KeyError:
                        ofs_pending[base_offset].append(unpacked)
                        continue
                    else:
                        unpacked.pack_type_num = REF_DELTA
                yield unpacked
                todo.remove(hexsha)
            for child in ofs_pending.pop(unpacked.offset, []):
                child.pack_type_num = REF_DELTA
                child.delta_base = sha
                yield child
        assert not ofs_pending
        if not allow_missing and todo:
            raise KeyError(todo.pop())

    def iter_unpacked(self, include_comp=False):
        ofs_to_entries = {ofs: (sha, crc32) for (sha, ofs, crc32) in self.index.iterentries()}
        for unpacked in self.data.iter_unpacked(include_comp=include_comp):
            (sha, crc32) = ofs_to_entries[unpacked.offset]
            unpacked._sha = sha
            unpacked.crc32 = crc32
            yield unpacked

    def keep(self, msg: Optional[bytes] = None) -> str:
        """Add a .keep file for the pack, preventing git from garbage collecting it.

        Args:
          msg: A message written inside the .keep file; can be used later
            to determine whether or not a .keep file is obsolete.
        Returns: The path of the .keep file, as a string.
        """
        keepfile_name = "%s.keep" % self._basename
        with GitFile(keepfile_name, "wb") as keepfile:
            if msg:
                keepfile.write(msg)
                keepfile.write(b"\n")
        return keepfile_name

    def get_ref(self, sha: bytes) -> Tuple[Optional[int], int, OldUnpackedObject]:
        """Get the object for a ref SHA, only looking in this pack."""
        # TODO: cache these results
        try:
            offset = self.index.object_offset(sha)
        except KeyError:
            offset = None
        if offset:
            type, obj = self.data.get_object_at(offset)
        elif self.resolve_ext_ref:
            type, obj = self.resolve_ext_ref(sha)
        else:
            raise KeyError(sha)
        return offset, type, obj

    def resolve_object(self, offset: int, type: int, obj, get_ref=None) -> Tuple[int, Iterable[bytes]]:
        """Resolve an object, possibly resolving deltas when necessary.

        Returns: Tuple with object type and contents.
        """
        # Walk down the delta chain, building a stack of deltas to reach
        # the requested object.
        base_offset = offset
        base_type = type
        base_obj = obj
        delta_stack = []
        while base_type in DELTA_TYPES:
            prev_offset = base_offset
            if get_ref is None:
                get_ref = self.get_ref
            if base_type == OFS_DELTA:
                (delta_offset, delta) = base_obj
                # TODO: clean up asserts and replace with nicer error messages
                base_offset = base_offset - delta_offset
                base_type, base_obj = self.data.get_object_at(base_offset)
                assert isinstance(base_type, int)
            elif base_type == REF_DELTA:
                (basename, delta) = base_obj
                assert isinstance(basename, bytes) and len(basename) == 20
                base_offset, base_type, base_obj = get_ref(basename)
                assert isinstance(base_type, int)
            delta_stack.append((prev_offset, base_type, delta))

        # Now grab the base object (mustn't be a delta) and apply the
        # deltas all the way up the stack.
        chunks = base_obj
        for prev_offset, delta_type, delta in reversed(delta_stack):
            chunks = apply_delta(chunks, delta)
            # TODO(dborowitz): This can result in poor performance if
            # large base objects are separated from deltas in the pack.
            # We should reorganize so that we apply deltas to all
            # objects in a chain one after the other to optimize cache
            # performance.
            if prev_offset is not None:
                self.data._offset_cache[prev_offset] = base_type, chunks
        return base_type, chunks

    def entries(self, progress: Optional[ProgressFn] = None) -> Iterator[PackIndexEntry]:
        """Yield entries summarizing the contents of this pack.

        Args:
          progress: Progress function, called with current and total
            object count.
        Returns: iterator of tuples with (sha, offset, crc32)
        """
        return self.data.iterentries(
            progress=progress, resolve_ext_ref=self.resolve_ext_ref)

    def sorted_entries(self, progress: Optional[ProgressFn] = None) -> Iterator[PackIndexEntry]:
        """Return entries in this pack, sorted by SHA.

        Args:
          progress: Progress function, called with current and total
            object count
        Returns: Iterator of tuples with (sha, offset, crc32)
        """
        return self.data.sorted_entries(
            progress=progress, resolve_ext_ref=self.resolve_ext_ref)

    def get_unpacked_object(self, sha: bytes, *, include_comp: bool = False, convert_ofs_delta: bool = True) -> UnpackedObject:
        """Get the unpacked object for a sha.

        Args:
          sha: SHA of object to fetch
          include_comp: Whether to include compression data in UnpackedObject
        """
        offset = self.index.object_offset(sha)
        unpacked = self.data.get_unpacked_object_at(offset, include_comp=include_comp)
        if unpacked.pack_type_num == OFS_DELTA and convert_ofs_delta:
            assert isinstance(unpacked.delta_base, int)
            unpacked.delta_base = self.index.object_sha1(offset - unpacked.delta_base)
            unpacked.pack_type_num = REF_DELTA
        return unpacked


def extend_pack(f: BinaryIO, object_ids: Set[ObjectID], get_raw, *, compression_level=-1, progress=None) -> Tuple[bytes, List]:
    """Extend a pack file with more objects.

    The caller should make sure that object_ids does not contain any objects
    that are already in the pack
    """
    # Update the header with the new number of objects.
    f.seek(0)
    _version, num_objects = read_pack_header(f.read)

    if object_ids:
        f.seek(0)
        write_pack_header(f.write, num_objects + len(object_ids))

        # Must flush before reading (http://bugs.python.org/issue3207)
        f.flush()

    # Rescan the rest of the pack, computing the SHA with the new header.
    new_sha = compute_file_sha(f, end_ofs=-20)

    # Must reposition before writing (http://bugs.python.org/issue3207)
    f.seek(0, os.SEEK_CUR)

    extra_entries = []

    # Complete the pack.
    for i, object_id in enumerate(object_ids):
        if progress is not None:
            progress(("writing extra base objects: %d/%d\r" % (i, len(object_ids))).encode("ascii"))
        assert len(object_id) == 20
        type_num, data = get_raw(object_id)
        offset = f.tell()
        crc32 = write_pack_object(
            f.write,
            type_num,
            data,
            sha=new_sha,
            compression_level=compression_level,
        )
        extra_entries.append((object_id, offset, crc32))
    pack_sha = new_sha.digest()
    f.write(pack_sha)
    return pack_sha, extra_entries


try:
    from dulwich._pack import apply_delta  # type: ignore # noqa: F811
    from dulwich._pack import bisect_find_sha  # type: ignore # noqa: F811
except ImportError:
    pass
