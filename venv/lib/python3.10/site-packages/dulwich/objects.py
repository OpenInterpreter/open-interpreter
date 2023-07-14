# objects.py -- Access to base git objects
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

"""Access to base git objects."""

import binascii
import os
import posixpath
import stat
import warnings
import zlib
from collections import namedtuple
from hashlib import sha1
from io import BytesIO
from typing import (BinaryIO, Dict, Iterable, Iterator, List, Optional, Tuple,
                    Type, Union)

from _hashlib import HASH

from .errors import (ChecksumMismatch, FileFormatException, NotBlobError,
                     NotCommitError, NotTagError, NotTreeError,
                     ObjectFormatException)
from .file import GitFile

ZERO_SHA = b"0" * 40

# Header fields for commits
_TREE_HEADER = b"tree"
_PARENT_HEADER = b"parent"
_AUTHOR_HEADER = b"author"
_COMMITTER_HEADER = b"committer"
_ENCODING_HEADER = b"encoding"
_MERGETAG_HEADER = b"mergetag"
_GPGSIG_HEADER = b"gpgsig"

# Header fields for objects
_OBJECT_HEADER = b"object"
_TYPE_HEADER = b"type"
_TAG_HEADER = b"tag"
_TAGGER_HEADER = b"tagger"


S_IFGITLINK = 0o160000


MAX_TIME = 9223372036854775807  # (2**63) - 1 - signed long int max

BEGIN_PGP_SIGNATURE = b"-----BEGIN PGP SIGNATURE-----"


ObjectID = bytes


class EmptyFileException(FileFormatException):
    """An unexpectedly empty file was encountered."""


def S_ISGITLINK(m):
    """Check if a mode indicates a submodule.

    Args:
      m: Mode to check
    Returns: a ``boolean``
    """
    return stat.S_IFMT(m) == S_IFGITLINK


def _decompress(string):
    dcomp = zlib.decompressobj()
    dcomped = dcomp.decompress(string)
    dcomped += dcomp.flush()
    return dcomped


def sha_to_hex(sha):
    """Takes a string and returns the hex of the sha within"""
    hexsha = binascii.hexlify(sha)
    assert len(hexsha) == 40, "Incorrect length of sha1 string: %r" % hexsha
    return hexsha


def hex_to_sha(hex):
    """Takes a hex sha and returns a binary sha"""
    assert len(hex) == 40, "Incorrect length of hexsha: %s" % hex
    try:
        return binascii.unhexlify(hex)
    except TypeError as exc:
        if not isinstance(hex, bytes):
            raise
        raise ValueError(exc.args[0]) from exc


def valid_hexsha(hex):
    if len(hex) != 40:
        return False
    try:
        binascii.unhexlify(hex)
    except (TypeError, binascii.Error):
        return False
    else:
        return True


def hex_to_filename(path, hex):
    """Takes a hex sha and returns its filename relative to the given path."""
    # os.path.join accepts bytes or unicode, but all args must be of the same
    # type. Make sure that hex which is expected to be bytes, is the same type
    # as path.
    if type(path) != type(hex) and getattr(path, "encode", None) is not None:
        hex = hex.decode("ascii")
    dir = hex[:2]
    file = hex[2:]
    # Check from object dir
    return os.path.join(path, dir, file)


def filename_to_hex(filename):
    """Takes an object filename and returns its corresponding hex sha."""
    # grab the last (up to) two path components
    names = filename.rsplit(os.path.sep, 2)[-2:]
    errmsg = "Invalid object filename: %s" % filename
    assert len(names) == 2, errmsg
    base, rest = names
    assert len(base) == 2 and len(rest) == 38, errmsg
    hex = (base + rest).encode("ascii")
    hex_to_sha(hex)
    return hex


def object_header(num_type: int, length: int) -> bytes:
    """Return an object header for the given numeric type and text length."""
    cls = object_class(num_type)
    if cls is None:
        raise AssertionError("unsupported class type num: %d" % num_type)
    return cls.type_name + b" " + str(length).encode("ascii") + b"\0"


def serializable_property(name: str, docstring: Optional[str] = None):
    """A property that helps tracking whether serialization is necessary."""

    def set(obj, value):
        setattr(obj, "_" + name, value)
        obj._needs_serialization = True

    def get(obj):
        return getattr(obj, "_" + name)

    return property(get, set, doc=docstring)


def object_class(type: Union[bytes, int]) -> Optional[Type["ShaFile"]]:
    """Get the object class corresponding to the given type.

    Args:
      type: Either a type name string or a numeric type.
    Returns: The ShaFile subclass corresponding to the given type, or None if
        type is not a valid type name/number.
    """
    return _TYPE_MAP.get(type, None)


def check_hexsha(hex, error_msg):
    """Check if a string is a valid hex sha string.

    Args:
      hex: Hex string to check
      error_msg: Error message to use in exception
    Raises:
      ObjectFormatException: Raised when the string is not valid
    """
    if not valid_hexsha(hex):
        raise ObjectFormatException("{} {}".format(error_msg, hex))


def check_identity(identity: bytes, error_msg: str) -> None:
    """Check if the specified identity is valid.

    This will raise an exception if the identity is not valid.

    Args:
      identity: Identity string
      error_msg: Error message to use in exception
    """
    email_start = identity.find(b'<')
    email_end = identity.find(b'>')
    if not all([
        email_start >= 1,
        identity[email_start - 1] == b' '[0],
        identity.find(b'<', email_start + 1) == -1,
        email_end == len(identity) - 1,
        b'\0' not in identity,
        b'\n' not in identity,
    ]):
        raise ObjectFormatException(error_msg)


def check_time(time_seconds):
    """Check if the specified time is not prone to overflow error.

    This will raise an exception if the time is not valid.

    Args:
      time_seconds: time in seconds

    """
    # Prevent overflow error
    if time_seconds > MAX_TIME:
        raise ObjectFormatException("Date field should not exceed %s" % MAX_TIME)


