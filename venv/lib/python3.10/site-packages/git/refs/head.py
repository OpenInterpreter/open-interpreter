from git.config import GitConfigParser, SectionConstraint
from git.util import join_path
from git.exc import GitCommandError

from .symbolic import SymbolicReference
from .reference import Reference

# typinng ---------------------------------------------------

from typing import Any, Sequence, Union, TYPE_CHECKING

from git.types import PathLike, Commit_ish

if TYPE_CHECKING:
    from git.repo import Repo
    from git.objects import Commit
    from git.refs import RemoteReference

# -------------------------------------------------------------------

__all__ = ["HEAD", "Head"]


def strip_quotes(string: str) -> str:
    if string.startswith('"') and string.endswith('"'):
        return string[1:-1]
    return string


class HEAD(SymbolicReference):

    """Special case of a Symbolic Reference as it represents the repository's
    HEAD reference."""

    _HEAD_NAME = "HEAD"
    _ORIG_HEAD_NAME = "ORIG_HEAD"
    __slots__ = ()

    def __init__(self, repo: "Repo", path: PathLike = _HEAD_NAME):
        if path != self._HEAD_NAME:
            raise ValueError("HEAD instance must point to %r, got %r" % (self._HEAD_NAME, path))
        super(HEAD, self).__init__(repo, path)
        self.commit: "Commit"

    def orig_head(self) -> SymbolicReference:
        """
        :return: SymbolicReference pointing at the ORIG_HEAD, which is maintained
            to contain the previous value of HEAD"""
        return SymbolicReference(self.repo, self._ORIG_HEAD_NAME)

    def reset(
        self,
        commit: Union[Commit_ish, SymbolicReference, str] = "HEAD",
        index: bool = True,
        working_tree: bool = False,
        paths: Union[PathLike, Sequence[PathLike], None] = None,
        **kwargs: Any,
    ) -> "HEAD":
        """Reset our HEAD to the given commit optionally synchronizing
        the index and working tree. The reference we refer to will be set to
        commit as well.

        :param commit:
            Commit object, Reference Object or string identifying a revision we
            should reset HEAD to.

        :param index:
            If True, the index will be set to match the given commit. Otherwise
            it will not be touched.

        :param working_tree:
            If True, the working tree will be forcefully adjusted to match the given
            commit, possibly overwriting uncommitted changes without warning.
            If working_tree is True, index must be true as well

        :param paths:
            Single path or list of paths relative to the git root directory
            that are to be reset. This allows to partially reset individual files.

        :param kwargs:
            Additional arguments passed to git-reset.

        :return: self"""
        mode: Union[str, None]
        mode = "--soft"
        if index:
            mode = "--mixed"

            # it appears, some git-versions declare mixed and paths deprecated
            # see http://github.com/Byron/GitPython/issues#issue/2
            if paths:
                mode = None
            # END special case
        # END handle index

        if working_tree:
            mode = "--hard"
            if not index:
                raise ValueError("Cannot reset the working tree if the index is not reset as well")

        # END working tree handling

        try:
            self.repo.git.reset(mode, commit, "--", paths, **kwargs)
        except GitCommandError as e:
            # git nowadays may use 1 as status to indicate there are still unstaged
            # modifications after the reset
            if e.status != 1:
                raise
        # END handle exception

        return self


