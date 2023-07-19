# exc.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
""" Module containing all exceptions thrown throughout the git package, """

from gitdb.exc import BadName  # NOQA @UnusedWildImport skipcq: PYL-W0401, PYL-W0614
from gitdb.exc import *  # NOQA @UnusedWildImport skipcq: PYL-W0401, PYL-W0614
from git.compat import safe_decode
from git.util import remove_password_if_present

# typing ----------------------------------------------------

from typing import List, Sequence, Tuple, Union, TYPE_CHECKING
from git.types import PathLike

if TYPE_CHECKING:
    from git.repo.base import Repo

# ------------------------------------------------------------------


class GitError(Exception):
    """Base class for all package exceptions"""


class InvalidGitRepositoryError(GitError):
    """Thrown if the given repository appears to have an invalid format."""


class WorkTreeRepositoryUnsupported(InvalidGitRepositoryError):
    """Thrown to indicate we can't handle work tree repositories"""


class NoSuchPathError(GitError, OSError):
    """Thrown if a path could not be access by the system."""


class UnsafeProtocolError(GitError):
    """Thrown if unsafe protocols are passed without being explicitly allowed."""


class UnsafeOptionError(GitError):
    """Thrown if unsafe options are passed without being explicitly allowed."""


class CommandError(GitError):
    """Base class for exceptions thrown at every stage of `Popen()` execution.

    :param command:
        A non-empty list of argv comprising the command-line.
    """

    #: A unicode print-format with 2 `%s for `<cmdline>` and the rest,
    #:  e.g.
    #:     "'%s' failed%s"
    _msg = "Cmd('%s') failed%s"

    def __init__(
        self,
        command: Union[List[str], Tuple[str, ...], str],
        status: Union[str, int, None, Exception] = None,
        stderr: Union[bytes, str, None] = None,
        stdout: Union[bytes, str, None] = None,
    ) -> None:
        if not isinstance(command, (tuple, list)):
            command = command.split()
        self.command = remove_password_if_present(command)
        self.status = status
        if status:
            if isinstance(status, Exception):
                status = "%s('%s')" % (type(status).__name__, safe_decode(str(status)))
            else:
                try:
                    status = "exit code(%s)" % int(status)
                except (ValueError, TypeError):
                    s = safe_decode(str(status))
                    status = "'%s'" % s if isinstance(status, str) else s

        self._cmd = safe_decode(self.command[0])
        self._cmdline = " ".join(safe_decode(i) for i in self.command)
        self._cause = status and " due to: %s" % status or "!"
        stdout_decode = safe_decode(stdout)
        stderr_decode = safe_decode(stderr)
        self.stdout = stdout_decode and "\n  stdout: '%s'" % stdout_decode or ""
        self.stderr = stderr_decode and "\n  stderr: '%s'" % stderr_decode or ""

    def __str__(self) -> str:
        return (self._msg + "\n  cmdline: %s%s%s") % (
            self._cmd,
            self._cause,
            self._cmdline,
            self.stdout,
            self.stderr,
        )


class GitCommandNotFound(CommandError):
    """Thrown if we cannot find the `git` executable in the PATH or at the path given by
    the GIT_PYTHON_GIT_EXECUTABLE environment variable"""

    def __init__(self, command: Union[List[str], Tuple[str], str], cause: Union[str, Exception]) -> None:
        super(GitCommandNotFound, self).__init__(command, cause)
        self._msg = "Cmd('%s') not found%s"


class GitCommandError(CommandError):
    """Thrown if execution of the git command fails with non-zero status code."""

    def __init__(
        self,
        command: Union[List[str], Tuple[str, ...], str],
        status: Union[str, int, None, Exception] = None,
        stderr: Union[bytes, str, None] = None,
        stdout: Union[bytes, str, None] = None,
    ) -> None:
        super(GitCommandError, self).__init__(command, status, stderr, stdout)


class CheckoutError(GitError):
    """Thrown if a file could not be checked out from the index as it contained
    changes.

    The .failed_files attribute contains a list of relative paths that failed
    to be checked out as they contained changes that did not exist in the index.

    The .failed_reasons attribute contains a string informing about the actual
    cause of the issue.

    The .valid_files attribute contains a list of relative paths to files that
    were checked out successfully and hence match the version stored in the
    index"""

    def __init__(
        self,
        message: str,
        failed_files: Sequence[PathLike],
        valid_files: Sequence[PathLike],
        failed_reasons: List[str],
    ) -> None:

        Exception.__init__(self, message)
        self.failed_files = failed_files
        self.failed_reasons = failed_reasons
        self.valid_files = valid_files

    def __str__(self) -> str:
        return Exception.__str__(self) + ":%s" % self.failed_files


class CacheError(GitError):

    """Base for all errors related to the git index, which is called cache internally"""


class UnmergedEntriesError(CacheError):
    """Thrown if an operation cannot proceed as there are still unmerged
    entries in the cache"""


class HookExecutionError(CommandError):
    """Thrown if a hook exits with a non-zero exit code. It provides access to the exit code and the string returned
    via standard output"""

    def __init__(
        self,
        command: Union[List[str], Tuple[str, ...], str],
        status: Union[str, int, None, Exception],
        stderr: Union[bytes, str, None] = None,
        stdout: Union[bytes, str, None] = None,
    ) -> None:

        super(HookExecutionError, self).__init__(command, status, stderr, stdout)
        self._msg = "Hook('%s') failed%s"


class RepositoryDirtyError(GitError):
    """Thrown whenever an operation on a repository fails as it has uncommitted changes that would be overwritten"""

    def __init__(self, repo: "Repo", message: str) -> None:
        self.repo = repo
        self.message = message

    def __str__(self) -> str:
        return "Operation cannot be performed on %r: %s" % (self.repo, self.message)