def git_line(*items):
    """Formats items into a space separated line."""
    return b" ".join(items) + b"\n"


class FixedSha:
    """SHA object that behaves like hashlib's but is given a fixed value."""

    __slots__ = ("_hexsha", "_sha")

    def __init__(self, hexsha):
        if getattr(hexsha, "encode", None) is not None:
            hexsha = hexsha.encode("ascii")
        if not isinstance(hexsha, bytes):
            raise TypeError("Expected bytes for hexsha, got %r" % hexsha)
        self._hexsha = hexsha
        self._sha = hex_to_sha(hexsha)

    def digest(self) -> bytes:
        """Return the raw SHA digest."""
        return self._sha

    def hexdigest(self) -> str:
        """Return the hex SHA digest."""
        return self._hexsha.decode("ascii")


class ShaFile:
    """A git SHA file."""

    __slots__ = ("_chunked_text", "_sha", "_needs_serialization")

    _needs_serialization: bool
    type_name: bytes
    type_num: int
    _chunked_text: Optional[List[bytes]]
    _sha: Union[FixedSha, None, HASH]

    @staticmethod
    def _parse_legacy_object_header(magic, f: BinaryIO) -> "ShaFile":
        """Parse a legacy object, creating it but not reading the file."""
        bufsize = 1024
        decomp = zlib.decompressobj()
        header = decomp.decompress(magic)
        start = 0
        end = -1
        while end < 0:
            extra = f.read(bufsize)
            header += decomp.decompress(extra)
            magic += extra
            end = header.find(b"\0", start)
            start = len(header)
        header = header[:end]
        type_name, size = header.split(b" ", 1)
        try:
            int(size)  # sanity check
        except ValueError as exc:
            raise ObjectFormatException(
                "Object size not an integer: %s" % exc) from exc
        obj_class = object_class(type_name)
        if not obj_class:
            raise ObjectFormatException("Not a known type: %s" % type_name.decode('ascii'))
        return obj_class()

    def _parse_legacy_object(self, map) -> None:
        """Parse a legacy object, setting the raw string."""
        text = _decompress(map)
        header_end = text.find(b"\0")
        if header_end < 0:
            raise ObjectFormatException("Invalid object header, no \\0")
        self.set_raw_string(text[header_end + 1 :])

    def as_legacy_object_chunks(
            self, compression_level: int = -1) -> Iterator[bytes]:
        """Return chunks representing the object in the experimental format.

        Returns: List of strings
        """
        compobj = zlib.compressobj(compression_level)
        yield compobj.compress(self._header())
        for chunk in self.as_raw_chunks():
            yield compobj.compress(chunk)
        yield compobj.flush()

    def as_legacy_object(self, compression_level: int = -1) -> bytes:
        """Return string representing the object in the experimental format."""
        return b"".join(
            self.as_legacy_object_chunks(compression_level=compression_level)
        )

    def as_raw_chunks(self) -> List[bytes]:
        """Return chunks with serialization of the object.

        Returns: List of strings, not necessarily one per line
        """
        if self._needs_serialization:
            self._sha = None
            self._chunked_text = self._serialize()
            self._needs_serialization = False
        return self._chunked_text  # type: ignore

    def as_raw_string(self) -> bytes:
        """Return raw string with serialization of the object.

        Returns: String object
        """
        return b"".join(self.as_raw_chunks())

    def __bytes__(self) -> bytes:
        """Return raw string serialization of this object."""
        return self.as_raw_string()

    def __hash__(self):
        """Return unique hash for this object."""
        return hash(self.id)

    def as_pretty_string(self) -> bytes:
        """Return a string representing this object, fit for display."""
        return self.as_raw_string()

    def set_raw_string(
            self, text: bytes, sha: Optional[ObjectID] = None) -> None:
        """Set the contents of this object from a serialized string."""
        if not isinstance(text, bytes):
            raise TypeError("Expected bytes for text, got %r" % text)
        self.set_raw_chunks([text], sha)

    def set_raw_chunks(
            self, chunks: List[bytes],
            sha: Optional[ObjectID] = None) -> None:
        """Set the contents of this object from a list of chunks."""
        self._chunked_text = chunks
        self._deserialize(chunks)
        if sha is None:
            self._sha = None
        else:
            self._sha = FixedSha(sha)  # type: ignore
        self._needs_serialization = False

    @staticmethod
    def _parse_object_header(magic, f):
        """Parse a new style object, creating it but not reading the file."""
        num_type = (ord(magic[0:1]) >> 4) & 7
        obj_class = object_class(num_type)
        if not obj_class:
            raise ObjectFormatException("Not a known type %d" % num_type)
        return obj_class()

    def _parse_object(self, map) -> None:
        """Parse a new style object, setting self._text."""
        # skip type and size; type must have already been determined, and
        # we trust zlib to fail if it's otherwise corrupted
        byte = ord(map[0:1])
        used = 1
        while (byte & 0x80) != 0:
            byte = ord(map[used : used + 1])
            used += 1
        raw = map[used:]
        self.set_raw_string(_decompress(raw))

    @classmethod
    def _is_legacy_object(cls, magic: bytes) -> bool:
        b0 = ord(magic[0:1])
        b1 = ord(magic[1:2])
        word = (b0 << 8) + b1
        return (b0 & 0x8F) == 0x08 and (word % 31) == 0

    @classmethod
    def _parse_file(cls, f):
        map = f.read()
        if not map:
            raise EmptyFileException("Corrupted empty file detected")

        if cls._is_legacy_object(map):
            obj = cls._parse_legacy_object_header(map, f)
            obj._parse_legacy_object(map)
        else:
            obj = cls._parse_object_header(map, f)
            obj._parse_object(map)
        return obj

    def __init__(self):
        """Don't call this directly"""
        self._sha = None
        self._chunked_text = []
        self._needs_serialization = True

    def _deserialize(self, chunks: List[bytes]) -> None:
        raise NotImplementedError(self._deserialize)

    def _serialize(self) -> List[bytes]:
        raise NotImplementedError(self._serialize)

    @classmethod
    def from_path(cls, path):
        """Open a SHA file from disk."""
        with GitFile(path, "rb") as f:
            return cls.from_file(f)

    @classmethod
    def from_file(cls, f):
        """Get the contents of a SHA file on disk."""
        try:
            obj = cls._parse_file(f)
            obj._sha = None
            return obj
        except (IndexError, ValueError) as exc:
            raise ObjectFormatException("invalid object header") from exc

    @staticmethod
    def from_raw_string(type_num, string, sha=None):
        """Creates an object of the indicated type from the raw string given.

        Args:
          type_num: The numeric type of the object.
          string: The raw uncompressed contents.
          sha: Optional known sha for the object
        """
        cls = object_class(type_num)
        if cls is None:
            raise AssertionError("unsupported class type num: %d" % type_num)
        obj = cls()
        obj.set_raw_string(string, sha)
        return obj

    @staticmethod
    def from_raw_chunks(
            type_num: int, chunks: List[bytes],
            sha: Optional[ObjectID] = None):
        """Creates an object of the indicated type from the raw chunks given.

        Args:
          type_num: The numeric type of the object.
          chunks: An iterable of the raw uncompressed contents.
          sha: Optional known sha for the object
        """
        cls = object_class(type_num)
        if cls is None:
            raise AssertionError("unsupported class type num: %d" % type_num)
        obj = cls()
        obj.set_raw_chunks(chunks, sha)
        return obj

    @classmethod
    def from_string(cls, string):
        """Create a ShaFile from a string."""
        obj = cls()
        obj.set_raw_string(string)
        return obj

    def _check_has_member(self, member, error_msg):
        """Check that the object has a given member variable.

        Args:
          member: the member variable to check for
          error_msg: the message for an error if the member is missing
        Raises:
          ObjectFormatException: with the given error_msg if member is
            missing or is None
        """
        if getattr(self, member, None) is None:
            raise ObjectFormatException(error_msg)

    def check(self) -> None:
        """Check this object for internal consistency.

        Raises:
          ObjectFormatException: if the object is malformed in some way
          ChecksumMismatch: if the object was created with a SHA that does
            not match its contents
        """
        # TODO: if we find that error-checking during object parsing is a
        # performance bottleneck, those checks should be moved to the class's
        # check() method during optimization so we can still check the object
        # when necessary.
        old_sha = self.id
        try:
            self._deserialize(self.as_raw_chunks())
            self._sha = None
            new_sha = self.id
        except Exception as exc:
            raise ObjectFormatException(exc) from exc
        if old_sha != new_sha:
            raise ChecksumMismatch(new_sha, old_sha)

    def _header(self):
        return object_header(self.type_num, self.raw_length())

    def raw_length(self) -> int:
        """Returns the length of the raw string of this object."""
        return sum(map(len, self.as_raw_chunks()))

    def sha(self):
        """The SHA1 object that is the name of this object."""
        if self._sha is None or self._needs_serialization:
            # this is a local because as_raw_chunks() overwrites self._sha
            new_sha = sha1()
            new_sha.update(self._header())
            for chunk in self.as_raw_chunks():
                new_sha.update(chunk)
            self._sha = new_sha
        return self._sha

    def copy(self):
        """Create a new copy of this SHA1 object from its raw string"""
        obj_class = object_class(self.type_num)
        if obj_class is None:
            raise AssertionError('invalid type num %d' % self.type_num)
        return obj_class.from_raw_string(self.type_num, self.as_raw_string(), self.id)

    @property
    def id(self):
        """The hex SHA of this object."""
        return self.sha().hexdigest().encode("ascii")

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.id)

    def __ne__(self, other):
        """Check whether this object does not match the other."""
        return not isinstance(other, ShaFile) or self.id != other.id

    def __eq__(self, other):
        """Return True if the SHAs of the two objects match."""
        return isinstance(other, ShaFile) and self.id == other.id

    def __lt__(self, other):
        """Return whether SHA of this object is less than the other."""
        if not isinstance(other, ShaFile):
            raise TypeError
        return self.id < other.id

    def __le__(self, other):
        """Check whether SHA of this object is less than or equal to the other."""
        if not isinstance(other, ShaFile):
            raise TypeError
        return self.id <= other.id