class Head(Reference):

    """A Head is a named reference to a Commit. Every Head instance contains a name
    and a Commit object.

    Examples::

        >>> repo = Repo("/path/to/repo")
        >>> head = repo.heads[0]

        >>> head.name
        'master'

        >>> head.commit
        <git.Commit "1c09f116cbc2cb4100fb6935bb162daa4723f455">

        >>> head.commit.hexsha
        '1c09f116cbc2cb4100fb6935bb162daa4723f455'"""

    _common_path_default = "refs/heads"
    k_config_remote = "remote"
    k_config_remote_ref = "merge"  # branch to merge from remote

    @classmethod
    def delete(cls, repo: "Repo", *heads: "Union[Head, str]", force: bool = False, **kwargs: Any) -> None:
        """Delete the given heads

        :param force:
            If True, the heads will be deleted even if they are not yet merged into
            the main development stream.
            Default False"""
        flag = "-d"
        if force:
            flag = "-D"
        repo.git.branch(flag, *heads)

    def set_tracking_branch(self, remote_reference: Union["RemoteReference", None]) -> "Head":
        """
        Configure this branch to track the given remote reference. This will alter
            this branch's configuration accordingly.

        :param remote_reference: The remote reference to track or None to untrack
            any references
        :return: self"""
        from .remote import RemoteReference

        if remote_reference is not None and not isinstance(remote_reference, RemoteReference):
            raise ValueError("Incorrect parameter type: %r" % remote_reference)
        # END handle type

        with self.config_writer() as writer:
            if remote_reference is None:
                writer.remove_option(self.k_config_remote)
                writer.remove_option(self.k_config_remote_ref)
                if len(writer.options()) == 0:
                    writer.remove_section()
            else:
                writer.set_value(self.k_config_remote, remote_reference.remote_name)
                writer.set_value(
                    self.k_config_remote_ref,
                    Head.to_full_path(remote_reference.remote_head),
                )

        return self

    def tracking_branch(self) -> Union["RemoteReference", None]:
        """
        :return: The remote_reference we are tracking, or None if we are
            not a tracking branch"""
        from .remote import RemoteReference

        reader = self.config_reader()
        if reader.has_option(self.k_config_remote) and reader.has_option(self.k_config_remote_ref):
            ref = Head(
                self.repo,
                Head.to_full_path(strip_quotes(reader.get_value(self.k_config_remote_ref))),
            )
            remote_refpath = RemoteReference.to_full_path(join_path(reader.get_value(self.k_config_remote), ref.name))
            return RemoteReference(self.repo, remote_refpath)
        # END handle have tracking branch

        # we are not a tracking branch
        return None

    def rename(self, new_path: PathLike, force: bool = False) -> "Head":
        """Rename self to a new path

        :param new_path:
            Either a simple name or a path, i.e. new_name or features/new_name.
            The prefix refs/heads is implied

        :param force:
            If True, the rename will succeed even if a head with the target name
            already exists.

        :return: self
        :note: respects the ref log as git commands are used"""
        flag = "-m"
        if force:
            flag = "-M"

        self.repo.git.branch(flag, self, new_path)
        self.path = "%s/%s" % (self._common_path_default, new_path)
        return self

    def checkout(self, force: bool = False, **kwargs: Any) -> Union["HEAD", "Head"]:
        """Checkout this head by setting the HEAD to this reference, by updating the index
        to reflect the tree we point to and by updating the working tree to reflect
        the latest index.

        The command will fail if changed working tree files would be overwritten.

        :param force:
            If True, changes to the index and the working tree will be discarded.
            If False, GitCommandError will be raised in that situation.

        :param kwargs:
            Additional keyword arguments to be passed to git checkout, i.e.
            b='new_branch' to create a new branch at the given spot.

        :return:
            The active branch after the checkout operation, usually self unless
            a new branch has been created.
            If there is no active branch, as the HEAD is now detached, the HEAD
            reference will be returned instead.

        :note:
            By default it is only allowed to checkout heads - everything else
            will leave the HEAD detached which is allowed and possible, but remains
            a special state that some tools might not be able to handle."""
        kwargs["f"] = force
        if kwargs["f"] is False:
            kwargs.pop("f")

        self.repo.git.checkout(self, **kwargs)
        if self.repo.head.is_detached:
            return self.repo.head
        else:
            return self.repo.active_branch

    # { Configuration
    def _config_parser(self, read_only: bool) -> SectionConstraint[GitConfigParser]:
        if read_only:
            parser = self.repo.config_reader()
        else:
            parser = self.repo.config_writer()
        # END handle parser instance

        return SectionConstraint(parser, 'branch "%s"' % self.name)

    def config_reader(self) -> SectionConstraint[GitConfigParser]:
        """
        :return: A configuration parser instance constrained to only read
            this instance's values"""
        return self._config_parser(read_only=True)

    def config_writer(self) -> SectionConstraint[GitConfigParser]:
        """
        :return: A configuration writer instance with read-and write access
            to options of this head"""
        return self._config_parser(read_only=False)

    # } END configuration
