"""Utilities related to handling / interacting with wheel files."""

import base64
import contextlib
import csv
import hashlib
import io
import os
import re
import sys
from collections import namedtuple
from configparser import ConfigParser
from email.message import Message
from email.parser import FeedParser
from email.policy import compat32
from typing import (
    TYPE_CHECKING,
    BinaryIO,
    Callable,
    Iterable,
    Iterator,
    NewType,
    Optional,
    Tuple,
    Union,
    cast,
)

from installer.records import RecordEntry

if TYPE_CHECKING:
    from installer.scripts import LauncherKind, ScriptSection

Scheme = NewType("Scheme", str)
AllSchemes = Tuple[Scheme, ...]

__all__ = [
    "parse_metadata_file",
    "parse_wheel_filename",
    "copyfileobj_with_hashing",
    "get_launcher_kind",
    "fix_shebang",
    "construct_record_file",
    "parse_entrypoints",
    "make_file_executable",
    "WheelFilename",
    "SCHEME_NAMES",
]

# Borrowed from https://github.com/python/cpython/blob/v3.9.1/Lib/shutil.py#L52
_WINDOWS = os.name == "nt"
_COPY_BUFSIZE = 1024 * 1024 if _WINDOWS else 64 * 1024

# According to https://www.python.org/dev/peps/pep-0427/#file-name-convention
_WHEEL_FILENAME_REGEX = re.compile(
    r"""
    ^
    (?P<distribution>.+?)
    -(?P<version>.*?)
    (?:-(?P<build_tag>\d[^-]*?))?
    -(?P<tag>.+?-.+?-.+?)
    \.whl
    $
    """,
    re.VERBOSE | re.UNICODE,
)
WheelFilename = namedtuple(
    "WheelFilename", ["distribution", "version", "build_tag", "tag"]
)

# Adapted from https://github.com/python/importlib_metadata/blob/v3.4.0/importlib_metadata/__init__.py#L90  # noqa
_ENTRYPOINT_REGEX = re.compile(
    r"""
    (?P<module>[\w.]+)\s*
    (:\s*(?P<attrs>[\w.]+))\s*
    (?P<extras>\[.*\])?\s*$
    """,
    re.VERBOSE | re.UNICODE,
)

# According to https://www.python.org/dev/peps/pep-0427/#id7
SCHEME_NAMES = cast(AllSchemes, ("purelib", "platlib", "headers", "scripts", "data"))


def parse_metadata_file(contents: str) -> Message:
    """Parse :pep:`376` ``PKG-INFO``-style metadata files.

    ``METADATA`` and ``WHEEL`` files (as per :pep:`427`) use the same syntax
    and can also be parsed using this function.

    :param contents: The entire contents of the file
    """
    feed_parser = FeedParser(policy=compat32)
    feed_parser.feed(contents)
    return feed_parser.close()