class Blob(ShaFile):
    """A Git Blob object."""

    __slots__ = ()

    type_name = b"blob"
    type_num = 3

    _chunked_text: List[bytes]

    def __init__(self):
        super().__init__()
        self._chunked_text = []
        self._needs_serialization = False

    def _get_data(self):
        return self.as_raw_string()

    def _set_data(self, data):
        self.set_raw_string(data)

    data = property(
        _get_data, _set_data, doc="The text contained within the blob object."
    )

    def _get_chunked(self):
        return self._chunked_text

    def _set_chunked(self, chunks: List[bytes]):
        self._chunked_text = chunks

    def _serialize(self):
        return self._chunked_text

    def _deserialize(self, chunks):
        self._chunked_text = chunks

    chunked = property(
        _get_chunked,
        _set_chunked,
        doc="The text in the blob object, as chunks (not necessarily lines)",
    )

    @classmethod
    def from_path(cls, path):
        blob = ShaFile.from_path(path)
        if not isinstance(blob, cls):
            raise NotBlobError(path)
        return blob

    def check(self):
        """Check this object for internal consistency.

        Raises:
          ObjectFormatException: if the object is malformed in some way
        """
        super().check()

    def splitlines(self) -> List[bytes]:
        """Return list of lines in this blob.

        This preserves the original line endings.
        """
        chunks = self.chunked
        if not chunks:
            return []
        if len(chunks) == 1:
            return chunks[0].splitlines(True)
        remaining = None
        ret = []
        for chunk in chunks:
            lines = chunk.splitlines(True)
            if len(lines) > 1:
                ret.append((remaining or b"") + lines[0])
                ret.extend(lines[1:-1])
                remaining = lines[-1]
            elif len(lines) == 1:
                if remaining is None:
                    remaining = lines.pop()
                else:
                    remaining += lines.pop()
        if remaining is not None:
            ret.append(remaining)
        return ret


