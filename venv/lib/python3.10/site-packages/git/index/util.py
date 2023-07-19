"""Module containing index utilities"""
from functools import wraps
import os
import struct
import tempfile
from types import TracebackType

from git.compat import is_win

import os.path as osp


# typing ----------------------------------------------------------------------

from typing import Any, Callable, TYPE_CHECKING, Optional, Type

from git.types import PathLike, _T

if TYPE_CHECKING:
    from git.index import IndexFile

# ---------------------------------------------------------------------------------


__all__ = ("TemporaryFileSwap", "post_clear_cache", "default_index", "git_working_dir")

# { Aliases
pack = struct.pack
unpack = struct.unpack


# } END aliases


class TemporaryFileSwap(object):

    """Utility class moving a file to a temporary location within the same directory
    and moving it back on to where on object deletion."""

    __slots__ = ("file_path", "tmp_file_path")

    def __init__(self, file_path: PathLike) -> None:
        self.file_path = file_path
        self.tmp_file_path = str(self.file_path) + tempfile.mktemp("", "", "")
        # it may be that the source does not exist
        try:
            os.rename(self.file_path, self.tmp_file_path)
        except OSError:
            pass

    def __enter__(self) -> "TemporaryFileSwap":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        if osp.isfile(self.tmp_file_path):
            if is_win and osp.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(self.tmp_file_path, self.file_path)

        return False


# { Decorators


def post_clear_cache(func: Callable[..., _T]) -> Callable[..., _T]:
    """Decorator for functions that alter the index using the git command. This would
    invalidate our possibly existing entries dictionary which is why it must be
    deleted to allow it to be lazily reread later.

    :note:
        This decorator will not be required once all functions are implemented
        natively which in fact is possible, but probably not feasible performance wise.
    """

    @wraps(func)
    def post_clear_cache_if_not_raised(self: "IndexFile", *args: Any, **kwargs: Any) -> _T:
        rval = func(self, *args, **kwargs)
        self._delete_entries_cache()
        return rval

    # END wrapper method

    return post_clear_cache_if_not_raised


def default_index(func: Callable[..., _T]) -> Callable[..., _T]:
    """Decorator assuring the wrapped method may only run if we are the default
    repository index. This is as we rely on git commands that operate
    on that index only."""

    @wraps(func)
    def check_default_index(self: "IndexFile", *args: Any, **kwargs: Any) -> _T:
        if self._file_path != self._index_path():
            raise AssertionError(
                "Cannot call %r on indices that do not represent the default git index" % func.__name__
            )
        return func(self, *args, **kwargs)

    # END wrapper method

    return check_default_index


def git_working_dir(func: Callable[..., _T]) -> Callable[..., _T]:
    """Decorator which changes the current working dir to the one of the git
    repository in order to assure relative paths are handled correctly"""

    @wraps(func)
    def set_git_working_dir(self: "IndexFile", *args: Any, **kwargs: Any) -> _T:
        cur_wd = os.getcwd()
        os.chdir(str(self.repo.working_tree_dir))
        try:
            return func(self, *args, **kwargs)
        finally:
            os.chdir(cur_wd)
        # END handle working dir

    # END wrapper

    return set_git_working_dir


# } END decorators
