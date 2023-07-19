# need a dict to set bloody .name field
from io import BytesIO
import logging
import os
import stat
import uuid

import git
from git.cmd import Git
from git.compat import (
    defenc,
    is_win,
)
from git.config import SectionConstraint, GitConfigParser, cp
from git.exc import (
    InvalidGitRepositoryError,
    NoSuchPathError,
    RepositoryDirtyError,
    BadName,
)
from git.objects.base import IndexObject, Object
from git.objects.util import TraversableIterableObj

from git.util import (
    join_path_native,
    to_native_path_linux,
    RemoteProgress,
    rmtree,
    unbare_repo,
    IterableList,
)
from git.util import HIDE_WINDOWS_KNOWN_ERRORS

import os.path as osp

from .util import (
    mkhead,
    sm_name,
    sm_section,
    SubmoduleConfigParser,
    find_first_remote_branch,
)


# typing ----------------------------------------------------------------------
from typing import Callable, Dict, Mapping, Sequence, TYPE_CHECKING, cast
from typing import Any, Iterator, Union

from git.types import Commit_ish, Literal, PathLike, TBD

if TYPE_CHECKING:
    from git.index import IndexFile
    from git.repo import Repo
    from git.refs import Head


# -----------------------------------------------------------------------------

__all__ = ["Submodule", "UpdateProgress"]


log = logging.getLogger("git.objects.submodule.base")
log.addHandler(logging.NullHandler())


class UpdateProgress(RemoteProgress):

    """Class providing detailed progress information to the caller who should
    derive from it and implement the ``update(...)`` message"""

    CLONE, FETCH, UPDWKTREE = [1 << x for x in range(RemoteProgress._num_op_codes, RemoteProgress._num_op_codes + 3)]
    _num_op_codes: int = RemoteProgress._num_op_codes + 3

    __slots__ = ()


BEGIN = UpdateProgress.BEGIN
END = UpdateProgress.END
CLONE = UpdateProgress.CLONE
FETCH = UpdateProgress.FETCH
UPDWKTREE = UpdateProgress.UPDWKTREE