def _parse_message(chunks: Iterable[bytes]) -> Iterator[Tuple[Optional[bytes], Optional[bytes]]]:
    """Parse a message with a list of fields and a body.

    Args:
      chunks: the raw chunks of the tag or commit object.
    Returns: iterator of tuples of (field, value), one per header line, in the
        order read from the text, possibly including duplicates. Includes a
        field named None for the freeform tag/commit text.
    """
    f = BytesIO(b"".join(chunks))
    k = None
    v = b""
    eof = False

    def _strip_last_newline(value):
        """Strip the last newline from value"""
        if value and value.endswith(b"\n"):
            return value[:-1]
        return value

    # Parse the headers
    #
    # Headers can contain newlines. The next line is indented with a space.
    # We store the latest key as 'k', and the accumulated value as 'v'.
    for line in f:
        if line.startswith(b" "):
            # Indented continuation of the previous line
            v += line[1:]
        else:
            if k is not None:
                # We parsed a new header, return its value
                yield (k, _strip_last_newline(v))
            if line == b"\n":
                # Empty line indicates end of headers
                break
            (k, v) = line.split(b" ", 1)

    else:
        # We reached end of file before the headers ended. We still need to
        # return the previous header, then we need to return a None field for
        # the text.
        eof = True
        if k is not None:
            yield (k, _strip_last_newline(v))
        yield (None, None)

    if not eof:
        # We didn't reach the end of file while parsing headers. We can return
        # the rest of the file as a message.
        yield (None, f.read())

    f.close()


def _format_message(headers, body):
    for field, value in headers:
        lines = value.split(b"\n")
        yield git_line(field, lines[0])
        for line in lines[1:]:
            yield b" " + line + b"\n"
    if body:
        yield b"\n"  # There must be a new line after the headers
        yield body


class Tag(ShaFile):
    """A Git Tag object."""

    type_name = b"tag"
    type_num = 4

    __slots__ = (
        "_tag_timezone_neg_utc",
        "_name",
        "_object_sha",
        "_object_class",
        "_tag_time",
        "_tag_timezone",
        "_tagger",
        "_message",
        "_signature",
    )

    _tagger: Optional[bytes]

    def __init__(self):
        super().__init__()
        self._tagger = None
        self._tag_time = None
        self._tag_timezone = None
        self._tag_timezone_neg_utc = False
        self._signature = None

    @classmethod
    def from_path(cls, filename):
        tag = ShaFile.from_path(filename)
        if not isinstance(tag, cls):
            raise NotTagError(filename)
        return tag

    def check(self):
        """Check this object for internal consistency.

        Raises:
          ObjectFormatException: if the object is malformed in some way
        """
        super().check()
        assert self._chunked_text is not None
        self._check_has_member("_object_sha", "missing object sha")
        self._check_has_member("_object_class", "missing object type")
        self._check_has_member("_name", "missing tag name")

        if not self._name:
            raise ObjectFormatException("empty tag name")

        check_hexsha(self._object_sha, "invalid object sha")

        if self._tagger is not None:
            check_identity(self._tagger, "invalid tagger")

        self._check_has_member("_tag_time", "missing tag time")
        check_time(self._tag_time)

        last = None
        for field, _ in _parse_message(self._chunked_text):
            if field == _OBJECT_HEADER and last is not None:
                raise ObjectFormatException("unexpected object")
            elif field == _TYPE_HEADER and last != _OBJECT_HEADER:
                raise ObjectFormatException("unexpected type")
            elif field == _TAG_HEADER and last != _TYPE_HEADER:
                raise ObjectFormatException("unexpected tag name")
            elif field == _TAGGER_HEADER and last != _TAG_HEADER:
                raise ObjectFormatException("unexpected tagger")
            last = field

    def _serialize(self):
        headers = []
        headers.append((_OBJECT_HEADER, self._object_sha))
        headers.append((_TYPE_HEADER, self._object_class.type_name))
        headers.append((_TAG_HEADER, self._name))
        if self._tagger:
            if self._tag_time is None:
                headers.append((_TAGGER_HEADER, self._tagger))
            else:
                headers.append((_TAGGER_HEADER, format_time_entry(
                    self._tagger, self._tag_time,
                    (self._tag_timezone, self._tag_timezone_neg_utc))))

        if self.message is None and self._signature is None:
            body = None
        else:
            body = (self.message or b"") + (self._signature or b"")
        return list(_format_message(headers, body))

    def _deserialize(self, chunks):
        """Grab the metadata attached to the tag"""
        self._tagger = None
        self._tag_time = None
        self._tag_timezone = None
        self._tag_timezone_neg_utc = False
        for field, value in _parse_message(chunks):
            if field == _OBJECT_HEADER:
                self._object_sha = value
            elif field == _TYPE_HEADER:
                assert isinstance(value, bytes)
                obj_class = object_class(value)
                if not obj_class:
                    raise ObjectFormatException("Not a known type: %s" % value)
                self._object_class = obj_class
            elif field == _TAG_HEADER:
                self._name = value
            elif field == _TAGGER_HEADER:
                (
                    self._tagger,
                    self._tag_time,
                    (self._tag_timezone, self._tag_timezone_neg_utc),
                ) = parse_time_entry(value)
            elif field is None:
                if value is None:
                    self._message = None
                    self._signature = None
                else:
                    try:
                        sig_idx = value.index(BEGIN_PGP_SIGNATURE)
                    except ValueError:
                        self._message = value
                        self._signature = None
                    else:
                        self._message = value[:sig_idx]
                        self._signature = value[sig_idx:]
            else:
                raise ObjectFormatException("Unknown field %s" % field)

    def _get_object(self):
        """Get the object pointed to by this tag.

        Returns: tuple of (object class, sha).
        """
        return (self._object_class, self._object_sha)

    def _set_object(self, value):
        (self._object_class, self._object_sha) = value
        self._needs_serialization = True

    object = property(_get_object, _set_object)

    name = serializable_property("name", "The name of this tag")
    tagger = serializable_property(
        "tagger", "Returns the name of the person who created this tag"
    )
    tag_time = serializable_property(
        "tag_time",
        "The creation timestamp of the tag.  As the number of seconds "
        "since the epoch",
    )
    tag_timezone = serializable_property(
        "tag_timezone", "The timezone that tag_time is in."
    )
    message = serializable_property("message", "the message attached to this tag")

    signature = serializable_property("signature", "Optional detached GPG signature")

    def sign(self, keyid: Optional[str] = None):
        import gpg
        with gpg.Context(armor=True) as c:
            if keyid is not None:
                key = c.get_key(keyid)
                with gpg.Context(armor=True, signers=[key]) as ctx:
                    self.signature, unused_result = ctx.sign(
                        self.as_raw_string(),
                        mode=gpg.constants.sig.mode.DETACH,
                    )
            else:
                self.signature, unused_result = c.sign(
                    self.as_raw_string(), mode=gpg.constants.sig.mode.DETACH
                )

    def verify(self, keyids: Optional[Iterable[str]] = None) -> None:
        """Verify GPG signature for this tag (if it is signed).

        Args:
          keyids: Optional iterable of trusted keyids for this tag.
            If this tag is not signed by any key in keyids verification will
            fail. If not specified, this function only verifies that the tag
            has a valid signature.

        Raises:
          gpg.errors.BadSignatures: if GPG signature verification fails
          gpg.errors.MissingSignatures: if tag was not signed by a key
            specified in keyids
        """
        if self._signature is None:
            return

        import gpg

        with gpg.Context() as ctx:
            data, result = ctx.verify(
                self.as_raw_string()[: -len(self._signature)],
                signature=self._signature,
            )
            if keyids:
                keys = [
                    ctx.get_key(key)
                    for key in keyids
                ]
                for key in keys:
                    for subkey in keys:
                        for sig in result.signatures:
                            if subkey.can_sign and subkey.fpr == sig.fpr:
                                return
                raise gpg.errors.MissingSignatures(
                    result, keys, results=(data, result)
                )


