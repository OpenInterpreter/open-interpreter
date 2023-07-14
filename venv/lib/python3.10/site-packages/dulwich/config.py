# config.py - Reading and writing Git config files
# Copyright (C) 2011-2013 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Reading and writing Git configuration files.

TODO:
 * preserve formatting when updating configuration files
 * treat subsection names as case-insensitive for [branch.foo] style
   subsections
"""

import os
import sys
from contextlib import suppress
from typing import (BinaryIO, Iterable, Iterator, KeysView, List,
                    MutableMapping, Optional, Tuple, Union, overload)

from .file import GitFile

SENTINEL = object()


def lower_key(key):
    if isinstance(key, (bytes, str)):
        return key.lower()

    if isinstance(key, Iterable):
        return type(key)(map(lower_key, key))  # type: ignore

    return key


class CaseInsensitiveOrderedMultiDict(MutableMapping):

    def __init__(self):
        self._real = []
        self._keyed = {}

    @classmethod
    def make(cls, dict_in=None):

        if isinstance(dict_in, cls):
            return dict_in

        out = cls()

        if dict_in is None:
            return out

        if not isinstance(dict_in, MutableMapping):
            raise TypeError

        for key, value in dict_in.items():
            out[key] = value

        return out

    def __len__(self):
        return len(self._keyed)

    def keys(self) -> KeysView[Tuple[bytes, ...]]:
        return self._keyed.keys()

    def items(self):
        return iter(self._real)

    def __iter__(self):
        return self._keyed.__iter__()

    def values(self):
        return self._keyed.values()

    def __setitem__(self, key, value):
        self._real.append((key, value))
        self._keyed[lower_key(key)] = value

    def __delitem__(self, key):
        key = lower_key(key)
        del self._keyed[key]
        for i, (actual, unused_value) in reversed(list(enumerate(self._real))):
            if lower_key(actual) == key:
                del self._real[i]

    def __getitem__(self, item):
        return self._keyed[lower_key(item)]

    def get(self, key, default=SENTINEL):
        try:
            return self[key]
        except KeyError:
            pass

        if default is SENTINEL:
            return type(self)()

        return default

    def get_all(self, key):
        key = lower_key(key)
        for actual, value in self._real:
            if lower_key(actual) == key:
                yield value

    def setdefault(self, key, default=SENTINEL):
        try:
            return self[key]
        except KeyError:
            self[key] = self.get(key, default)

        return self[key]


Name = bytes
NameLike = Union[bytes, str]
Section = Tuple[bytes, ...]
SectionLike = Union[bytes, str, Tuple[Union[bytes, str], ...]]
Value = bytes
ValueLike = Union[bytes, str]


class Config:
    """A Git configuration."""

    def get(self, section: SectionLike, name: NameLike) -> Value:
        """Retrieve the contents of a configuration setting.

        Args:
          section: Tuple with section name and optional subsection name
          name: Variable name
        Returns:
          Contents of the setting
        Raises:
          KeyError: if the value is not set
        """
        raise NotImplementedError(self.get)

    def get_multivar(self, section: SectionLike, name: NameLike) -> Iterator[Value]:
        """Retrieve the contents of a multivar configuration setting.

        Args:
          section: Tuple with section name and optional subsection namee
          name: Variable name
        Returns:
          Contents of the setting as iterable
        Raises:
          KeyError: if the value is not set
        """
        raise NotImplementedError(self.get_multivar)

    @overload
    def get_boolean(self, section: SectionLike, name: NameLike, default: bool) -> bool:
        ...

    @overload
    def get_boolean(self, section: SectionLike, name: NameLike) -> Optional[bool]:
        ...

    def get_boolean(
        self, section: SectionLike, name: NameLike, default: Optional[bool] = None
    ) -> Optional[bool]:
        """Retrieve a configuration setting as boolean.

        Args:
          section: Tuple with section name and optional subsection name
          name: Name of the setting, including section and possible
            subsection.
        Returns:
          Contents of the setting
        """
        try:
            value = self.get(section, name)
        except KeyError:
            return default
        if value.lower() == b"true":
            return True
        elif value.lower() == b"false":
            return False
        raise ValueError("not a valid boolean string: %r" % value)

    def set(
        self,
        section: SectionLike,
        name: NameLike,
        value: Union[ValueLike, bool]
    ) -> None:
        """Set a configuration value.

        Args:
          section: Tuple with section name and optional subsection namee
          name: Name of the configuration value, including section
            and optional subsection
          value: value of the setting
        """
        raise NotImplementedError(self.set)

    def items(self, section: SectionLike) -> Iterator[Tuple[Name, Value]]:
        """Iterate over the configuration pairs for a specific section.

        Args:
          section: Tuple with section name and optional subsection namee
        Returns:
          Iterator over (name, value) pairs
        """
        raise NotImplementedError(self.items)

    def sections(self) -> Iterator[Section]:
        """Iterate over the sections.

        Returns: Iterator over section tuples
        """
        raise NotImplementedError(self.sections)

    def has_section(self, name: Section) -> bool:
        """Check if a specified section exists.

        Args:
          name: Name of section to check for
        Returns:
          boolean indicating whether the section exists
        """
        return name in self.sections()


class ConfigDict(Config, MutableMapping[Section, MutableMapping[Name, Value]]):
    """Git configuration stored in a dictionary."""

    def __init__(
        self,
        values: Union[
            MutableMapping[Section, MutableMapping[Name, Value]], None
        ] = None,
        encoding: Union[str, None] = None
    ) -> None:
        """Create a new ConfigDict."""
        if encoding is None:
            encoding = sys.getdefaultencoding()
        self.encoding = encoding
        self._values = CaseInsensitiveOrderedMultiDict.make(values)

    def __repr__(self) -> str:
        return "{}({!r})".format(self.__class__.__name__, self._values)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and other._values == self._values

    def __getitem__(self, key: Section) -> MutableMapping[Name, Value]:
        return self._values.__getitem__(key)

    def __setitem__(
        self,
        key: Section,
        value: MutableMapping[Name, Value]
    ) -> None:
        return self._values.__setitem__(key, value)

    def __delitem__(self, key: Section) -> None:
        return self._values.__delitem__(key)

    def __iter__(self) -> Iterator[Section]:
        return self._values.__iter__()

    def __len__(self) -> int:
        return self._values.__len__()

    @classmethod
    def _parse_setting(cls, name: str):
        parts = name.split(".")
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2])
        else:
            return (parts[0], None, parts[1])

    def _check_section_and_name(
        self,
        section: SectionLike,
        name: NameLike
    ) -> Tuple[Section, Name]:
        if not isinstance(section, tuple):
            section = (section,)

        checked_section = tuple(
            [
                subsection.encode(self.encoding)
                if not isinstance(subsection, bytes)
                else subsection
                for subsection in section
            ]
        )

        if not isinstance(name, bytes):
            name = name.encode(self.encoding)

        return checked_section, name

    def get_multivar(
        self,
        section: SectionLike,
        name: NameLike
    ) -> Iterator[Value]:
        section, name = self._check_section_and_name(section, name)

        if len(section) > 1:
            try:
                return self._values[section].get_all(name)
            except KeyError:
                pass

        return self._values[(section[0],)].get_all(name)

    def get(  # type: ignore[override]
        self,
        section: SectionLike,
        name: NameLike,
    ) -> Value:
        section, name = self._check_section_and_name(section, name)

        if len(section) > 1:
            try:
                return self._values[section][name]
            except KeyError:
                pass

        return self._values[(section[0],)][name]

    def set(
        self,
        section: SectionLike,
        name: NameLike,
        value: Union[ValueLike, bool],
    ) -> None:
        section, name = self._check_section_and_name(section, name)

        if isinstance(value, bool):
            value = b"true" if value else b"false"

        if not isinstance(value, bytes):
            value = value.encode(self.encoding)

        self._values.setdefault(section)[name] = value

    def items(  # type: ignore[override]
        self,
        section: Section
    ) -> Iterator[Tuple[Name, Value]]:
        return self._values.get(section).items()

    def sections(self) -> Iterator[Section]:
        return self._values.keys()


def _format_string(value: bytes) -> bytes:
    if (
        value.startswith(b" ")
        or value.startswith(b"\t")
        or value.endswith(b" ")
        or b"#" in value
        or value.endswith(b"\t")
    ):
        return b'"' + _escape_value(value) + b'"'
    else:
        return _escape_value(value)


_ESCAPE_TABLE = {
    ord(b"\\"): ord(b"\\"),
    ord(b'"'): ord(b'"'),
    ord(b"n"): ord(b"\n"),
    ord(b"t"): ord(b"\t"),
    ord(b"b"): ord(b"\b"),
}
_COMMENT_CHARS = [ord(b"#"), ord(b";")]
_WHITESPACE_CHARS = [ord(b"\t"), ord(b" ")]


def _parse_string(value: bytes) -> bytes:
    value = bytearray(value.strip())
    ret = bytearray()
    whitespace = bytearray()
    in_quotes = False
    i = 0
    while i < len(value):
        c = value[i]
        if c == ord(b"\\"):
            i += 1
            try:
                v = _ESCAPE_TABLE[value[i]]
            except IndexError as exc:
                raise ValueError(
                    "escape character in %r at %d before end of string" % (value, i)
                ) from exc
            except KeyError as exc:
                raise ValueError(
                    "escape character followed by unknown character "
                    "%s at %d in %r" % (value[i], i, value)
                ) from exc
            if whitespace:
                ret.extend(whitespace)
                whitespace = bytearray()
            ret.append(v)
        elif c == ord(b'"'):
            in_quotes = not in_quotes
        elif c in _COMMENT_CHARS and not in_quotes:
            # the rest of the line is a comment
            break
        elif c in _WHITESPACE_CHARS:
            whitespace.append(c)
        else:
            if whitespace:
                ret.extend(whitespace)
                whitespace = bytearray()
            ret.append(c)
        i += 1

    if in_quotes:
        raise ValueError("missing end quote")

    return bytes(ret)


def _escape_value(value: bytes) -> bytes:
    """Escape a value."""
    value = value.replace(b"\\", b"\\\\")
    value = value.replace(b"\r", b"\\r")
    value = value.replace(b"\n", b"\\n")
    value = value.replace(b"\t", b"\\t")
    value = value.replace(b'"', b'\\"')
    return value


def _check_variable_name(name: bytes) -> bool:
    for i in range(len(name)):
        c = name[i : i + 1]
        if not c.isalnum() and c != b"-":
            return False
    return True


def _check_section_name(name: bytes) -> bool:
    for i in range(len(name)):
        c = name[i : i + 1]
        if not c.isalnum() and c not in (b"-", b"."):
            return False
    return True


def _strip_comments(line: bytes) -> bytes:
    comment_bytes = {ord(b"#"), ord(b";")}
    quote = ord(b'"')
    string_open = False
    # Normalize line to bytearray for simple 2/3 compatibility
    for i, character in enumerate(bytearray(line)):
        # Comment characters outside balanced quotes denote comment start
        if character == quote:
            string_open = not string_open
        elif not string_open and character in comment_bytes:
            return line[:i]
    return line


def _parse_section_header_line(line: bytes) -> Tuple[Section, bytes]:
    # Parse section header ("[bla]")
    line = _strip_comments(line).rstrip()
    in_quotes = False
    escaped = False
    for i, c in enumerate(line):
        if escaped:
            escaped = False
            continue
        if c == ord(b'"'):
            in_quotes = not in_quotes
        if c == ord(b'\\'):
            escaped = True
        if c == ord(b']') and not in_quotes:
            last = i
            break
    else:
        raise ValueError("expected trailing ]")
    pts = line[1:last].split(b" ", 1)
    line = line[last + 1:]
    section: Section
    if len(pts) == 2:
        if pts[1][:1] != b'"' or pts[1][-1:] != b'"':
            raise ValueError("Invalid subsection %r" % pts[1])
        else:
            pts[1] = pts[1][1:-1]
        if not _check_section_name(pts[0]):
            raise ValueError("invalid section name %r" % pts[0])
        section = (pts[0], pts[1])
    else:
        if not _check_section_name(pts[0]):
            raise ValueError("invalid section name %r" % pts[0])
        pts = pts[0].split(b".", 1)
        if len(pts) == 2:
            section = (pts[0], pts[1])
        else:
            section = (pts[0],)
    return section, line


class ConfigFile(ConfigDict):
    """A Git configuration file, like .git/config or ~/.gitconfig."""

    def __init__(
        self,
        values: Union[
            MutableMapping[Section, MutableMapping[Name, Value]], None
        ] = None,
        encoding: Union[str, None] = None
    ) -> None:
        super().__init__(values=values, encoding=encoding)
        self.path: Optional[str] = None

    @classmethod  # noqa: C901
    def from_file(cls, f: BinaryIO) -> "ConfigFile":  # noqa: C901
        """Read configuration from a file-like object."""
        ret = cls()
        section: Optional[Section] = None
        setting = None
        continuation = None
        for lineno, line in enumerate(f.readlines()):
            if lineno == 0 and line.startswith(b'\xef\xbb\xbf'):
                line = line[3:]
            line = line.lstrip()
            if setting is None:
                if len(line) > 0 and line[:1] == b"[":
                    section, line = _parse_section_header_line(line)
                    ret._values.setdefault(section)
                if _strip_comments(line).strip() == b"":
                    continue
                if section is None:
                    raise ValueError("setting %r without section" % line)
                try:
                    setting, value = line.split(b"=", 1)
                except ValueError:
                    setting = line
                    value = b"true"
                setting = setting.strip()
                if not _check_variable_name(setting):
                    raise ValueError("invalid variable name %r" % setting)
                if value.endswith(b"\\\n"):
                    continuation = value[:-2]
                elif value.endswith(b"\\\r\n"):
                    continuation = value[:-3]
                else:
                    continuation = None
                    value = _parse_string(value)
                    ret._values[section][setting] = value
                    setting = None
            else:  # continuation line
                if line.endswith(b"\\\n"):
                    continuation += line[:-2]
                elif line.endswith(b"\\\r\n"):
                    continuation += line[:-3]
                else:
                    continuation += line
                    value = _parse_string(continuation)
                    ret._values[section][setting] = value
                    continuation = None
                    setting = None
        return ret

    @classmethod
    def from_path(cls, path: str) -> "ConfigFile":
        """Read configuration from a file on disk."""
        with GitFile(path, "rb") as f:
            ret = cls.from_file(f)
            ret.path = path
            return ret

    def write_to_path(self, path: Optional[str] = None) -> None:
        """Write configuration to a file on disk."""
        if path is None:
            path = self.path
        with GitFile(path, "wb") as f:
            self.write_to_file(f)

    def write_to_file(self, f: BinaryIO) -> None:
        """Write configuration to a file-like object."""
        for section, values in self._values.items():
            try:
                section_name, subsection_name = section
            except ValueError:
                (section_name,) = section
                subsection_name = None
            if subsection_name is None:
                f.write(b"[" + section_name + b"]\n")
            else:
                f.write(b"[" + section_name + b' "' + subsection_name + b'"]\n')
            for key, value in values.items():
                value = _format_string(value)
                f.write(b"\t" + key + b" = " + value + b"\n")


def get_xdg_config_home_path(*path_segments):
    xdg_config_home = os.environ.get(
        "XDG_CONFIG_HOME",
        os.path.expanduser("~/.config/"),
    )
    return os.path.join(xdg_config_home, *path_segments)


def _find_git_in_win_path():
    for exe in ("git.exe", "git.cmd"):
        for path in os.environ.get("PATH", "").split(";"):
            if os.path.exists(os.path.join(path, exe)):
                # exe path is .../Git/bin/git.exe or .../Git/cmd/git.exe
                git_dir, _bin_dir = os.path.split(path)
                yield git_dir
                break


def _find_git_in_win_reg():
    import platform
    import winreg

    if platform.machine() == "AMD64":
        subkey = (
            "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\"
            "CurrentVersion\\Uninstall\\Git_is1"
        )
    else:
        subkey = (
            "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\"
            "Uninstall\\Git_is1"
        )

    for key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):  # type: ignore
        with suppress(OSError):
            with winreg.OpenKey(key, subkey) as k:  # type: ignore
                val, typ = winreg.QueryValueEx(k, "InstallLocation")  # type: ignore
                if typ == winreg.REG_SZ:  # type: ignore
                    yield val


# There is no set standard for system config dirs on windows. We try the
# following:
#   - %PROGRAMDATA%/Git/config - (deprecated) Windows config dir per CGit docs
#   - %PROGRAMFILES%/Git/etc/gitconfig - Git for Windows (msysgit) config dir
#     Used if CGit installation (Git/bin/git.exe) is found in PATH in the
#     system registry
def get_win_system_paths():
    if "PROGRAMDATA" in os.environ:
        yield os.path.join(os.environ["PROGRAMDATA"], "Git", "config")

    for git_dir in _find_git_in_win_path():
        yield os.path.join(git_dir, "etc", "gitconfig")
    for git_dir in _find_git_in_win_reg():
        yield os.path.join(git_dir, "etc", "gitconfig")


class StackedConfig(Config):
    """Configuration which reads from multiple config files.."""

    def __init__(
        self, backends: List[ConfigFile], writable: Optional[ConfigFile] = None
    ):
        self.backends = backends
        self.writable = writable

    def __repr__(self) -> str:
        return "<{} for {!r}>".format(self.__class__.__name__, self.backends)

    @classmethod
    def default(cls) -> "StackedConfig":
        return cls(cls.default_backends())

    @classmethod
    def default_backends(cls) -> List[ConfigFile]:
        """Retrieve the default configuration.

        See git-config(1) for details on the files searched.
        """
        paths = []
        paths.append(os.path.expanduser("~/.gitconfig"))
        paths.append(get_xdg_config_home_path("git", "config"))

        if "GIT_CONFIG_NOSYSTEM" not in os.environ:
            paths.append("/etc/gitconfig")
            if sys.platform == "win32":
                paths.extend(get_win_system_paths())

        backends = []
        for path in paths:
            try:
                cf = ConfigFile.from_path(path)
            except FileNotFoundError:
                continue
            backends.append(cf)
        return backends

    def get(self, section: SectionLike, name: NameLike) -> Value:
        if not isinstance(section, tuple):
            section = (section,)
        for backend in self.backends:
            try:
                return backend.get(section, name)
            except KeyError:
                pass
        raise KeyError(name)

    def get_multivar(self, section: SectionLike, name: NameLike) -> Iterator[Value]:
        if not isinstance(section, tuple):
            section = (section,)
        for backend in self.backends:
            try:
                yield from backend.get_multivar(section, name)
            except KeyError:
                pass

    def set(
        self,
        section: SectionLike,
        name: NameLike,
        value: Union[ValueLike, bool]
    ) -> None:
        if self.writable is None:
            raise NotImplementedError(self.set)
        return self.writable.set(section, name, value)

    def sections(self) -> Iterator[Section]:
        seen = set()
        for backend in self.backends:
            for section in backend.sections():
                if section not in seen:
                    seen.add(section)
                    yield section


def read_submodules(path: str) -> Iterator[Tuple[bytes, bytes, bytes]]:
    """read a .gitmodules file."""
    cfg = ConfigFile.from_path(path)
    return parse_submodules(cfg)


def parse_submodules(config: ConfigFile) -> Iterator[Tuple[bytes, bytes, bytes]]:
    """Parse a gitmodules GitConfig file, returning submodules.

    Args:
      config: A `ConfigFile`
    Returns:
      list of tuples (submodule path, url, name),
        where name is quoted part of the section's name.
    """
    for section in config.keys():
        section_kind, section_name = section
        if section_kind == b"submodule":
            sm_path = config.get(section, b"path")
            sm_url = config.get(section, b"url")
            yield (sm_path, sm_url, section_name)


def iter_instead_of(config: Config, push: bool = False) -> Iterable[Tuple[str, str]]:
    """Iterate over insteadOf / pushInsteadOf values.
    """
    for section in config.sections():
        if section[0] != b'url':
            continue
        replacement = section[1]
        try:
            needles = list(config.get_multivar(section, "insteadOf"))
        except KeyError:
            needles = []
        if push:
            try:
                needles += list(config.get_multivar(section, "pushInsteadOf"))
            except KeyError:
                pass
        for needle in needles:
            assert isinstance(needle, bytes)
            yield needle.decode('utf-8'), replacement.decode('utf-8')


def apply_instead_of(config: Config, orig_url: str, push: bool = False) -> str:
    """Apply insteadOf / pushInsteadOf to a URL.
    """
    longest_needle = ""
    updated_url = orig_url
    for needle, replacement in iter_instead_of(config, push):
        if not orig_url.startswith(needle):
            continue
        if len(longest_needle) < len(needle):
            longest_needle = needle
            updated_url = replacement + orig_url[len(needle):]
    return updated_url
