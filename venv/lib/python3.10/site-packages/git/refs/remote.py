import os

from git.util import join_path

from .head import Head


__all__ = ["RemoteReference"]

# typing ------------------------------------------------------------------

from typing import Any, Iterator, NoReturn, Union, TYPE_CHECKING
from git.types import PathLike


if TYPE_CHECKING:
    from git.repo import Repo
    from git import Remote

# ------------------------------------------------------------------------------


class RemoteReference(Head):

    """Represents a reference pointing to a remote head."""

    _common_path_default = Head._remote_common_path_default

    @classmethod
    def iter_items(
        cls,
        repo: "Repo",
        common_path: Union[PathLike, None] = None,
        remote: Union["Remote", None] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator["RemoteReference"]:
        """Iterate remote references, and if given, constrain them to the given remote"""
        common_path = common_path or cls._common_path_default
        if remote is not None:
            common_path = join_path(common_path, str(remote))
        # END handle remote constraint
        # super is Reference
        return super(RemoteReference, cls).iter_items(repo, common_path)

    # The Head implementation of delete also accepts strs, but this
    # implementation does not.  mypy doesn't have a way of representing
    # tightening the types of arguments in subclasses and recommends Any or
    # "type: ignore".  (See https://github.com/python/typing/issues/241)
    @classmethod
    def delete(cls, repo: "Repo", *refs: "RemoteReference", **kwargs: Any) -> None:  # type: ignore
        """Delete the given remote references

        :note:
            kwargs are given for comparability with the base class method as we
            should not narrow the signature."""
        repo.git.branch("-d", "-r", *refs)
        # the official deletion method will ignore remote symbolic refs - these
        # are generally ignored in the refs/ folder. We don't though
        # and delete remainders manually
        for ref in refs:
            try:
                os.remove(os.path.join(repo.common_dir, ref.path))
            except OSError:
                pass
            try:
                os.remove(os.path.join(repo.git_dir, ref.path))
            except OSError:
                pass
        # END for each ref

    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> NoReturn:
        """Used to disable this method"""
        raise TypeError("Cannot explicitly create remote references")