class TreeEntry(namedtuple("TreeEntry", ["path", "mode", "sha"])):
    """Named tuple encapsulating a single tree entry."""

    def in_path(self, path: bytes):
        """Return a copy of this entry with the given path prepended."""
        if not isinstance(self.path, bytes):
            raise TypeError("Expected bytes for path, got %r" % path)
        return TreeEntry(posixpath.join(path, self.path), self.mode, self.sha)


def parse_tree(text, strict=False):
    """Parse a tree text.

    Args:
      text: Serialized text to parse
    Returns: iterator of tuples of (name, mode, sha)
    Raises:
      ObjectFormatException: if the object was malformed in some way
    """
    count = 0
    length = len(text)
    while count < length:
        mode_end = text.index(b" ", count)
        mode_text = text[count:mode_end]
        if strict and mode_text.startswith(b"0"):
            raise ObjectFormatException("Invalid mode '%s'" % mode_text)
        try:
            mode = int(mode_text, 8)
        except ValueError as exc:
            raise ObjectFormatException(
                "Invalid mode '%s'" % mode_text) from exc
        name_end = text.index(b"\0", mode_end)
        name = text[mode_end + 1 : name_end]
        count = name_end + 21
        sha = text[name_end + 1 : count]
        if len(sha) != 20:
            raise ObjectFormatException("Sha has invalid length")
        hexsha = sha_to_hex(sha)
        yield (name, mode, hexsha)


def serialize_tree(items):
    """Serialize the items in a tree to a text.

    Args:
      items: Sorted iterable over (name, mode, sha) tuples
    Returns: Serialized tree text as chunks
    """
    for name, mode, hexsha in items:
        yield (
            ("%04o" % mode).encode("ascii") + b" " + name + b"\0" + hex_to_sha(hexsha)
        )


def sorted_tree_items(entries, name_order: bool):
    """Iterate over a tree entries dictionary.

    Args:
      name_order: If True, iterate entries in order of their name. If
        False, iterate entries in tree order, that is, treat subtree entries as
        having '/' appended.
      entries: Dictionary mapping names to (mode, sha) tuples
    Returns: Iterator over (name, mode, hexsha)
    """
    if name_order:
        key_func = key_entry_name_order
    else:
        key_func = key_entry
    for name, entry in sorted(entries.items(), key=key_func):
        mode, hexsha = entry
        # Stricter type checks than normal to mirror checks in the C version.
        mode = int(mode)
        if not isinstance(hexsha, bytes):
            raise TypeError("Expected bytes for SHA, got %r" % hexsha)
        yield TreeEntry(name, mode, hexsha)


def key_entry(entry) -> bytes:
    """Sort key for tree entry.

    Args:
      entry: (name, value) tuple
    """
    (name, value) = entry
    if stat.S_ISDIR(value[0]):
        name += b"/"
    return name


def key_entry_name_order(entry):
    """Sort key for tree entry in name order."""
    return entry[0]


