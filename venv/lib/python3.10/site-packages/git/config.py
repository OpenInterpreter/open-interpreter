# config.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Module containing module parser implementation able to properly read and write
configuration files"""

import sys
import abc
from functools import wraps
import inspect
from io import BufferedReader, IOBase
import logging
import os
import re
import fnmatch

from git.compat import (
    defenc,
    force_text,
    is_win,
)

from git.util import LockFile

import os.path as osp

import configparser as cp

# typing-------------------------------------------------------

from typing import (
    Any,
    Callable,
    Generic,
    IO,
    List,
    Dict,
    Sequence,
    TYPE_CHECKING,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from git.types import Lit_config_levels, ConfigLevels_Tup, PathLike, assert_never, _T

if TYPE_CHECKING:
    from git.repo.base import Repo
    from io import BytesIO

T_ConfigParser = TypeVar("T_ConfigParser", bound="GitConfigParser")
T_OMD_value = TypeVar("T_OMD_value", str, bytes, int, float, bool)

if sys.version_info[:3] < (3, 7, 2):
    # typing.Ordereddict not added until py 3.7.2
    from collections import OrderedDict

    OrderedDict_OMD = OrderedDict
else:
    from typing import OrderedDict

    OrderedDict_OMD = OrderedDict[str, List[T_OMD_value]]  # type: ignore[assignment, misc]

# -------------------------------------------------------------

__all__ = ("GitConfigParser", "SectionConstraint")


log = logging.getLogger("git.config")
log.addHandler(logging.NullHandler())

# invariants
# represents the configuration level of a configuration file


CONFIG_LEVELS: ConfigLevels_Tup = ("system", "user", "global", "repository")


# Section pattern to detect conditional includes.
# https://git-scm.com/docs/git-config#_conditional_includes
CONDITIONAL_INCLUDE_REGEXP = re.compile(r"(?<=includeIf )\"(gitdir|gitdir/i|onbranch):(.+)\"")


class MetaParserBuilder(abc.ABCMeta):  # noqa: B024
    """Utility class wrapping base-class methods into decorators that assure read-only properties"""

    def __new__(cls, name: str, bases: Tuple, clsdict: Dict[str, Any]) -> "MetaParserBuilder":
        """
        Equip all base-class methods with a needs_values decorator, and all non-const methods
        with a set_dirty_and_flush_changes decorator in addition to that."""
        kmm = "_mutating_methods_"
        if kmm in clsdict:
            mutating_methods = clsdict[kmm]
            for base in bases:
                methods = (t for t in inspect.getmembers(base, inspect.isroutine) if not t[0].startswith("_"))
                for name, method in methods:
                    if name in clsdict:
                        continue
                    method_with_values = needs_values(method)
                    if name in mutating_methods:
                        method_with_values = set_dirty_and_flush_changes(method_with_values)
                    # END mutating methods handling

                    clsdict[name] = method_with_values
                # END for each name/method pair
            # END for each base
        # END if mutating methods configuration is set

        new_type = super(MetaParserBuilder, cls).__new__(cls, name, bases, clsdict)
        return new_type


def needs_values(func: Callable[..., _T]) -> Callable[..., _T]:
    """Returns method assuring we read values (on demand) before we try to access them"""

    @wraps(func)
    def assure_data_present(self: "GitConfigParser", *args: Any, **kwargs: Any) -> _T:
        self.read()
        return func(self, *args, **kwargs)

    # END wrapper method
    return assure_data_present


def set_dirty_and_flush_changes(non_const_func: Callable[..., _T]) -> Callable[..., _T]:
    """Return method that checks whether given non constant function may be called.
    If so, the instance will be set dirty.
    Additionally, we flush the changes right to disk"""

    def flush_changes(self: "GitConfigParser", *args: Any, **kwargs: Any) -> _T:
        rval = non_const_func(self, *args, **kwargs)
        self._dirty = True
        self.write()
        return rval

    # END wrapper method
    flush_changes.__name__ = non_const_func.__name__
    return flush_changes


class SectionConstraint(Generic[T_ConfigParser]):

    """Constrains a ConfigParser to only option commands which are constrained to
    always use the section we have been initialized with.

    It supports all ConfigParser methods that operate on an option.

    :note:
        If used as a context manager, will release the wrapped ConfigParser."""

    __slots__ = ("_config", "_section_name")
    _valid_attrs_ = (
        "get_value",
        "set_value",
        "get",
        "set",
        "getint",
        "getfloat",
        "getboolean",
        "has_option",
        "remove_section",
        "remove_option",
        "options",
    )

    def __init__(self, config: T_ConfigParser, section: str) -> None:
        self._config = config
        self._section_name = section

    def __del__(self) -> None:
        # Yes, for some reason, we have to call it explicitly for it to work in PY3 !
        # Apparently __del__ doesn't get call anymore if refcount becomes 0
        # Ridiculous ... .
        self._config.release()

    def __getattr__(self, attr: str) -> Any:
        if attr in self._valid_attrs_:
            return lambda *args, **kwargs: self._call_config(attr, *args, **kwargs)
        return super(SectionConstraint, self).__getattribute__(attr)

    def _call_config(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call the configuration at the given method which must take a section name
        as first argument"""
        return getattr(self._config, method)(self._section_name, *args, **kwargs)

    @property
    def config(self) -> T_ConfigParser:
        """return: Configparser instance we constrain"""
        return self._config

    def release(self) -> None:
        """Equivalent to GitConfigParser.release(), which is called on our underlying parser instance"""
        return self._config.release()

    def __enter__(self) -> "SectionConstraint[T_ConfigParser]":
        self._config.__enter__()
        return self

    def __exit__(self, exception_type: str, exception_value: str, traceback: str) -> None:
        self._config.__exit__(exception_type, exception_value, traceback)