# IndexObject comes via util module, its a 'hacky' fix thanks to pythons import
# mechanism which cause plenty of trouble of the only reason for packages and
# modules is refactoring - subpackages shouldn't depend on parent packages
class Submodule(IndexObject, TraversableIterableObj):

    """Implements access to a git submodule. They are special in that their sha
    represents a commit in the submodule's repository which is to be checked out
    at the path of this instance.
    The submodule type does not have a string type associated with it, as it exists
    solely as a marker in the tree and index.

    All methods work in bare and non-bare repositories."""

    _id_attribute_ = "name"
    k_modules_file = ".gitmodules"
    k_head_option = "branch"
    k_head_default = "master"
    k_default_mode = stat.S_IFDIR | stat.S_IFLNK  # submodules are directories with link-status

    # this is a bogus type for base class compatibility
    type: Literal["submodule"] = "submodule"  # type: ignore

    __slots__ = ("_parent_commit", "_url", "_branch_path", "_name", "__weakref__")
    _cache_attrs = ("path", "_url", "_branch_path")

    def __init__(
        self,
        repo: "Repo",
        binsha: bytes,
        mode: Union[int, None] = None,
        path: Union[PathLike, None] = None,
        name: Union[str, None] = None,
        parent_commit: Union[Commit_ish, None] = None,
        url: Union[str, None] = None,
        branch_path: Union[PathLike, None] = None,
    ) -> None:
        """Initialize this instance with its attributes. We only document the ones
        that differ from ``IndexObject``

        :param repo: Our parent repository
        :param binsha: binary sha referring to a commit in the remote repository, see url parameter
        :param parent_commit: see set_parent_commit()
        :param url: The url to the remote repository which is the submodule
        :param branch_path: full (relative) path to ref to checkout when cloning the remote repository"""
        super(Submodule, self).__init__(repo, binsha, mode, path)
        self.size = 0
        self._parent_commit = parent_commit
        if url is not None:
            self._url = url
        if branch_path is not None:
            # assert isinstance(branch_path, str)
            self._branch_path = branch_path
        if name is not None:
            self._name = name

    def _set_cache_(self, attr: str) -> None:
        if attr in ("path", "_url", "_branch_path"):
            reader: SectionConstraint = self.config_reader()
            # default submodule values
            try:
                self.path = reader.get("path")
            except cp.NoSectionError as e:
                if self.repo.working_tree_dir is not None:
                    raise ValueError(
                        "This submodule instance does not exist anymore in '%s' file"
                        % osp.join(self.repo.working_tree_dir, ".gitmodules")
                    ) from e
            # end
            self._url = reader.get("url")
            # git-python extension values - optional
            self._branch_path = reader.get_value(self.k_head_option, git.Head.to_full_path(self.k_head_default))
        elif attr == "_name":
            raise AttributeError("Cannot retrieve the name of a submodule if it was not set initially")
        else:
            super(Submodule, self)._set_cache_(attr)
        # END handle attribute name

    @classmethod
    def _get_intermediate_items(cls, item: "Submodule") -> IterableList["Submodule"]:
        """:return: all the submodules of our module repository"""
        try:
            return cls.list_items(item.module())
        except InvalidGitRepositoryError:
            return IterableList("")
        # END handle intermediate items

    @classmethod
    def _need_gitfile_submodules(cls, git: Git) -> bool:
        return git.version_info[:3] >= (1, 7, 5)

    def __eq__(self, other: Any) -> bool:
        """Compare with another submodule"""
        # we may only compare by name as this should be the ID they are hashed with
        # Otherwise this type wouldn't be hashable
        # return self.path == other.path and self.url == other.url and super(Submodule, self).__eq__(other)
        return self._name == other._name

    def __ne__(self, other: object) -> bool:
        """Compare with another submodule for inequality"""
        return not (self == other)

    def __hash__(self) -> int:
        """Hash this instance using its logical id, not the sha"""
        return hash(self._name)

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return "git.%s(name=%s, path=%s, url=%s, branch_path=%s)" % (
            type(self).__name__,
            self._name,
            self.path,
            self.url,
            self.branch_path,
        )

    @classmethod
    def _config_parser(
        cls, repo: "Repo", parent_commit: Union[Commit_ish, None], read_only: bool
    ) -> SubmoduleConfigParser:
        """:return: Config Parser constrained to our submodule in read or write mode
        :raise IOError: If the .gitmodules file cannot be found, either locally or in the repository
            at the given parent commit. Otherwise the exception would be delayed until the first
            access of the config parser"""
        parent_matches_head = True
        if parent_commit is not None:
            try:
                parent_matches_head = repo.head.commit == parent_commit
            except ValueError:
                # We are most likely in an empty repository, so the HEAD doesn't point to a valid ref
                pass
        # end handle parent_commit
        fp_module: Union[str, BytesIO]
        if not repo.bare and parent_matches_head and repo.working_tree_dir:
            fp_module = osp.join(repo.working_tree_dir, cls.k_modules_file)
        else:
            assert parent_commit is not None, "need valid parent_commit in bare repositories"
            try:
                fp_module = cls._sio_modules(parent_commit)
            except KeyError as e:
                raise IOError(
                    "Could not find %s file in the tree of parent commit %s" % (cls.k_modules_file, parent_commit)
                ) from e
            # END handle exceptions
        # END handle non-bare working tree

        if not read_only and (repo.bare or not parent_matches_head):
            raise ValueError("Cannot write blobs of 'historical' submodule configurations")
        # END handle writes of historical submodules

        return SubmoduleConfigParser(fp_module, read_only=read_only)

    def _clear_cache(self) -> None:
        # clear the possibly changed values
        for name in self._cache_attrs:
            try:
                delattr(self, name)
            except AttributeError:
                pass
            # END try attr deletion
        # END for each name to delete

    @classmethod
    def _sio_modules(cls, parent_commit: Commit_ish) -> BytesIO:
        """:return: Configuration file as BytesIO - we only access it through the respective blob's data"""
        sio = BytesIO(parent_commit.tree[cls.k_modules_file].data_stream.read())
        sio.name = cls.k_modules_file
        return sio

    def _config_parser_constrained(self, read_only: bool) -> SectionConstraint:
        """:return: Config Parser constrained to our submodule in read or write mode"""
        try:
            pc: Union["Commit_ish", None] = self.parent_commit
        except ValueError:
            pc = None
        # end handle empty parent repository
        parser = self._config_parser(self.repo, pc, read_only)
        parser.set_submodule(self)
        return SectionConstraint(parser, sm_section(self.name))

    @classmethod
    def _module_abspath(cls, parent_repo: "Repo", path: PathLike, name: str) -> PathLike:
        if cls._need_gitfile_submodules(parent_repo.git):
            return osp.join(parent_repo.git_dir, "modules", name)
        if parent_repo.working_tree_dir:
            return osp.join(parent_repo.working_tree_dir, path)
        raise NotADirectoryError()
        # end

    @classmethod
    def _clone_repo(
        cls,
        repo: "Repo",
        url: str,
        path: PathLike,
        name: str,
        allow_unsafe_options: bool = False,
        allow_unsafe_protocols: bool = False,
        **kwargs: Any,
    ) -> "Repo":
        """:return: Repo instance of newly cloned repository
        :param repo: our parent repository
        :param url: url to clone from
        :param path: repository - relative path to the submodule checkout location
        :param name: canonical of the submodule
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --upload-pack
        :param kwargs: additional arguments given to git.clone"""
        module_abspath = cls._module_abspath(repo, path, name)
        module_checkout_path = module_abspath
        if cls._need_gitfile_submodules(repo.git):
            kwargs["separate_git_dir"] = module_abspath
            module_abspath_dir = osp.dirname(module_abspath)
            if not osp.isdir(module_abspath_dir):
                os.makedirs(module_abspath_dir)
            module_checkout_path = osp.join(str(repo.working_tree_dir), path)
        # end

        clone = git.Repo.clone_from(
            url,
            module_checkout_path,
            allow_unsafe_options=allow_unsafe_options,
            allow_unsafe_protocols=allow_unsafe_protocols,
            **kwargs,
        )
        if cls._need_gitfile_submodules(repo.git):
            cls._write_git_file_and_module_config(module_checkout_path, module_abspath)
        # end
        return clone

    @classmethod
    def _to_relative_path(cls, parent_repo: "Repo", path: PathLike) -> PathLike:
        """:return: a path guaranteed  to be relative to the given parent - repository
        :raise ValueError: if path is not contained in the parent repository's working tree"""
        path = to_native_path_linux(path)
        if path.endswith("/"):
            path = path[:-1]
        # END handle trailing slash

        if osp.isabs(path) and parent_repo.working_tree_dir:
            working_tree_linux = to_native_path_linux(parent_repo.working_tree_dir)
            if not path.startswith(working_tree_linux):
                raise ValueError(
                    "Submodule checkout path '%s' needs to be within the parents repository at '%s'"
                    % (working_tree_linux, path)
                )
            path = path[len(working_tree_linux.rstrip("/")) + 1 :]
            if not path:
                raise ValueError("Absolute submodule path '%s' didn't yield a valid relative path" % path)
            # end verify converted relative path makes sense
        # end convert to a relative path

        return path

    @classmethod
    def _write_git_file_and_module_config(cls, working_tree_dir: PathLike, module_abspath: PathLike) -> None:
        """Writes a .git file containing a(preferably) relative path to the actual git module repository.
        It is an error if the module_abspath cannot be made into a relative path, relative to the working_tree_dir
        :note: will overwrite existing files !
        :note: as we rewrite both the git file as well as the module configuration, we might fail on the configuration
            and will not roll back changes done to the git file. This should be a non - issue, but may easily be fixed
            if it becomes one
        :param working_tree_dir: directory to write the .git file into
        :param module_abspath: absolute path to the bare repository
        """
        git_file = osp.join(working_tree_dir, ".git")
        rela_path = osp.relpath(module_abspath, start=working_tree_dir)
        if is_win:
            if osp.isfile(git_file):
                os.remove(git_file)
        with open(git_file, "wb") as fp:
            fp.write(("gitdir: %s" % rela_path).encode(defenc))

        with GitConfigParser(osp.join(module_abspath, "config"), read_only=False, merge_includes=False) as writer:
            writer.set_value(
                "core",
                "worktree",
                to_native_path_linux(osp.relpath(working_tree_dir, start=module_abspath)),
            )

    # { Edit Interface

    @classmethod
    def add(
        cls,
        repo: "Repo",
        name: str,
        path: PathLike,
        url: Union[str, None] = None,
        branch: Union[str, None] = None,
        no_checkout: bool = False,
        depth: Union[int, None] = None,
        env: Union[Mapping[str, str], None] = None,
        clone_multi_options: Union[Sequence[TBD], None] = None,
        allow_unsafe_options: bool = False,
        allow_unsafe_protocols: bool = False,
    ) -> "Submodule":
        """Add a new submodule to the given repository. This will alter the index
        as well as the .gitmodules file, but will not create a new commit.
        If the submodule already exists, no matter if the configuration differs
        from the one provided, the existing submodule will be returned.

        :param repo: Repository instance which should receive the submodule
        :param name: The name/identifier for the submodule
        :param path: repository-relative or absolute path at which the submodule
            should be located
            It will be created as required during the repository initialization.
        :param url: git-clone compatible URL, see git-clone reference for more information
            If None, the repository is assumed to exist, and the url of the first
            remote is taken instead. This is useful if you want to make an existing
            repository a submodule of anotherone.
        :param branch: name of branch at which the submodule should (later) be checked out.
            The given branch must exist in the remote repository, and will be checked
            out locally as a tracking branch.
            It will only be written into the configuration if it not None, which is
            when the checked out branch will be the one the remote HEAD pointed to.
            The result you get in these situation is somewhat fuzzy, and it is recommended
            to specify at least 'master' here.
            Examples are 'master' or 'feature/new'
        :param no_checkout: if True, and if the repository has to be cloned manually,
            no checkout will be performed
        :param depth: Create a shallow clone with a history truncated to the
            specified number of commits.
        :param env: Optional dictionary containing the desired environment variables.
            Note: Provided variables will be used to update the execution
            environment for `git`. If some variable is not specified in `env`
            and is defined in `os.environ`, value from `os.environ` will be used.
            If you want to unset some variable, consider providing empty string
            as its value.
        :param clone_multi_options: A list of Clone options. Please see ``git.repo.base.Repo.clone``
            for details.
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --upload-pack
        :return: The newly created submodule instance
        :note: works atomically, such that no change will be done if the repository
            update fails for instance"""

        if repo.bare:
            raise InvalidGitRepositoryError("Cannot add submodules to bare repositories")
        # END handle bare repos

        path = cls._to_relative_path(repo, path)

        # assure we never put backslashes into the url, as some operating systems
        # like it ...
        if url is not None:
            url = to_native_path_linux(url)
        # END assure url correctness

        # INSTANTIATE INTERMEDIATE SM
        sm = cls(
            repo,
            cls.NULL_BIN_SHA,
            cls.k_default_mode,
            path,
            name,
            url="invalid-temporary",
        )
        if sm.exists():
            # reretrieve submodule from tree
            try:
                sm = repo.head.commit.tree[str(path)]
                sm._name = name
                return sm
            except KeyError:
                # could only be in index
                index = repo.index
                entry = index.entries[index.entry_key(path, 0)]
                sm.binsha = entry.binsha
                return sm
            # END handle exceptions
        # END handle existing

        # fake-repo - we only need the functionality on the branch instance
        br = git.Head(repo, git.Head.to_full_path(str(branch) or cls.k_head_default))
        has_module = sm.module_exists()
        branch_is_default = branch is None
        if has_module and url is not None:
            if url not in [r.url for r in sm.module().remotes]:
                raise ValueError(
                    "Specified URL '%s' does not match any remote url of the repository at '%s'" % (url, sm.abspath)
                )
            # END check url
        # END verify urls match

        mrepo: Union[Repo, None] = None

        if url is None:
            if not has_module:
                raise ValueError("A URL was not given and a repository did not exist at %s" % path)
            # END check url
            mrepo = sm.module()
            # assert isinstance(mrepo, git.Repo)
            urls = [r.url for r in mrepo.remotes]
            if not urls:
                raise ValueError("Didn't find any remote url in repository at %s" % sm.abspath)
            # END verify we have url
            url = urls[0]
        else:
            # clone new repo
            kwargs: Dict[str, Union[bool, int, str, Sequence[TBD]]] = {"n": no_checkout}
            if not branch_is_default:
                kwargs["b"] = br.name
            # END setup checkout-branch

            if depth:
                if isinstance(depth, int):
                    kwargs["depth"] = depth
                else:
                    raise ValueError("depth should be an integer")
            if clone_multi_options:
                kwargs["multi_options"] = clone_multi_options

            # _clone_repo(cls, repo, url, path, name, **kwargs):
            mrepo = cls._clone_repo(
                repo,
                url,
                path,
                name,
                env=env,
                allow_unsafe_options=allow_unsafe_options,
                allow_unsafe_protocols=allow_unsafe_protocols,
                **kwargs,
            )
        # END verify url

        ## See #525 for ensuring git urls in config-files valid under Windows.
        url = Git.polish_url(url)

        # It's important to add the URL to the parent config, to let `git submodule` know.
        # otherwise there is a '-' character in front of the submodule listing
        #  a38efa84daef914e4de58d1905a500d8d14aaf45 mymodule (v0.9.0-1-ga38efa8)
        # -a38efa84daef914e4de58d1905a500d8d14aaf45 submodules/intermediate/one
        writer: Union[GitConfigParser, SectionConstraint]

        with sm.repo.config_writer() as writer:
            writer.set_value(sm_section(name), "url", url)

        # update configuration and index
        index = sm.repo.index
        with sm.config_writer(index=index, write=False) as writer:
            writer.set_value("url", url)
            writer.set_value("path", path)

            sm._url = url
            if not branch_is_default:
                # store full path
                writer.set_value(cls.k_head_option, br.path)
                sm._branch_path = br.path

        # we deliberately assume that our head matches our index !
        if mrepo:
            sm.binsha = mrepo.head.commit.binsha
        index.add([sm], write=True)

        return sm

    def update(
        self,
        recursive: bool = False,
        init: bool = True,
        to_latest_revision: bool = False,
        progress: Union["UpdateProgress", None] = None,
        dry_run: bool = False,
        force: bool = False,
        keep_going: bool = False,
        env: Union[Mapping[str, str], None] = None,
        clone_multi_options: Union[Sequence[TBD], None] = None,
        allow_unsafe_options: bool = False,
        allow_unsafe_protocols: bool = False,
    ) -> "Submodule":
        """Update the repository of this submodule to point to the checkout
        we point at with the binsha of this instance.

        :param recursive: if True, we will operate recursively and update child-
            modules as well.
        :param init: if True, the module repository will be cloned into place if necessary
        :param to_latest_revision: if True, the submodule's sha will be ignored during checkout.
            Instead, the remote will be fetched, and the local tracking branch updated.
            This only works if we have a local tracking branch, which is the case
            if the remote repository had a master branch, or of the 'branch' option
            was specified for this submodule and the branch existed remotely
        :param progress: UpdateProgress instance or None if no progress should be shown
        :param dry_run: if True, the operation will only be simulated, but not performed.
            All performed operations are read - only
        :param force:
            If True, we may reset heads even if the repository in question is dirty. Additinoally we will be allowed
            to set a tracking branch which is ahead of its remote branch back into the past or the location of the
            remote branch. This will essentially 'forget' commits.
            If False, local tracking branches that are in the future of their respective remote branches will simply
            not be moved.
        :param keep_going: if True, we will ignore but log all errors, and keep going recursively.
            Unless dry_run is set as well, keep_going could cause subsequent / inherited errors you wouldn't see
            otherwise.
            In conjunction with dry_run, it can be useful to anticipate all errors when updating submodules
        :param env: Optional dictionary containing the desired environment variables.
            Note: Provided variables will be used to update the execution
            environment for `git`. If some variable is not specified in `env`
            and is defined in `os.environ`, value from `os.environ` will be used.
            If you want to unset some variable, consider providing empty string
            as its value.
        :param clone_multi_options:  list of Clone options. Please see ``git.repo.base.Repo.clone``
            for details. Only take effect with `init` option.
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --upload-pack
        :note: does nothing in bare repositories
        :note: method is definitely not atomic if recurisve is True
        :return: self"""
        if self.repo.bare:
            return self
        # END pass in bare mode

        if progress is None:
            progress = UpdateProgress()
        # END handle progress
        prefix = ""
        if dry_run:
            prefix = "DRY-RUN: "
        # END handle prefix

        # to keep things plausible in dry-run mode
        if dry_run:
            mrepo = None
        # END init mrepo

        try:
            # ASSURE REPO IS PRESENT AND UPTODATE
            #####################################
            try:
                mrepo = self.module()
                rmts = mrepo.remotes
                len_rmts = len(rmts)
                for i, remote in enumerate(rmts):
                    op = FETCH
                    if i == 0:
                        op |= BEGIN
                    # END handle start

                    progress.update(
                        op,
                        i,
                        len_rmts,
                        prefix + "Fetching remote %s of submodule %r" % (remote, self.name),
                    )
                    # ===============================
                    if not dry_run:
                        remote.fetch(progress=progress)
                    # END handle dry-run
                    # ===============================
                    if i == len_rmts - 1:
                        op |= END
                    # END handle end
                    progress.update(
                        op,
                        i,
                        len_rmts,
                        prefix + "Done fetching remote of submodule %r" % self.name,
                    )
                # END fetch new data
            except InvalidGitRepositoryError:
                mrepo = None
                if not init:
                    return self
                # END early abort if init is not allowed

                # there is no git-repository yet - but delete empty paths
                checkout_module_abspath = self.abspath
                if not dry_run and osp.isdir(checkout_module_abspath):
                    try:
                        os.rmdir(checkout_module_abspath)
                    except OSError as e:
                        raise OSError(
                            "Module directory at %r does already exist and is non-empty" % checkout_module_abspath
                        ) from e
                    # END handle OSError
                # END handle directory removal

                # don't check it out at first - nonetheless it will create a local
                # branch according to the remote-HEAD if possible
                progress.update(
                    BEGIN | CLONE,
                    0,
                    1,
                    prefix
                    + "Cloning url '%s' to '%s' in submodule %r" % (self.url, checkout_module_abspath, self.name),
                )
                if not dry_run:
                    mrepo = self._clone_repo(
                        self.repo,
                        self.url,
                        self.path,
                        self.name,
                        n=True,
                        env=env,
                        multi_options=clone_multi_options,
                        allow_unsafe_options=allow_unsafe_options,
                        allow_unsafe_protocols=allow_unsafe_protocols,
                    )
                # END handle dry-run
                progress.update(
                    END | CLONE,
                    0,
                    1,
                    prefix + "Done cloning to %s" % checkout_module_abspath,
                )

                if not dry_run:
                    # see whether we have a valid branch to checkout
                    try:
                        mrepo = cast("Repo", mrepo)
                        # find  a remote which has our branch - we try to be flexible
                        remote_branch = find_first_remote_branch(mrepo.remotes, self.branch_name)
                        local_branch = mkhead(mrepo, self.branch_path)

                        # have a valid branch, but no checkout - make sure we can figure
                        # that out by marking the commit with a null_sha
                        local_branch.set_object(Object(mrepo, self.NULL_BIN_SHA))
                        # END initial checkout + branch creation

                        # make sure HEAD is not detached
                        mrepo.head.set_reference(
                            local_branch,
                            logmsg="submodule: attaching head to %s" % local_branch,
                        )
                        mrepo.head.reference.set_tracking_branch(remote_branch)
                    except (IndexError, InvalidGitRepositoryError):
                        log.warning("Failed to checkout tracking branch %s", self.branch_path)
                    # END handle tracking branch

                    # NOTE: Have to write the repo config file as well, otherwise
                    # the default implementation will be offended and not update the repository
                    # Maybe this is a good way to assure it doesn't get into our way, but
                    # we want to stay backwards compatible too ... . Its so redundant !
                    with self.repo.config_writer() as writer:
                        writer.set_value(sm_section(self.name), "url", self.url)
                # END handle dry_run
            # END handle initialization

            # DETERMINE SHAS TO CHECKOUT
            ############################
            binsha = self.binsha
            hexsha = self.hexsha
            if mrepo is not None:
                # mrepo is only set if we are not in dry-run mode or if the module existed
                is_detached = mrepo.head.is_detached
            # END handle dry_run

            if mrepo is not None and to_latest_revision:
                msg_base = "Cannot update to latest revision in repository at %r as " % mrepo.working_dir
                if not is_detached:
                    rref = mrepo.head.reference.tracking_branch()
                    if rref is not None:
                        rcommit = rref.commit
                        binsha = rcommit.binsha
                        hexsha = rcommit.hexsha
                    else:
                        log.error(
                            "%s a tracking branch was not set for local branch '%s'",
                            msg_base,
                            mrepo.head.reference,
                        )
                    # END handle remote ref
                else:
                    log.error("%s there was no local tracking branch", msg_base)
                # END handle detached head
            # END handle to_latest_revision option

            # update the working tree
            # handles dry_run
            if mrepo is not None and mrepo.head.commit.binsha != binsha:
                # We must assure that our destination sha (the one to point to) is in the future of our current head.
                # Otherwise, we will reset changes that might have been done on the submodule, but were not yet pushed
                # We also handle the case that history has been rewritten, leaving no merge-base. In that case
                # we behave conservatively, protecting possible changes the user had done
                may_reset = True
                if mrepo.head.commit.binsha != self.NULL_BIN_SHA:
                    base_commit = mrepo.merge_base(mrepo.head.commit, hexsha)
                    if len(base_commit) == 0 or (base_commit[0] is not None and base_commit[0].hexsha == hexsha):
                        if force:
                            msg = "Will force checkout or reset on local branch that is possibly in the future of"
                            msg += "the commit it will be checked out to, effectively 'forgetting' new commits"
                            log.debug(msg)
                        else:
                            msg = "Skipping %s on branch '%s' of submodule repo '%s' as it contains un-pushed commits"
                            msg %= (
                                is_detached and "checkout" or "reset",
                                mrepo.head,
                                mrepo,
                            )
                            log.info(msg)
                            may_reset = False
                        # end handle force
                    # end handle if we are in the future

                    if may_reset and not force and mrepo.is_dirty(index=True, working_tree=True, untracked_files=True):
                        raise RepositoryDirtyError(mrepo, "Cannot reset a dirty repository")
                    # end handle force and dirty state
                # end handle empty repo

                # end verify future/past
                progress.update(
                    BEGIN | UPDWKTREE,
                    0,
                    1,
                    prefix
                    + "Updating working tree at %s for submodule %r to revision %s" % (self.path, self.name, hexsha),
                )

                if not dry_run and may_reset:
                    if is_detached:
                        # NOTE: for now we force, the user is no supposed to change detached
                        # submodules anyway. Maybe at some point this becomes an option, to
                        # properly handle user modifications - see below for future options
                        # regarding rebase and merge.
                        mrepo.git.checkout(hexsha, force=force)
                    else:
                        mrepo.head.reset(hexsha, index=True, working_tree=True)
                    # END handle checkout
                # if we may reset/checkout
                progress.update(
                    END | UPDWKTREE,
                    0,
                    1,
                    prefix + "Done updating working tree for submodule %r" % self.name,
                )
            # END update to new commit only if needed
        except Exception as err:
            if not keep_going:
                raise
            log.error(str(err))
        # end handle keep_going

        # HANDLE RECURSION
        ##################
        if recursive:
            # in dry_run mode, the module might not exist
            if mrepo is not None:
                for submodule in self.iter_items(self.module()):
                    submodule.update(
                        recursive,
                        init,
                        to_latest_revision,
                        progress=progress,
                        dry_run=dry_run,
                        force=force,
                        keep_going=keep_going,
                    )
                # END handle recursive update
            # END handle dry run
        # END for each submodule

        return self

    @unbare_repo
    def move(self, module_path: PathLike, configuration: bool = True, module: bool = True) -> "Submodule":
        """Move the submodule to a another module path. This involves physically moving
        the repository at our current path, changing the configuration, as well as
        adjusting our index entry accordingly.

        :param module_path: the path to which to move our module in the parent repostory's working tree,
            given as repository - relative or absolute path. Intermediate directories will be created
            accordingly. If the path already exists, it must be empty.
            Trailing(back)slashes are removed automatically
        :param configuration: if True, the configuration will be adjusted to let
            the submodule point to the given path.
        :param module: if True, the repository managed by this submodule
            will be moved as well. If False, we don't move the submodule's checkout, which may leave
            the parent repository in an inconsistent state.
        :return: self
        :raise ValueError: if the module path existed and was not empty, or was a file
        :note: Currently the method is not atomic, and it could leave the repository
            in an inconsistent state if a sub - step fails for some reason
        """
        if module + configuration < 1:
            raise ValueError("You must specify to move at least the module or the configuration of the submodule")
        # END handle input

        module_checkout_path = self._to_relative_path(self.repo, module_path)

        # VERIFY DESTINATION
        if module_checkout_path == self.path:
            return self
        # END handle no change

        module_checkout_abspath = join_path_native(str(self.repo.working_tree_dir), module_checkout_path)
        if osp.isfile(module_checkout_abspath):
            raise ValueError("Cannot move repository onto a file: %s" % module_checkout_abspath)
        # END handle target files

        index = self.repo.index
        tekey = index.entry_key(module_checkout_path, 0)
        # if the target item already exists, fail
        if configuration and tekey in index.entries:
            raise ValueError("Index entry for target path did already exist")
        # END handle index key already there

        # remove existing destination
        if module:
            if osp.exists(module_checkout_abspath):
                if len(os.listdir(module_checkout_abspath)):
                    raise ValueError("Destination module directory was not empty")
                # END handle non-emptiness

                if osp.islink(module_checkout_abspath):
                    os.remove(module_checkout_abspath)
                else:
                    os.rmdir(module_checkout_abspath)
                # END handle link
            else:
                # recreate parent directories
                # NOTE: renames() does that now
                pass
            # END handle existence
        # END handle module

        # move the module into place if possible
        cur_path = self.abspath
        renamed_module = False
        if module and osp.exists(cur_path):
            os.renames(cur_path, module_checkout_abspath)
            renamed_module = True

            if osp.isfile(osp.join(module_checkout_abspath, ".git")):
                module_abspath = self._module_abspath(self.repo, self.path, self.name)
                self._write_git_file_and_module_config(module_checkout_abspath, module_abspath)
            # end handle git file rewrite
        # END move physical module

        # rename the index entry - have to manipulate the index directly as
        # git-mv cannot be used on submodules ... yeah
        previous_sm_path = self.path
        try:
            if configuration:
                try:
                    ekey = index.entry_key(self.path, 0)
                    entry = index.entries[ekey]
                    del index.entries[ekey]
                    nentry = git.IndexEntry(entry[:3] + (module_checkout_path,) + entry[4:])
                    index.entries[tekey] = nentry
                except KeyError as e:
                    raise InvalidGitRepositoryError("Submodule's entry at %r did not exist" % (self.path)) from e
                # END handle submodule doesn't exist

                # update configuration
                with self.config_writer(index=index) as writer:  # auto-write
                    writer.set_value("path", module_checkout_path)
                    self.path = module_checkout_path
            # END handle configuration flag
        except Exception:
            if renamed_module:
                os.renames(module_checkout_abspath, cur_path)
            # END undo module renaming
            raise
        # END handle undo rename

        # Auto-rename submodule if it's name was 'default', that is, the checkout directory
        if previous_sm_path == self.name:
            self.rename(module_checkout_path)
        # end

        return self

    @unbare_repo
    def remove(
        self,
        module: bool = True,
        force: bool = False,
        configuration: bool = True,
        dry_run: bool = False,
    ) -> "Submodule":
        """Remove this submodule from the repository. This will remove our entry
        from the .gitmodules file and the entry in the .git / config file.

        :param module: If True, the module checkout we point to will be deleted
            as well. If the module is currently on a commit which is not part
            of any branch in the remote, if the currently checked out branch
            working tree, or untracked files,
            is ahead of its tracking branch, if you have modifications in the
            In case the removal of the repository fails for these reasons, the
            submodule status will not have been altered.
            If this submodule has child - modules on its own, these will be deleted
            prior to touching the own module.
        :param force: Enforces the deletion of the module even though it contains
            modifications. This basically enforces a brute - force file system based
            deletion.
        :param configuration: if True, the submodule is deleted from the configuration,
            otherwise it isn't. Although this should be enabled most of the times,
            this flag enables you to safely delete the repository of your submodule.
        :param dry_run: if True, we will not actually do anything, but throw the errors
            we would usually throw
        :return: self
        :note: doesn't work in bare repositories
        :note: doesn't work atomically, as failure to remove any part of the submodule will leave
            an inconsistent state
        :raise InvalidGitRepositoryError: thrown if the repository cannot be deleted
        :raise OSError: if directories or files could not be removed"""
        if not (module or configuration):
            raise ValueError("Need to specify to delete at least the module, or the configuration")
        # END handle parameters

        # Recursively remove children of this submodule
        nc = 0
        for csm in self.children():
            nc += 1
            csm.remove(module, force, configuration, dry_run)
            del csm
        # end
        if configuration and not dry_run and nc > 0:
            # Assure we don't leave the parent repository in a dirty state, and commit our changes
            # It's important for recursive, unforced, deletions to work as expected
            self.module().index.commit("Removed at least one of child-modules of '%s'" % self.name)
        # end handle recursion

        # DELETE REPOSITORY WORKING TREE
        ################################
        if module and self.module_exists():
            mod = self.module()
            git_dir = mod.git_dir
            if force:
                # take the fast lane and just delete everything in our module path
                # TODO: If we run into permission problems, we have a highly inconsistent
                # state. Delete the .git folders last, start with the submodules first
                mp = self.abspath
                method: Union[None, Callable[[PathLike], None]] = None
                if osp.islink(mp):
                    method = os.remove
                elif osp.isdir(mp):
                    method = rmtree
                elif osp.exists(mp):
                    raise AssertionError("Cannot forcibly delete repository as it was neither a link, nor a directory")
                # END handle brutal deletion
                if not dry_run:
                    assert method
                    method(mp)
                # END apply deletion method
            else:
                # verify we may delete our module
                if mod.is_dirty(index=True, working_tree=True, untracked_files=True):
                    raise InvalidGitRepositoryError(
                        "Cannot delete module at %s with any modifications, unless force is specified"
                        % mod.working_tree_dir
                    )
                # END check for dirt

                # figure out whether we have new commits compared to the remotes
                # NOTE: If the user pulled all the time, the remote heads might
                # not have been updated, so commits coming from the remote look
                # as if they come from us. But we stay strictly read-only and
                # don't fetch beforehand.
                for remote in mod.remotes:
                    num_branches_with_new_commits = 0
                    rrefs = remote.refs
                    for rref in rrefs:
                        num_branches_with_new_commits += len(mod.git.cherry(rref)) != 0
                    # END for each remote ref
                    # not a single remote branch contained all our commits
                    if len(rrefs) and num_branches_with_new_commits == len(rrefs):
                        raise InvalidGitRepositoryError(
                            "Cannot delete module at %s as there are new commits" % mod.working_tree_dir
                        )
                    # END handle new commits
                    # have to manually delete references as python's scoping is
                    # not existing, they could keep handles open ( on windows this is a problem )
                    if len(rrefs):
                        del rref  # skipcq: PYL-W0631
                    # END handle remotes
                    del rrefs
                    del remote
                # END for each remote

                # finally delete our own submodule
                if not dry_run:
                    self._clear_cache()
                    wtd = mod.working_tree_dir
                    del mod  # release file-handles (windows)
                    import gc

                    gc.collect()
                    try:
                        rmtree(str(wtd))
                    except Exception as ex:
                        if HIDE_WINDOWS_KNOWN_ERRORS:
                            from unittest import SkipTest

                            raise SkipTest("FIXME: fails with: PermissionError\n  {}".format(ex)) from ex
                        raise
                # END delete tree if possible
            # END handle force

            if not dry_run and osp.isdir(git_dir):
                self._clear_cache()
                try:
                    rmtree(git_dir)
                except Exception as ex:
                    if HIDE_WINDOWS_KNOWN_ERRORS:
                        from unittest import SkipTest

                        raise SkipTest(f"FIXME: fails with: PermissionError\n  {ex}") from ex
                    else:
                        raise
            # end handle separate bare repository
        # END handle module deletion

        # void our data not to delay invalid access
        if not dry_run:
            self._clear_cache()

        # DELETE CONFIGURATION
        ######################
        if configuration and not dry_run:
            # first the index-entry
            parent_index = self.repo.index
            try:
                del parent_index.entries[parent_index.entry_key(self.path, 0)]
            except KeyError:
                pass
            # END delete entry
            parent_index.write()

            # now git config - need the config intact, otherwise we can't query
            # information anymore

            with self.repo.config_writer() as gcp_writer:
                gcp_writer.remove_section(sm_section(self.name))

            with self.config_writer() as sc_writer:
                sc_writer.remove_section()
        # END delete configuration

        return self

    def set_parent_commit(self, commit: Union[Commit_ish, None], check: bool = True) -> "Submodule":
        """Set this instance to use the given commit whose tree is supposed to
        contain the .gitmodules blob.

        :param commit:
            Commit'ish reference pointing at the root_tree, or None to always point to the
            most recent commit
        :param check:
            if True, relatively expensive checks will be performed to verify
            validity of the submodule.
        :raise ValueError: if the commit's tree didn't contain the .gitmodules blob.
        :raise ValueError:
            if the parent commit didn't store this submodule under the current path
        :return: self"""
        if commit is None:
            self._parent_commit = None
            return self
        # end handle None
        pcommit = self.repo.commit(commit)
        pctree = pcommit.tree
        if self.k_modules_file not in pctree:
            raise ValueError("Tree of commit %s did not contain the %s file" % (commit, self.k_modules_file))
        # END handle exceptions

        prev_pc = self._parent_commit
        self._parent_commit = pcommit

        if check:
            parser = self._config_parser(self.repo, self._parent_commit, read_only=True)
            if not parser.has_section(sm_section(self.name)):
                self._parent_commit = prev_pc
                raise ValueError("Submodule at path %r did not exist in parent commit %s" % (self.path, commit))
            # END handle submodule did not exist
        # END handle checking mode

        # update our sha, it could have changed
        # If check is False, we might see a parent-commit that doesn't even contain the submodule anymore.
        # in that case, mark our sha as being NULL
        try:
            self.binsha = pctree[str(self.path)].binsha
        except KeyError:
            self.binsha = self.NULL_BIN_SHA
        # end

        self._clear_cache()
        return self

    @unbare_repo
    def config_writer(
        self, index: Union["IndexFile", None] = None, write: bool = True
    ) -> SectionConstraint["SubmoduleConfigParser"]:
        """:return: a config writer instance allowing you to read and write the data
            belonging to this submodule into the .gitmodules file.

        :param index: if not None, an IndexFile instance which should be written.
            defaults to the index of the Submodule's parent repository.
        :param write: if True, the index will be written each time a configuration
            value changes.
        :note: the parameters allow for a more efficient writing of the index,
            as you can pass in a modified index on your own, prevent automatic writing,
            and write yourself once the whole operation is complete
        :raise ValueError: if trying to get a writer on a parent_commit which does not
            match the current head commit
        :raise IOError: If the .gitmodules file/blob could not be read"""
        writer = self._config_parser_constrained(read_only=False)
        if index is not None:
            writer.config._index = index
        writer.config._auto_write = write
        return writer

    @unbare_repo
    def rename(self, new_name: str) -> "Submodule":
        """Rename this submodule
        :note: This method takes care of renaming the submodule in various places, such as

            * $parent_git_dir / config
            * $working_tree_dir / .gitmodules
            * (git >= v1.8.0: move submodule repository to new name)

        As .gitmodules will be changed, you would need to make a commit afterwards. The changed .gitmodules file
        will already be added to the index

        :return: this submodule instance
        """
        if self.name == new_name:
            return self

        # .git/config
        with self.repo.config_writer() as pw:
            # As we ourselves didn't write anything about submodules into the parent .git/config,
            # we will not require it to exist, and just ignore missing entries.
            if pw.has_section(sm_section(self.name)):
                pw.rename_section(sm_section(self.name), sm_section(new_name))

        # .gitmodules
        with self.config_writer(write=True).config as cw:
            cw.rename_section(sm_section(self.name), sm_section(new_name))

        self._name = new_name

        # .git/modules
        mod = self.module()
        if mod.has_separate_working_tree():
            destination_module_abspath = self._module_abspath(self.repo, self.path, new_name)
            source_dir = mod.git_dir
            # Let's be sure the submodule name is not so obviously tied to a directory
            if str(destination_module_abspath).startswith(str(mod.git_dir)):
                tmp_dir = self._module_abspath(self.repo, self.path, str(uuid.uuid4()))
                os.renames(source_dir, tmp_dir)
                source_dir = tmp_dir
            # end handle self-containment
            os.renames(source_dir, destination_module_abspath)
            if mod.working_tree_dir:
                self._write_git_file_and_module_config(mod.working_tree_dir, destination_module_abspath)
        # end move separate git repository

        return self

    # } END edit interface

    # { Query Interface

    @unbare_repo
    def module(self) -> "Repo":
        """:return: Repo instance initialized from the repository at our submodule path
        :raise InvalidGitRepositoryError: if a repository was not available. This could
            also mean that it was not yet initialized"""
        # late import to workaround circular dependencies
        module_checkout_abspath = self.abspath
        try:
            repo = git.Repo(module_checkout_abspath)
            if repo != self.repo:
                return repo
            # END handle repo uninitialized
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            raise InvalidGitRepositoryError("No valid repository at %s" % module_checkout_abspath) from e
        else:
            raise InvalidGitRepositoryError("Repository at %r was not yet checked out" % module_checkout_abspath)
        # END handle exceptions

    def module_exists(self) -> bool:
        """:return: True if our module exists and is a valid git repository. See module() method"""
        try:
            self.module()
            return True
        except Exception:
            return False
        # END handle exception

    def exists(self) -> bool:
        """
        :return: True if the submodule exists, False otherwise. Please note that
            a submodule may exist ( in the .gitmodules file) even though its module
            doesn't exist on disk"""
        # keep attributes for later, and restore them if we have no valid data
        # this way we do not actually alter the state of the object
        loc = locals()
        for attr in self._cache_attrs:
            try:
                if hasattr(self, attr):
                    loc[attr] = getattr(self, attr)
                # END if we have the attribute cache
            except (cp.NoSectionError, ValueError):
                # on PY3, this can happen apparently ... don't know why this doesn't happen on PY2
                pass
        # END for each attr
        self._clear_cache()

        try:
            try:
                self.path
                return True
            except Exception:
                return False
            # END handle exceptions
        finally:
            for attr in self._cache_attrs:
                if attr in loc:
                    setattr(self, attr, loc[attr])
                # END if we have a cache
            # END reapply each attribute
        # END handle object state consistency

    @property
    def branch(self) -> "Head":
        """:return: The branch instance that we are to checkout
        :raise InvalidGitRepositoryError: if our module is not yet checked out"""
        return mkhead(self.module(), self._branch_path)

    @property
    def branch_path(self) -> PathLike:
        """
        :return: full(relative) path as string to the branch we would checkout
            from the remote and track"""
        return self._branch_path

    @property
    def branch_name(self) -> str:
        """:return: the name of the branch, which is the shortest possible branch name"""
        # use an instance method, for this we create a temporary Head instance
        # which uses a repository that is available at least ( it makes no difference )
        return git.Head(self.repo, self._branch_path).name

    @property
    def url(self) -> str:
        """:return: The url to the repository which our module - repository refers to"""
        return self._url

    @property
    def parent_commit(self) -> "Commit_ish":
        """:return: Commit instance with the tree containing the .gitmodules file
        :note: will always point to the current head's commit if it was not set explicitly"""
        if self._parent_commit is None:
            return self.repo.commit()
        return self._parent_commit

    @property
    def name(self) -> str:
        """:return: The name of this submodule. It is used to identify it within the
            .gitmodules file.
        :note: by default, the name is the path at which to find the submodule, but
            in git - python it should be a unique identifier similar to the identifiers
            used for remotes, which allows to change the path of the submodule
            easily
        """
        return self._name

    def config_reader(self) -> SectionConstraint[SubmoduleConfigParser]:
        """
        :return: ConfigReader instance which allows you to qurey the configuration values
            of this submodule, as provided by the .gitmodules file
        :note: The config reader will actually read the data directly from the repository
            and thus does not need nor care about your working tree.
        :note: Should be cached by the caller and only kept as long as needed
        :raise IOError: If the .gitmodules file/blob could not be read"""
        return self._config_parser_constrained(read_only=True)

    def children(self) -> IterableList["Submodule"]:
        """
        :return: IterableList(Submodule, ...) an iterable list of submodules instances
            which are children of this submodule or 0 if the submodule is not checked out"""
        return self._get_intermediate_items(self)

    # } END query interface

    # { Iterable Interface

    @classmethod
    def iter_items(
        cls,
        repo: "Repo",
        parent_commit: Union[Commit_ish, str] = "HEAD",
        *Args: Any,
        **kwargs: Any,
    ) -> Iterator["Submodule"]:
        """:return: iterator yielding Submodule instances available in the given repository"""
        try:
            pc = repo.commit(parent_commit)  # parent commit instance
            parser = cls._config_parser(repo, pc, read_only=True)
        except (IOError, BadName):
            return iter([])
        # END handle empty iterator

        for sms in parser.sections():
            n = sm_name(sms)
            p = parser.get(sms, "path")
            u = parser.get(sms, "url")
            b = cls.k_head_default
            if parser.has_option(sms, cls.k_head_option):
                b = str(parser.get(sms, cls.k_head_option))
            # END handle optional information

            # get the binsha
            index = repo.index
            try:
                rt = pc.tree  # root tree
                sm = rt[p]
            except KeyError:
                # try the index, maybe it was just added
                try:
                    entry = index.entries[index.entry_key(p, 0)]
                    sm = Submodule(repo, entry.binsha, entry.mode, entry.path)
                except KeyError:
                    # The submodule doesn't exist, probably it wasn't
                    # removed from the .gitmodules file.
                    continue
                # END handle keyerror
            # END handle critical error

            # fill in remaining info - saves time as it doesn't have to be parsed again
            sm._name = n
            if pc != repo.commit():
                sm._parent_commit = pc
            # end set only if not most recent !
            sm._branch_path = git.Head.to_full_path(b)
            sm._url = u

            yield sm
        # END for each section

    # } END iterable interface