def pretty_format_tree_entry(name, mode, hexsha, encoding="utf-8") -> str:
    """Pretty format tree entry.

    Args:
      name: Name of the directory entry
      mode: Mode of entry
      hexsha: Hexsha of the referenced object
    Returns: string describing the tree entry
    """
    if mode & stat.S_IFDIR:
        kind = "tree"
    else:
        kind = "blob"
    return "{:04o} {} {}\t{}\n".format(
        mode,
        kind,
        hexsha.decode("ascii"),
        name.decode(encoding, "replace"),
    )


class SubmoduleEncountered(Exception):
    """A submodule was encountered while resolving a path."""

    def __init__(self, path, sha):
        self.path = path
        self.sha = sha


class Tree(ShaFile):
    """A Git tree object"""

    type_name = b"tree"
    type_num = 2

    __slots__ = "_entries"

    def __init__(self):
        super().__init__()
        self._entries = {}

    @classmethod
    def from_path(cls, filename):
        tree = ShaFile.from_path(filename)
        if not isinstance(tree, cls):
            raise NotTreeError(filename)
        return tree

    def __contains__(self, name):
        return name in self._entries

    def __getitem__(self, name):
        return self._entries[name]

    def __setitem__(self, name, value):
        """Set a tree entry by name.

        Args:
          name: The name of the entry, as a string.
          value: A tuple of (mode, hexsha), where mode is the mode of the
            entry as an integral type and hexsha is the hex SHA of the entry as
            a string.
        """
        mode, hexsha = value
        self._entries[name] = (mode, hexsha)
        self._needs_serialization = True

    def __delitem__(self, name):
        del self._entries[name]
        self._needs_serialization = True

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def add(self, name, mode, hexsha):
        """Add an entry to the tree.

        Args:
          mode: The mode of the entry as an integral type. Not all
            possible modes are supported by git; see check() for details.
          name: The name of the entry, as a string.
          hexsha: The hex SHA of the entry as a string.
        """
        self._entries[name] = mode, hexsha
        self._needs_serialization = True

    def iteritems(self, name_order=False):
        """Iterate over entries.

        Args:
          name_order: If True, iterate in name order instead of tree
            order.
        Returns: Iterator over (name, mode, sha) tuples
        """
        return sorted_tree_items(self._entries, name_order)

    def items(self):
        """Return the sorted entries in this tree.

        Returns: List with (name, mode, sha) tuples
        """
        return list(self.iteritems())

    def _deserialize(self, chunks):
        """Grab the entries in the tree"""
        try:
            parsed_entries = parse_tree(b"".join(chunks))
        except ValueError as exc:
            raise ObjectFormatException(exc) from exc
        # TODO: list comprehension is for efficiency in the common (small)
        # case; if memory efficiency in the large case is a concern, use a
        # genexp.
        self._entries = {n: (m, s) for n, m, s in parsed_entries}

    def check(self):
        """Check this object for internal consistency.

        Raises:
          ObjectFormatException: if the object is malformed in some way
        """
        super().check()
        assert self._chunked_text is not None
        last = None
        allowed_modes = (
            stat.S_IFREG | 0o755,
            stat.S_IFREG | 0o644,
            stat.S_IFLNK,
            stat.S_IFDIR,
            S_IFGITLINK,
            # TODO: optionally exclude as in git fsck --strict
            stat.S_IFREG | 0o664,
        )
        for name, mode, sha in parse_tree(b"".join(self._chunked_text), True):
            check_hexsha(sha, "invalid sha %s" % sha)
            if b"/" in name or name in (b"", b".", b"..", b".git"):
                raise ObjectFormatException(
                    "invalid name %s" % name.decode("utf-8", "replace")
                )

            if mode not in allowed_modes:
                raise ObjectFormatException("invalid mode %06o" % mode)

            entry = (name, (mode, sha))
            if last:
                if key_entry(last) > key_entry(entry):
                    raise ObjectFormatException("entries not sorted")
                if name == last[0]:
                    raise ObjectFormatException("duplicate entry %s" % name)
            last = entry

    def _serialize(self):
        return list(serialize_tree(self.iteritems()))

    def as_pretty_string(self):
        text: List[str] = []
        for name, mode, hexsha in self.iteritems():
            text.append(pretty_format_tree_entry(name, mode, hexsha))
        return "".join(text)

    def lookup_path(self, lookup_obj, path):
        """Look up an object in a Git tree.

        Args:
          lookup_obj: Callback for retrieving object by SHA1
          path: Path to lookup
        Returns: A tuple of (mode, SHA) of the resulting path.
        """
        parts = path.split(b"/")
        sha = self.id
        mode = None
        for i, p in enumerate(parts):
            if not p:
                continue
            if mode is not None and S_ISGITLINK(mode):
                raise SubmoduleEncountered(b'/'.join(parts[:i]), sha)
            obj = lookup_obj(sha)
            if not isinstance(obj, Tree):
                raise NotTreeError(sha)
            mode, sha = obj[p]
        return mode, sha


def parse_timezone(text):
    """Parse a timezone text fragment (e.g. '+0100').

    Args:
      text: Text to parse.
    Returns: Tuple with timezone as seconds difference to UTC
        and a boolean indicating whether this was a UTC timezone
        prefixed with a negative sign (-0000).
    """
    # cgit parses the first character as the sign, and the rest
    #  as an integer (using strtol), which could also be negative.
    #  We do the same for compatibility. See #697828.
    if not text[0] in b"+-":
        raise ValueError("Timezone must start with + or - (%(text)s)" % vars())
    sign = text[:1]
    offset = int(text[1:])
    if sign == b"-":
        offset = -offset
    unnecessary_negative_timezone = offset >= 0 and sign == b"-"
    signum = (offset < 0) and -1 or 1
    offset = abs(offset)
    hours = int(offset / 100)
    minutes = offset % 100
    return (
        signum * (hours * 3600 + minutes * 60),
        unnecessary_negative_timezone,
    )