class _OMD(OrderedDict_OMD):
    """Ordered multi-dict."""

    def __setitem__(self, key: str, value: _T) -> None:
        super(_OMD, self).__setitem__(key, [value])

    def add(self, key: str, value: Any) -> None:
        if key not in self:
            super(_OMD, self).__setitem__(key, [value])
            return None
        super(_OMD, self).__getitem__(key).append(value)

    def setall(self, key: str, values: List[_T]) -> None:
        super(_OMD, self).__setitem__(key, values)

    def __getitem__(self, key: str) -> Any:
        return super(_OMD, self).__getitem__(key)[-1]

    def getlast(self, key: str) -> Any:
        return super(_OMD, self).__getitem__(key)[-1]

    def setlast(self, key: str, value: Any) -> None:
        if key not in self:
            super(_OMD, self).__setitem__(key, [value])
            return

        prior = super(_OMD, self).__getitem__(key)
        prior[-1] = value

    def get(self, key: str, default: Union[_T, None] = None) -> Union[_T, None]:
        return super(_OMD, self).get(key, [default])[-1]

    def getall(self, key: str) -> List[_T]:
        return super(_OMD, self).__getitem__(key)

    def items(self) -> List[Tuple[str, _T]]:  # type: ignore[override]
        """List of (key, last value for key)."""
        return [(k, self[k]) for k in self]

    def items_all(self) -> List[Tuple[str, List[_T]]]:
        """List of (key, list of values for key)."""
        return [(k, self.getall(k)) for k in self]


def get_config_path(config_level: Lit_config_levels) -> str:

    # we do not support an absolute path of the gitconfig on windows ,
    # use the global config instead
    if is_win and config_level == "system":
        config_level = "global"

    if config_level == "system":
        return "/etc/gitconfig"
    elif config_level == "user":
        config_home = os.environ.get("XDG_CONFIG_HOME") or osp.join(os.environ.get("HOME", "~"), ".config")
        return osp.normpath(osp.expanduser(osp.join(config_home, "git", "config")))
    elif config_level == "global":
        return osp.normpath(osp.expanduser("~/.gitconfig"))
    elif config_level == "repository":
        raise ValueError("No repo to get repository configuration from. Use Repo._get_config_path")
    else:
        # Should not reach here. Will raise ValueError if does. Static typing will warn missing elifs
        assert_never(
            config_level,  # type: ignore[unreachable]
            ValueError(f"Invalid configuration level: {config_level!r}"),
        )


