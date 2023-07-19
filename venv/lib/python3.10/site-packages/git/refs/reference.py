from git.util import (
    LazyMixin,
    IterableObj,
)
from .symbolic import SymbolicReference, T_References


# typing ------------------------------------------------------------------

from typing import Any, Callable, Iterator, Type, Union, TYPE_CHECKING  # NOQA
from git.types import Commit_ish, PathLike, _T  # NOQA

if TYPE_CHECKING:
    from git.repo import Repo

# ------------------------------------------------------------------------------


__all__ = ["Reference"]

# { Utilities


def require_remote_ref_path(func: Callable[..., _T]) -> Callable[..., _T]:
    """A decorator raising a TypeError if we are not a valid remote, based on the path"""

    def wrapper(self: T_References, *args: Any) -> _T:
        if not self.is_remote():
            raise ValueError("ref path does not point to a remote reference: %s" % self.path)
        return func(self, *args)

    # END wrapper
    wrapper.__name__ = func.__name__
    return wrapper


# }END utilities


class Reference(SymbolicReference, LazyMixin, IterableObj):

    """Represents a named reference to any object. Subclasses may apply restrictions though,
    i.e. Heads can only point to commits."""

    __slots__ = ()
    _points_to_commits_only = False
    _resolve_ref_on_create = True
    _common_path_default = "refs"

    def __init__(self, repo: "Repo", path: PathLike, check_path: bool = True) -> None:
        """Initialize this instance

        :param repo: Our parent repository
        :param path:
            Path relative to the .git/ directory pointing to the ref in question, i.e.
            refs/heads/master
        :param check_path: if False, you can provide any path. Otherwise the path must start with the
            default path prefix of this type."""
        if check_path and not str(path).startswith(self._common_path_default + "/"):
            raise ValueError(f"Cannot instantiate {self.__class__.__name__!r} from path {path}")
        self.path: str  # SymbolicReference converts to string atm
        super(Reference, self).__init__(repo, path)

    def __str__(self) -> str:
        return self.name

    # { Interface

    # @ReservedAssignment
    def set_object(
        self,
        object: Union[Commit_ish, "SymbolicReference", str],
        logmsg: Union[str, None] = None,
    ) -> "Reference":
        """Special version which checks if the head-log needs an update as well

        :return: self"""
        oldbinsha = None
        if logmsg is not None:
            head = self.repo.head
            if not head.is_detached and head.ref == self:
                oldbinsha = self.commit.binsha
            # END handle commit retrieval
        # END handle message is set

        super(Reference, self).set_object(object, logmsg)

        if oldbinsha is not None:
            # /* from refs.c in git-source
            # * Special hack: If a branch is updated directly and HEAD
            # * points to it (may happen on the remote side of a push
            # * for example) then logically the HEAD reflog should be
            # * updated too.
            # * A generic solution implies reverse symref information,
            # * but finding all symrefs pointing to the given branch
            # * would be rather costly for this rare event (the direct
            # * update of a branch) to be worth it.  So let's cheat and
            # * check with HEAD only which should cover 99% of all usage
            # * scenarios (even 100% of the default ones).
            # */
            self.repo.head.log_append(oldbinsha, logmsg)
        # END check if the head

        return self

    # NOTE: Don't have to overwrite properties as the will only work without a the log

    @property
    def name(self) -> str:
        """:return: (shortest) Name of this reference - it may contain path components"""
        # first two path tokens are can be removed as they are
        # refs/heads or refs/tags or refs/remotes
        tokens = self.path.split("/")
        if len(tokens) < 3:
            return self.path  # could be refs/HEAD
        return "/".join(tokens[2:])

    @classmethod
    def iter_items(
        cls: Type[T_References],
        repo: "Repo",
        common_path: Union[PathLike, None] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[T_References]:
        """Equivalent to SymbolicReference.iter_items, but will return non-detached
        references as well."""
        return cls._iter_items(repo, common_path)

    # }END interface

    # { Remote Interface

    @property  # type: ignore ## mypy cannot deal with properties with an extra decorator (2021-04-21)
    @require_remote_ref_path
    def remote_name(self) -> str:
        """
        :return:
            Name of the remote we are a reference of, such as 'origin' for a reference
            named 'origin/master'"""
        tokens = self.path.split("/")
        # /refs/remotes/<remote name>/<branch_name>
        return tokens[2]

    @property  # type: ignore ## mypy cannot deal with properties with an extra decorator (2021-04-21)
    @require_remote_ref_path
    def remote_head(self) -> str:
        """:return: Name of the remote head itself, i.e. master.
        :note: The returned name is usually not qualified enough to uniquely identify
            a branch"""
        tokens = self.path.split("/")
        return "/".join(tokens[3:])

    # } END remote interface