def format_timezone(offset, unnecessary_negative_timezone=False):
    """Format a timezone for Git serialization.

    Args:
      offset: Timezone offset as seconds difference to UTC
      unnecessary_negative_timezone: Whether to use a minus sign for
        UTC or positive timezones (-0000 and --700 rather than +0000 / +0700).
    """
    if offset % 60 != 0:
        raise ValueError("Unable to handle non-minute offset.")
    if offset < 0 or unnecessary_negative_timezone:
        sign = "-"
        offset = -offset
    else:
        sign = "+"
    return ("%c%02d%02d" % (sign, offset / 3600, (offset / 60) % 60)).encode("ascii")


def parse_time_entry(value):
    """Parse event

    Args:
      value: Bytes representing a git commit/tag line
    Raises:
      ObjectFormatException in case of parsing error (malformed
      field date)
    Returns: Tuple of (author, time, (timezone, timezone_neg_utc))
    """
    try:
        sep = value.rindex(b"> ")
    except ValueError:
        return (value, None, (None, False))
    try:
        person = value[0 : sep + 1]
        rest = value[sep + 2 :]
        timetext, timezonetext = rest.rsplit(b" ", 1)
        time = int(timetext)
        timezone, timezone_neg_utc = parse_timezone(timezonetext)
    except ValueError as exc:
        raise ObjectFormatException(exc) from exc
    return person, time, (timezone, timezone_neg_utc)


def format_time_entry(person, time, timezone_info):
    """Format an event
    """
    (timezone, timezone_neg_utc) = timezone_info
    return b" ".join([
        person,
        str(time).encode("ascii"),
        format_timezone(timezone, timezone_neg_utc)])


def parse_commit(chunks):
    """Parse a commit object from chunks.

    Args:
      chunks: Chunks to parse
    Returns: Tuple of (tree, parents, author_info, commit_info,
        encoding, mergetag, gpgsig, message, extra)
    """
    warnings.warn('parse_commit will be removed in 0.22', DeprecationWarning)
    parents = []
    extra = []
    tree = None
    author_info = (None, None, (None, None))
    commit_info = (None, None, (None, None))
    encoding = None
    mergetag = []
    message = None
    gpgsig = None

    for field, value in _parse_message(chunks):
        # TODO(jelmer): Enforce ordering
        if field == _TREE_HEADER:
            tree = value
        elif field == _PARENT_HEADER:
            parents.append(value)
        elif field == _AUTHOR_HEADER:
            author_info = parse_time_entry(value)
        elif field == _COMMITTER_HEADER:
            commit_info = parse_time_entry(value)
        elif field == _ENCODING_HEADER:
            encoding = value
        elif field == _MERGETAG_HEADER:
            mergetag.append(Tag.from_string(value + b"\n"))
        elif field == _GPGSIG_HEADER:
            gpgsig = value
        elif field is None:
            message = value
        else:
            extra.append((field, value))
    return (
        tree,
        parents,
        author_info,
        commit_info,
        encoding,
        mergetag,
        gpgsig,
        message,
        extra,
    )