class GitConfigParser(cp.RawConfigParser, metaclass=MetaParserBuilder):

    """Implements specifics required to read git style configuration files.

    This variation behaves much like the git.config command such that the configuration
    will be read on demand based on the filepath given during initialization.

    The changes will automatically be written once the instance goes out of scope, but
    can be triggered manually as well.

    The configuration file will be locked if you intend to change values preventing other
    instances to write concurrently.

    :note:
        The config is case-sensitive even when queried, hence section and option names
        must match perfectly.
        If used as a context manager, will release the locked file."""

    # { Configuration
    # The lock type determines the type of lock to use in new configuration readers.
    # They must be compatible to the LockFile interface.
    # A suitable alternative would be the BlockingLockFile
    t_lock = LockFile
    re_comment = re.compile(r"^\s*[#;]")

    # } END configuration

    optvalueonly_source = r"\s*(?P<option>[^:=\s][^:=]*)"

    OPTVALUEONLY = re.compile(optvalueonly_source)

    OPTCRE = re.compile(optvalueonly_source + r"\s*(?P<vi>[:=])\s*" + r"(?P<value>.*)$")

    del optvalueonly_source

    # list of RawConfigParser methods able to change the instance
    _mutating_methods_ = ("add_section", "remove_section", "remove_option", "set")

    def __init__(
        self,
        file_or_files: Union[None, PathLike, "BytesIO", Sequence[Union[PathLike, "BytesIO"]]] = None,
        read_only: bool = True,
        merge_includes: bool = True,
        config_level: Union[Lit_config_levels, None] = None,
        repo: Union["Repo", None] = None,
    ) -> None:
        """Initialize a configuration reader to read the given file_or_files and to
        possibly allow changes to it by setting read_only False

        :param file_or_files:
            A single file path or file objects or multiple of these

        :param read_only:
            If True, the ConfigParser may only read the data , but not change it.
            If False, only a single file path or file object may be given. We will write back the changes
            when they happen, or when the ConfigParser is released. This will not happen if other
            configuration files have been included
        :param merge_includes: if True, we will read files mentioned in [include] sections and merge their
            contents into ours. This makes it impossible to write back an individual configuration file.
            Thus, if you want to modify a single configuration file, turn this off to leave the original
            dataset unaltered when reading it.
        :param repo: Reference to repository to use if [includeIf] sections are found in configuration files.

        """
        cp.RawConfigParser.__init__(self, dict_type=_OMD)
        self._dict: Callable[..., _OMD]  # type: ignore   # mypy/typeshed bug?
        self._defaults: _OMD
        self._sections: _OMD  # type: ignore  # mypy/typeshed bug?

        # Used in python 3, needs to stay in sync with sections for underlying implementation to work
        if not hasattr(self, "_proxies"):
            self._proxies = self._dict()

        if file_or_files is not None:
            self._file_or_files: Union[PathLike, "BytesIO", Sequence[Union[PathLike, "BytesIO"]]] = file_or_files
        else:
            if config_level is None:
                if read_only:
                    self._file_or_files = [
                        get_config_path(cast(Lit_config_levels, f)) for f in CONFIG_LEVELS if f != "repository"
                    ]
                else:
                    raise ValueError("No configuration level or configuration files specified")
            else:
                self._file_or_files = [get_config_path(config_level)]

        self._read_only = read_only
        self._dirty = False
        self._is_initialized = False
        self._merge_includes = merge_includes
        self._repo = repo
        self._lock: Union["LockFile", None] = None
        self._acquire_lock()

    def _acquire_lock(self) -> None:
        if not self._read_only:
            if not self._lock:
                if isinstance(self._file_or_files, (str, os.PathLike)):
                    file_or_files = self._file_or_files
                elif isinstance(self._file_or_files, (tuple, list, Sequence)):
                    raise ValueError(
                        "Write-ConfigParsers can operate on a single file only, multiple files have been passed"
                    )
                else:
                    file_or_files = self._file_or_files.name

                # END get filename from handle/stream
                # initialize lock base - we want to write
                self._lock = self.t_lock(file_or_files)
            # END lock check

            self._lock._obtain_lock()
        # END read-only check

    def __del__(self) -> None:
        """Write pending changes if required and release locks"""
        # NOTE: only consistent in PY2
        self.release()

    def __enter__(self) -> "GitConfigParser":
        self._acquire_lock()
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()

    def release(self) -> None:
        """Flush changes and release the configuration write lock. This instance must not be used anymore afterwards.
        In Python 3, it's required to explicitly release locks and flush changes, as __del__ is not called
        deterministically anymore."""
        # checking for the lock here makes sure we do not raise during write()
        # in case an invalid parser was created who could not get a lock
        if self.read_only or (self._lock and not self._lock._has_lock()):
            return

        try:
            try:
                self.write()
            except IOError:
                log.error("Exception during destruction of GitConfigParser", exc_info=True)
            except ReferenceError:
                # This happens in PY3 ... and usually means that some state cannot be written
                # as the sections dict cannot be iterated
                # Usually when shutting down the interpreter, don'y know how to fix this
                pass
        finally:
            if self._lock is not None:
                self._lock._release_lock()

    def optionxform(self, optionstr: str) -> str:
        """Do not transform options in any way when writing"""
        return optionstr

    def _read(self, fp: Union[BufferedReader, IO[bytes]], fpname: str) -> None:
        """A direct copy of the py2.4 version of the super class's _read method
        to assure it uses ordered dicts. Had to change one line to make it work.

        Future versions have this fixed, but in fact its quite embarrassing for the
        guys not to have done it right in the first place !

        Removed big comments to make it more compact.

        Made sure it ignores initial whitespace as git uses tabs"""
        cursect = None  # None, or a dictionary
        optname = None
        lineno = 0
        is_multi_line = False
        e = None  # None, or an exception

        def string_decode(v: str) -> str:
            if v[-1] == "\\":
                v = v[:-1]
            # end cut trailing escapes to prevent decode error

            return v.encode(defenc).decode("unicode_escape")
            # end

        # end

        while True:
            # we assume to read binary !
            line = fp.readline().decode(defenc)
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if line.strip() == "" or self.re_comment.match(line):
                continue
            if line.split(None, 1)[0].lower() == "rem" and line[0] in "rR":
                # no leading whitespace
                continue

            # is it a section header?
            mo = self.SECTCRE.match(line.strip())
            if not is_multi_line and mo:
                sectname: str = mo.group("header").strip()
                if sectname in self._sections:
                    cursect = self._sections[sectname]
                elif sectname == cp.DEFAULTSECT:
                    cursect = self._defaults
                else:
                    cursect = self._dict((("__name__", sectname),))
                    self._sections[sectname] = cursect
                    self._proxies[sectname] = None
                # So sections can't start with a continuation line
                optname = None
            # no section header in the file?
            elif cursect is None:
                raise cp.MissingSectionHeaderError(fpname, lineno, line)
            # an option line?
            elif not is_multi_line:
                mo = self.OPTCRE.match(line)
                if mo:
                    # We might just have handled the last line, which could contain a quotation we want to remove
                    optname, vi, optval = mo.group("option", "vi", "value")
                    if vi in ("=", ":") and ";" in optval and not optval.strip().startswith('"'):
                        pos = optval.find(";")
                        if pos != -1 and optval[pos - 1].isspace():
                            optval = optval[:pos]
                    optval = optval.strip()
                    if optval == '""':
                        optval = ""
                    # end handle empty string
                    optname = self.optionxform(optname.rstrip())
                    if len(optval) > 1 and optval[0] == '"' and optval[-1] != '"':
                        is_multi_line = True
                        optval = string_decode(optval[1:])
                    # end handle multi-line
                    # preserves multiple values for duplicate optnames
                    cursect.add(optname, optval)
                else:
                    # check if it's an option with no value - it's just ignored by git
                    if not self.OPTVALUEONLY.match(line):
                        if not e:
                            e = cp.ParsingError(fpname)
                        e.append(lineno, repr(line))
                    continue
            else:
                line = line.rstrip()
                if line.endswith('"'):
                    is_multi_line = False
                    line = line[:-1]
                # end handle quotations
                optval = cursect.getlast(optname)
                cursect.setlast(optname, optval + string_decode(line))
            # END parse section or option
        # END while reading

        # if any parsing errors occurred, raise an exception
        if e:
            raise e

    def _has_includes(self) -> Union[bool, int]:
        return self._merge_includes and len(self._included_paths())

    def _included_paths(self) -> List[Tuple[str, str]]:
        """Return List all paths that must be included to configuration
        as Tuples of (option, value).
        """
        paths = []

        for section in self.sections():
            if section == "include":
                paths += self.items(section)

            match = CONDITIONAL_INCLUDE_REGEXP.search(section)
            if match is None or self._repo is None:
                continue

            keyword = match.group(1)
            value = match.group(2).strip()

            if keyword in ["gitdir", "gitdir/i"]:
                value = osp.expanduser(value)

                if not any(value.startswith(s) for s in ["./", "/"]):
                    value = "**/" + value
                if value.endswith("/"):
                    value += "**"

                # Ensure that glob is always case insensitive if required.
                if keyword.endswith("/i"):
                    value = re.sub(
                        r"[a-zA-Z]",
                        lambda m: "[{}{}]".format(m.group().lower(), m.group().upper()),
                        value,
                    )
                if self._repo.git_dir:
                    if fnmatch.fnmatchcase(str(self._repo.git_dir), value):
                        paths += self.items(section)

            elif keyword == "onbranch":
                try:
                    branch_name = self._repo.active_branch.name
                except TypeError:
                    # Ignore section if active branch cannot be retrieved.
                    continue

                if fnmatch.fnmatchcase(branch_name, value):
                    paths += self.items(section)

        return paths

    def read(self) -> None:  # type: ignore[override]
        """Reads the data stored in the files we have been initialized with. It will
        ignore files that cannot be read, possibly leaving an empty configuration

        :return: Nothing
        :raise IOError: if a file cannot be handled"""
        if self._is_initialized:
            return None
        self._is_initialized = True

        files_to_read: List[Union[PathLike, IO]] = [""]
        if isinstance(self._file_or_files, (str, os.PathLike)):
            # for str or Path, as str is a type of Sequence
            files_to_read = [self._file_or_files]
        elif not isinstance(self._file_or_files, (tuple, list, Sequence)):
            # could merge with above isinstance once runtime type known
            files_to_read = [self._file_or_files]
        else:  # for lists or tuples
            files_to_read = list(self._file_or_files)
        # end assure we have a copy of the paths to handle

        seen = set(files_to_read)
        num_read_include_files = 0
        while files_to_read:
            file_path = files_to_read.pop(0)
            file_ok = False

            if hasattr(file_path, "seek"):
                # must be a file objectfile-object
                file_path = cast(IO[bytes], file_path)  # replace with assert to narrow type, once sure
                self._read(file_path, file_path.name)
            else:
                # assume a path if it is not a file-object
                file_path = cast(PathLike, file_path)
                try:
                    with open(file_path, "rb") as fp:
                        file_ok = True
                        self._read(fp, fp.name)
                except IOError:
                    continue

            # Read includes and append those that we didn't handle yet
            # We expect all paths to be normalized and absolute (and will assure that is the case)
            if self._has_includes():
                for _, include_path in self._included_paths():
                    if include_path.startswith("~"):
                        include_path = osp.expanduser(include_path)
                    if not osp.isabs(include_path):
                        if not file_ok:
                            continue
                        # end ignore relative paths if we don't know the configuration file path
                        file_path = cast(PathLike, file_path)
                        assert osp.isabs(file_path), "Need absolute paths to be sure our cycle checks will work"
                        include_path = osp.join(osp.dirname(file_path), include_path)
                    # end make include path absolute
                    include_path = osp.normpath(include_path)
                    if include_path in seen or not os.access(include_path, os.R_OK):
                        continue
                    seen.add(include_path)
                    # insert included file to the top to be considered first
                    files_to_read.insert(0, include_path)
                    num_read_include_files += 1
                # each include path in configuration file
            # end handle includes
        # END for each file object to read

        # If there was no file included, we can safely write back (potentially) the configuration file
        # without altering it's meaning
        if num_read_include_files == 0:
            self._merge_includes = False
        # end

    def _write(self, fp: IO) -> None:
        """Write an .ini-format representation of the configuration state in
        git compatible format"""

        def write_section(name: str, section_dict: _OMD) -> None:
            fp.write(("[%s]\n" % name).encode(defenc))

            values: Sequence[str]  # runtime only gets str in tests, but should be whatever _OMD stores
            v: str
            for (key, values) in section_dict.items_all():
                if key == "__name__":
                    continue

                for v in values:
                    fp.write(("\t%s = %s\n" % (key, self._value_to_string(v).replace("\n", "\n\t"))).encode(defenc))
                # END if key is not __name__

        # END section writing

        if self._defaults:
            write_section(cp.DEFAULTSECT, self._defaults)
        value: _OMD

        for name, value in self._sections.items():
            write_section(name, value)

    def items(self, section_name: str) -> List[Tuple[str, str]]:  # type: ignore[override]
        """:return: list((option, value), ...) pairs of all items in the given section"""
        return [(k, v) for k, v in super(GitConfigParser, self).items(section_name) if k != "__name__"]

    def items_all(self, section_name: str) -> List[Tuple[str, List[str]]]:
        """:return: list((option, [values...]), ...) pairs of all items in the given section"""
        rv = _OMD(self._defaults)

        for k, vs in self._sections[section_name].items_all():
            if k == "__name__":
                continue

            if k in rv and rv.getall(k) == vs:
                continue

            for v in vs:
                rv.add(k, v)

        return rv.items_all()

    @needs_values
    def write(self) -> None:
        """Write changes to our file, if there are changes at all

        :raise IOError: if this is a read-only writer instance or if we could not obtain
            a file lock"""
        self._assure_writable("write")
        if not self._dirty:
            return None

        if isinstance(self._file_or_files, (list, tuple)):
            raise AssertionError(
                "Cannot write back if there is not exactly a single file to write to, have %i files"
                % len(self._file_or_files)
            )
        # end assert multiple files

        if self._has_includes():
            log.debug(
                "Skipping write-back of configuration file as include files were merged in."
                + "Set merge_includes=False to prevent this."
            )
            return None
        # end

        fp = self._file_or_files

        # we have a physical file on disk, so get a lock
        is_file_lock = isinstance(fp, (str, os.PathLike, IOBase))  # can't use Pathlike until 3.5 dropped
        if is_file_lock and self._lock is not None:  # else raise Error?
            self._lock._obtain_lock()

        if not hasattr(fp, "seek"):
            fp = cast(PathLike, fp)
            with open(fp, "wb") as fp_open:
                self._write(fp_open)
        else:
            fp = cast("BytesIO", fp)
            fp.seek(0)
            # make sure we do not overwrite into an existing file
            if hasattr(fp, "truncate"):
                fp.truncate()
            self._write(fp)

    def _assure_writable(self, method_name: str) -> None:
        if self.read_only:
            raise IOError("Cannot execute non-constant method %s.%s" % (self, method_name))

    def add_section(self, section: str) -> None:
        """Assures added options will stay in order"""
        return super(GitConfigParser, self).add_section(section)

    @property
    def read_only(self) -> bool:
        """:return: True if this instance may change the configuration file"""
        return self._read_only

    def get_value(
        self,
        section: str,
        option: str,
        default: Union[int, float, str, bool, None] = None,
    ) -> Union[int, float, str, bool]:
        # can default or return type include bool?
        """Get an option's value.

        If multiple values are specified for this option in the section, the
        last one specified is returned.

        :param default:
            If not None, the given default value will be returned in case
            the option did not exist
        :return: a properly typed value, either int, float or string

        :raise TypeError: in case the value could not be understood
            Otherwise the exceptions known to the ConfigParser will be raised."""
        try:
            valuestr = self.get(section, option)
        except Exception:
            if default is not None:
                return default
            raise

        return self._string_to_value(valuestr)

    def get_values(
        self,
        section: str,
        option: str,
        default: Union[int, float, str, bool, None] = None,
    ) -> List[Union[int, float, str, bool]]:
        """Get an option's values.

        If multiple values are specified for this option in the section, all are
        returned.

        :param default:
            If not None, a list containing the given default value will be
            returned in case the option did not exist
        :return: a list of properly typed values, either int, float or string

        :raise TypeError: in case the value could not be understood
            Otherwise the exceptions known to the ConfigParser will be raised."""
        try:
            self.sections()
            lst = self._sections[section].getall(option)
        except Exception:
            if default is not None:
                return [default]
            raise

        return [self._string_to_value(valuestr) for valuestr in lst]

    def _string_to_value(self, valuestr: str) -> Union[int, float, str, bool]:
        types = (int, float)
        for numtype in types:
            try:
                val = numtype(valuestr)
                # truncated value ?
                if val != float(valuestr):
                    continue
                return val
            except (ValueError, TypeError):
                continue
        # END for each numeric type

        # try boolean values as git uses them
        vl = valuestr.lower()
        if vl == "false":
            return False
        if vl == "true":
            return True

        if not isinstance(valuestr, str):
            raise TypeError(
                "Invalid value type: only int, long, float and str are allowed",
                valuestr,
            )

        return valuestr

    def _value_to_string(self, value: Union[str, bytes, int, float, bool]) -> str:
        if isinstance(value, (int, float, bool)):
            return str(value)
        return force_text(value)

    @needs_values
    @set_dirty_and_flush_changes
    def set_value(self, section: str, option: str, value: Union[str, bytes, int, float, bool]) -> "GitConfigParser":
        """Sets the given option in section to the given value.
        It will create the section if required, and will not throw as opposed to the default
        ConfigParser 'set' method.

        :param section: Name of the section in which the option resides or should reside
        :param option: Name of the options whose value to set

        :param value: Value to set the option to. It must be a string or convertible
            to a string
        :return: this instance"""
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, self._value_to_string(value))
        return self

    @needs_values
    @set_dirty_and_flush_changes
    def add_value(self, section: str, option: str, value: Union[str, bytes, int, float, bool]) -> "GitConfigParser":
        """Adds a value for the given option in section.
        It will create the section if required, and will not throw as opposed to the default
        ConfigParser 'set' method. The value becomes the new value of the option as returned
        by 'get_value', and appends to the list of values returned by 'get_values`'.

        :param section: Name of the section in which the option resides or should reside
        :param option: Name of the option

        :param value: Value to add to option. It must be a string or convertible
            to a string
        :return: this instance"""
        if not self.has_section(section):
            self.add_section(section)
        self._sections[section].add(option, self._value_to_string(value))
        return self

    def rename_section(self, section: str, new_name: str) -> "GitConfigParser":
        """rename the given section to new_name
        :raise ValueError: if section doesn't exit
        :raise ValueError: if a section with new_name does already exist
        :return: this instance
        """
        if not self.has_section(section):
            raise ValueError("Source section '%s' doesn't exist" % section)
        if self.has_section(new_name):
            raise ValueError("Destination section '%s' already exists" % new_name)

        super(GitConfigParser, self).add_section(new_name)
        new_section = self._sections[new_name]
        for k, vs in self.items_all(section):
            new_section.setall(k, vs)
        # end for each value to copy

        # This call writes back the changes, which is why we don't have the respective decorator
        self.remove_section(section)
        return self