def canonicalize_name(name: str) -> str:
    """Canonicalize a project name according to PEP-503.

    :param name: The project name to canonicalize
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_wheel_filename(filename: str) -> WheelFilename:
    """Parse a wheel filename, into it's various components.

    :param filename: The filename to parse
    """
    wheel_info = _WHEEL_FILENAME_REGEX.match(filename)
    if not wheel_info:
        raise ValueError(f"Not a valid wheel filename: {filename}")
    return WheelFilename(*wheel_info.groups())


def copyfileobj_with_hashing(
    source: BinaryIO,
    dest: BinaryIO,
    hash_algorithm: str,
) -> Tuple[str, int]:
    """Copy a buffer while computing the content's hash and size.

    Copies the source buffer into the destination buffer while computing the
    hash of the contents. Adapted from :any:`shutil.copyfileobj`.

    :param source: buffer holding the source data
    :param dest: destination buffer
    :param hash_algorithm: hashing algorithm

    :return: size, hash digest of the contents
    """
    hasher = hashlib.new(hash_algorithm)
    size = 0
    while True:
        buf = source.read(_COPY_BUFSIZE)
        if not buf:
            break
        hasher.update(buf)
        dest.write(buf)
        size += len(buf)

    return base64.urlsafe_b64encode(hasher.digest()).decode("ascii").rstrip("="), size


def get_launcher_kind() -> "LauncherKind":  # pragma: no cover
    """Get the launcher kind for the current machine."""
    if os.name != "nt":
        return "posix"

    if "amd64" in sys.version.lower():
        return "win-amd64"
    if "(arm64)" in sys.version.lower():
        return "win-arm64"
    if "(arm)" in sys.version.lower():
        return "win-arm"
    if sys.platform == "win32":
        return "win-ia32"

    raise NotImplementedError("Unknown launcher kind for this machine")


@contextlib.contextmanager
def fix_shebang(stream: BinaryIO, interpreter: str) -> Iterator[BinaryIO]:
    """Replace ``#!python`` shebang in a stream with the correct interpreter.

    :param stream: stream to modify
    :param interpreter: "correct interpreter" to substitute the shebang with

    :returns: A context manager, that provides an appropriately modified stream.
    """
    stream.seek(0)
    if stream.read(8) == b"#!python":
        new_stream = io.BytesIO()
        # write our new shebang
        new_stream.write(f"#!{interpreter}\n".encode())
        # copy the rest of the stream
        stream.seek(0)
        stream.readline()  # skip first line
        while True:
            buf = stream.read(_COPY_BUFSIZE)
            if not buf:
                break
            new_stream.write(buf)
        new_stream.seek(0)
        yield new_stream
        new_stream.close()
    else:
        stream.seek(0)
        yield stream


def construct_record_file(
    records: Iterable[Tuple[Scheme, RecordEntry]],
    prefix_for_scheme: Callable[[Scheme], Optional[str]] = lambda _: None,
) -> BinaryIO:
    """Construct a RECORD file.

    :param records:
        ``records`` as passed into :any:`WheelDestination.finalize_installation`
    :param prefix_for_scheme:
        function to get a prefix to add for RECORD entries, within a scheme

    :return: A stream that can be written to file. Must be closed by the caller.
    """
    stream = io.TextIOWrapper(
        io.BytesIO(), encoding="utf-8", write_through=True, newline=""
    )
    writer = csv.writer(stream, delimiter=",", quotechar='"', lineterminator="\n")
    for scheme, record in records:
        writer.writerow(record.to_row(prefix_for_scheme(scheme)))
    stream.seek(0)
    return stream.detach()


def parse_entrypoints(text: str) -> Iterable[Tuple[str, str, str, "ScriptSection"]]:
    """Parse ``entry_points.txt``-style files.

    :param text: entire contents of the file
    :return:
        name of the script, module to use, attribute to call, kind of script (cli / gui)
    """
    # Borrowed from https://github.com/python/importlib_metadata/blob/v3.4.0/importlib_metadata/__init__.py#L115  # noqa
    config = ConfigParser(delimiters="=")
    config.optionxform = str  # type: ignore
    config.read_string(text)

    for section in config.sections():
        if section not in ["console_scripts", "gui_scripts"]:
            continue

        for name, value in config.items(section):
            assert isinstance(name, str)
            match = _ENTRYPOINT_REGEX.match(value)
            assert match

            module = match.group("module")
            assert isinstance(module, str)

            attrs = match.group("attrs")
            # TODO: make this a proper error, which can be caught.
            assert attrs is not None
            assert isinstance(attrs, str)

            script_section = cast("ScriptSection", section[: -len("_scripts")])

            yield name, module, attrs, script_section


def _current_umask() -> int:
    """Get the current umask which involves having to set it temporarily."""
    mask = os.umask(0)
    os.umask(mask)
    return mask


# Borrowed from:
# https://github.com/pypa/pip/blob/0f21fb92/src/pip/_internal/utils/unpacking.py#L93
def make_file_executable(path: Union[str, "os.PathLike[str]"]) -> None:
    """Make the file at the provided path executable."""
    os.chmod(path, (0o777 & ~_current_umask() | 0o111))