class Commit(ShaFile):
    """A git commit object"""

    type_name = b"commit"
    type_num = 1

    __slots__ = (
        "_parents",
        "_encoding",
        "_extra",
        "_author_timezone_neg_utc",
        "_commit_timezone_neg_utc",
        "_commit_time",
        "_author_time",
        "_author_timezone",
        "_commit_timezone",
        "_author",
        "_committer",
        "_tree",
        "_message",
        "_mergetag",
        "_gpgsig",
    )

    def __init__(self):
        super().__init__()
        self._parents = []
        self._encoding = None
        self._mergetag = []
        self._gpgsig = None
        self._extra = []
        self._author_timezone_neg_utc = False
        self._commit_timezone_neg_utc = False

    @classmethod
    def from_path(cls, path):
        commit = ShaFile.from_path(path)
        if not isinstance(commit, cls):
            raise NotCommitError(path)
        return commit

    def _deserialize(self, chunks):
        self._parents = []
        self._extra = []
        self._tree = None
        author_info = (None, None, (None, None))
        commit_info = (None, None, (None, None))
        self._encoding = None
        self._mergetag = []
        self._message = None
        self._gpgsig = None

        for field, value in _parse_message(chunks):
            # TODO(jelmer): Enforce ordering
            if field == _TREE_HEADER:
                self._tree = value
            elif field == _PARENT_HEADER:
                self._parents.append(value)
            elif field == _AUTHOR_HEADER:
                author_info = parse_time_entry(value)
            elif field == _COMMITTER_HEADER:
                commit_info = parse_time_entry(value)
            elif field == _ENCODING_HEADER:
                self._encoding = value
            elif field == _MERGETAG_HEADER:
                self._mergetag.append(Tag.from_string(value + b"\n"))
            elif field == _GPGSIG_HEADER:
                self._gpgsig = value
            elif field is None:
                self._message = value
            else:
                self._extra.append((field, value))

        (
            self._author,
            self._author_time,
            (self._author_timezone, self._author_timezone_neg_utc),
        ) = author_info
        (
            self._committer,
            self._commit_time,
            (self._commit_timezone, self._commit_timezone_neg_utc),
        ) = commit_info

    def check(self):
        """Check this object for internal consistency.

        Raises:
          ObjectFormatException: if the object is malformed in some way
        """
        super().check()
        assert self._chunked_text is not None
        self._check_has_member("_tree", "missing tree")
        self._check_has_member("_author", "missing author")
        self._check_has_member("_committer", "missing committer")
        self._check_has_member("_author_time", "missing author time")
        self._check_has_member("_commit_time", "missing commit time")

        for parent in self._parents:
            check_hexsha(parent, "invalid parent sha")
        check_hexsha(self._tree, "invalid tree sha")

        check_identity(self._author, "invalid author")
        check_identity(self._committer, "invalid committer")

        check_time(self._author_time)
        check_time(self._commit_time)

        last = None
        for field, _ in _parse_message(self._chunked_text):
            if field == _TREE_HEADER and last is not None:
                raise ObjectFormatException("unexpected tree")
            elif field == _PARENT_HEADER and last not in (
                _PARENT_HEADER,
                _TREE_HEADER,
            ):
                raise ObjectFormatException("unexpected parent")
            elif field == _AUTHOR_HEADER and last not in (
                _TREE_HEADER,
                _PARENT_HEADER,
            ):
                raise ObjectFormatException("unexpected author")
            elif field == _COMMITTER_HEADER and last != _AUTHOR_HEADER:
                raise ObjectFormatException("unexpected committer")
            elif field == _ENCODING_HEADER and last != _COMMITTER_HEADER:
                raise ObjectFormatException("unexpected encoding")
            last = field

        # TODO: optionally check for duplicate parents

    def sign(self, keyid: Optional[str] = None):
        import gpg
        with gpg.Context(armor=True) as c:
            if keyid is not None:
                key = c.get_key(keyid)
                with gpg.Context(armor=True, signers=[key]) as ctx:
                    self.gpgsig, unused_result = ctx.sign(
                        self.as_raw_string(),
                        mode=gpg.constants.sig.mode.DETACH,
                    )
            else:
                self.gpgsig, unused_result = c.sign(
                    self.as_raw_string(), mode=gpg.constants.sig.mode.DETACH
                )

    def verify(self, keyids: Optional[Iterable[str]] = None):
        """Verify GPG signature for this commit (if it is signed).

        Args:
          keyids: Optional iterable of trusted keyids for this commit.
            If this commit is not signed by any key in keyids verification will
            fail. If not specified, this function only verifies that the commit
            has a valid signature.

        Raises:
          gpg.errors.BadSignatures: if GPG signature verification fails
          gpg.errors.MissingSignatures: if commit was not signed by a key
            specified in keyids
        """
        if self._gpgsig is None:
            return

        import gpg

        with gpg.Context() as ctx:
            self_without_gpgsig = self.copy()
            self_without_gpgsig._gpgsig = None
            self_without_gpgsig.gpgsig = None
            data, result = ctx.verify(
                self_without_gpgsig.as_raw_string(),
                signature=self._gpgsig,
            )
            if keyids:
                keys = [
                    ctx.get_key(key)
                    for key in keyids
                ]
                for key in keys:
                    for subkey in keys:
                        for sig in result.signatures:
                            if subkey.can_sign and subkey.fpr == sig.fpr:
                                return
                raise gpg.errors.MissingSignatures(
                    result, keys, results=(data, result)
                )

    def _serialize(self):
        headers = []
        tree_bytes = self._tree.id if isinstance(self._tree, Tree) else self._tree
        headers.append((_TREE_HEADER, tree_bytes))
        for p in self._parents:
            headers.append((_PARENT_HEADER, p))
        headers.append((
            _AUTHOR_HEADER,
            format_time_entry(
                self._author, self._author_time,
                (self._author_timezone, self._author_timezone_neg_utc))))
        headers.append((
            _COMMITTER_HEADER,
            format_time_entry(
                self._committer, self._commit_time,
                (self._commit_timezone, self._commit_timezone_neg_utc))))
        if self.encoding:
            headers.append((_ENCODING_HEADER, self.encoding))
        for mergetag in self.mergetag:
            headers.append((_MERGETAG_HEADER, mergetag.as_raw_string()[:-1]))
        headers.extend(self._extra)
        if self.gpgsig:
            headers.append((_GPGSIG_HEADER, self.gpgsig))
        return list(_format_message(headers, self._message))

    tree = serializable_property("tree", "Tree that is the state of this commit")

    def _get_parents(self):
        """Return a list of parents of this commit."""
        return self._parents

    def _set_parents(self, value):
        """Set a list of parents of this commit."""
        self._needs_serialization = True
        self._parents = value

    parents = property(
        _get_parents,
        _set_parents,
        doc="Parents of this commit, by their SHA1.",
    )

    def _get_extra(self):
        """Return extra settings of this commit."""
        warnings.warn(
            'Commit.extra is deprecated. Use Commit._extra instead.',
            DeprecationWarning, stacklevel=2)
        return self._extra

    extra = property(
        _get_extra,
        doc="Extra header fields not understood (presumably added in a "
        "newer version of git). Kept verbatim so the object can "
        "be correctly reserialized. For private commit metadata, use "
        "pseudo-headers in Commit.message, rather than this field.",
    )

    author = serializable_property("author", "The name of the author of the commit")

    committer = serializable_property(
        "committer", "The name of the committer of the commit"
    )

    message = serializable_property("message", "The commit message")

    commit_time = serializable_property(
        "commit_time",
        "The timestamp of the commit. As the number of seconds since the " "epoch.",
    )

    commit_timezone = serializable_property(
        "commit_timezone", "The zone the commit time is in"
    )

    author_time = serializable_property(
        "author_time",
        "The timestamp the commit was written. As the number of "
        "seconds since the epoch.",
    )

    author_timezone = serializable_property(
        "author_timezone", "Returns the zone the author time is in."
    )

    encoding = serializable_property("encoding", "Encoding of the commit message.")

    mergetag = serializable_property("mergetag", "Associated signed tag.")

    gpgsig = serializable_property("gpgsig", "GPG Signature.")


OBJECT_CLASSES = (
    Commit,
    Tree,
    Blob,
    Tag,
)

_TYPE_MAP: Dict[Union[bytes, int], Type[ShaFile]] = {}

for cls in OBJECT_CLASSES:
    _TYPE_MAP[cls.type_name] = cls
    _TYPE_MAP[cls.type_num] = cls


# Hold on to the pure-python implementations for testing
_parse_tree_py = parse_tree
_sorted_tree_items_py = sorted_tree_items
try:
    # Try to import C versions
    from dulwich._objects import parse_tree, sorted_tree_items  # type: ignore
except ImportError:
    pass
