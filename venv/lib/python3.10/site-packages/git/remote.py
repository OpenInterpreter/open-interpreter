# remote.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

# Module implementing a remote object allowing easy access to git remotes
import logging
import re

from git.cmd import handle_process_output, Git
from git.compat import defenc, force_text
from git.exc import GitCommandError
from git.util import (
    LazyMixin,
    IterableObj,
    IterableList,
    RemoteProgress,
    CallableRemoteProgress,
)
from git.util import (
    join_path,
)

from git.config import (
    GitConfigParser,
    SectionConstraint,
    cp,
)
from git.refs import Head, Reference, RemoteReference, SymbolicReference, TagReference

# typing-------------------------------------------------------

from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    NoReturn,
    Optional,
    Sequence,
    TYPE_CHECKING,
    Type,
    Union,
    cast,
    overload,
)

from git.types import PathLike, Literal, Commit_ish

if TYPE_CHECKING:
    from git.repo.base import Repo
    from git.objects.submodule.base import UpdateProgress

    # from git.objects.commit import Commit
    # from git.objects import Blob, Tree, TagObject

flagKeyLiteral = Literal[" ", "!", "+", "-", "*", "=", "t", "?"]

# def is_flagKeyLiteral(inp: str) -> TypeGuard[flagKeyLiteral]:
#     return inp in [' ', '!', '+', '-', '=', '*', 't', '?']


# -------------------------------------------------------------


log = logging.getLogger("git.remote")
log.addHandler(logging.NullHandler())


__all__ = ("RemoteProgress", "PushInfo", "FetchInfo", "Remote")

# { Utilities


def add_progress(
    kwargs: Any,
    git: Git,
    progress: Union[RemoteProgress, "UpdateProgress", Callable[..., RemoteProgress], None],
) -> Any:
    """Add the --progress flag to the given kwargs dict if supported by the
    git command. If the actual progress in the given progress instance is not
    given, we do not request any progress
    :return: possibly altered kwargs"""
    if progress is not None:
        v = git.version_info[:2]
        if v >= (1, 7):
            kwargs["progress"] = True
        # END handle --progress
    # END handle progress
    return kwargs


# } END utilities


@overload
def to_progress_instance(progress: None) -> RemoteProgress:
    ...


@overload
def to_progress_instance(progress: Callable[..., Any]) -> CallableRemoteProgress:
    ...


@overload
def to_progress_instance(progress: RemoteProgress) -> RemoteProgress:
    ...


def to_progress_instance(
    progress: Union[Callable[..., Any], RemoteProgress, None]
) -> Union[RemoteProgress, CallableRemoteProgress]:
    """Given the 'progress' return a suitable object derived from
    RemoteProgress().
    """
    # new API only needs progress as a function
    if callable(progress):
        return CallableRemoteProgress(progress)

    # where None is passed create a parser that eats the progress
    elif progress is None:
        return RemoteProgress()

    # assume its the old API with an instance of RemoteProgress.
    return progress


class PushInfo(IterableObj, object):
    """
    Carries information about the result of a push operation of a single head::

        info = remote.push()[0]
        info.flags          # bitflags providing more information about the result
        info.local_ref      # Reference pointing to the local reference that was pushed
                            # It is None if the ref was deleted.
        info.remote_ref_string # path to the remote reference located on the remote side
        info.remote_ref # Remote Reference on the local side corresponding to
                        # the remote_ref_string. It can be a TagReference as well.
        info.old_commit # commit at which the remote_ref was standing before we pushed
                        # it to local_ref.commit. Will be None if an error was indicated
        info.summary    # summary line providing human readable english text about the push
    """

    __slots__ = (
        "local_ref",
        "remote_ref_string",
        "flags",
        "_old_commit_sha",
        "_remote",
        "summary",
    )
    _id_attribute_ = "pushinfo"

    (
        NEW_TAG,
        NEW_HEAD,
        NO_MATCH,
        REJECTED,
        REMOTE_REJECTED,
        REMOTE_FAILURE,
        DELETED,
        FORCED_UPDATE,
        FAST_FORWARD,
        UP_TO_DATE,
        ERROR,
    ) = [1 << x for x in range(11)]

    _flag_map = {
        "X": NO_MATCH,
        "-": DELETED,
        "*": 0,
        "+": FORCED_UPDATE,
        " ": FAST_FORWARD,
        "=": UP_TO_DATE,
        "!": ERROR,
    }

    def __init__(
        self,
        flags: int,
        local_ref: Union[SymbolicReference, None],
        remote_ref_string: str,
        remote: "Remote",
        old_commit: Optional[str] = None,
        summary: str = "",
    ) -> None:
        """Initialize a new instance
        local_ref: HEAD | Head | RemoteReference | TagReference | Reference | SymbolicReference | None"""
        self.flags = flags
        self.local_ref = local_ref
        self.remote_ref_string = remote_ref_string
        self._remote = remote
        self._old_commit_sha = old_commit
        self.summary = summary

    @property
    def old_commit(self) -> Union[str, SymbolicReference, Commit_ish, None]:
        return self._old_commit_sha and self._remote.repo.commit(self._old_commit_sha) or None

    @property
    def remote_ref(self) -> Union[RemoteReference, TagReference]:
        """
        :return:
            Remote Reference or TagReference in the local repository corresponding
            to the remote_ref_string kept in this instance."""
        # translate heads to a local remote, tags stay as they are
        if self.remote_ref_string.startswith("refs/tags"):
            return TagReference(self._remote.repo, self.remote_ref_string)
        elif self.remote_ref_string.startswith("refs/heads"):
            remote_ref = Reference(self._remote.repo, self.remote_ref_string)
            return RemoteReference(
                self._remote.repo,
                "refs/remotes/%s/%s" % (str(self._remote), remote_ref.name),
            )
        else:
            raise ValueError("Could not handle remote ref: %r" % self.remote_ref_string)
        # END

    @classmethod
    def _from_line(cls, remote: "Remote", line: str) -> "PushInfo":
        """Create a new PushInfo instance as parsed from line which is expected to be like
        refs/heads/master:refs/heads/master 05d2687..1d0568e as bytes"""
        control_character, from_to, summary = line.split("\t", 3)
        flags = 0

        # control character handling
        try:
            flags |= cls._flag_map[control_character]
        except KeyError as e:
            raise ValueError("Control character %r unknown as parsed from line %r" % (control_character, line)) from e
        # END handle control character

        # from_to handling
        from_ref_string, to_ref_string = from_to.split(":")
        if flags & cls.DELETED:
            from_ref: Union[SymbolicReference, None] = None
        else:
            if from_ref_string == "(delete)":
                from_ref = None
            else:
                from_ref = Reference.from_path(remote.repo, from_ref_string)

        # commit handling, could be message or commit info
        old_commit: Optional[str] = None
        if summary.startswith("["):
            if "[rejected]" in summary:
                flags |= cls.REJECTED
            elif "[remote rejected]" in summary:
                flags |= cls.REMOTE_REJECTED
            elif "[remote failure]" in summary:
                flags |= cls.REMOTE_FAILURE
            elif "[no match]" in summary:
                flags |= cls.ERROR
            elif "[new tag]" in summary:
                flags |= cls.NEW_TAG
            elif "[new branch]" in summary:
                flags |= cls.NEW_HEAD
            # uptodate encoded in control character
        else:
            # fast-forward or forced update - was encoded in control character,
            # but we parse the old and new commit
            split_token = "..."
            if control_character == " ":
                split_token = ".."
            old_sha, _new_sha = summary.split(" ")[0].split(split_token)
            # have to use constructor here as the sha usually is abbreviated
            old_commit = old_sha
        # END message handling

        return PushInfo(flags, from_ref, to_ref_string, remote, old_commit, summary)

    @classmethod
    def iter_items(cls, repo: "Repo", *args: Any, **kwargs: Any) -> NoReturn:  # -> Iterator['PushInfo']:
        raise NotImplementedError


class PushInfoList(IterableList[PushInfo]):
    """
    IterableList of PushInfo objects.
    """

    def __new__(cls) -> "PushInfoList":
        return cast(PushInfoList, IterableList.__new__(cls, "push_infos"))

    def __init__(self) -> None:
        super().__init__("push_infos")
        self.error: Optional[Exception] = None

    def raise_if_error(self) -> None:
        """
        Raise an exception if any ref failed to push.
        """
        if self.error:
            raise self.error


class FetchInfo(IterableObj, object):

    """
    Carries information about the results of a fetch operation of a single head::

     info = remote.fetch()[0]
     info.ref           # Symbolic Reference or RemoteReference to the changed
                        # remote head or FETCH_HEAD
     info.flags         # additional flags to be & with enumeration members,
                        # i.e. info.flags & info.REJECTED
                        # is 0 if ref is SymbolicReference
     info.note          # additional notes given by git-fetch intended for the user
     info.old_commit    # if info.flags & info.FORCED_UPDATE|info.FAST_FORWARD,
                        # field is set to the previous location of ref, otherwise None
     info.remote_ref_path # The path from which we fetched on the remote. It's the remote's version of our info.ref
    """

    __slots__ = ("ref", "old_commit", "flags", "note", "remote_ref_path")
    _id_attribute_ = "fetchinfo"

    (
        NEW_TAG,
        NEW_HEAD,
        HEAD_UPTODATE,
        TAG_UPDATE,
        REJECTED,
        FORCED_UPDATE,
        FAST_FORWARD,
        ERROR,
    ) = [1 << x for x in range(8)]

    _re_fetch_result = re.compile(r"^\s*(.) (\[[\w\s\.$@]+\]|[\w\.$@]+)\s+(.+) -> ([^\s]+)(    \(.*\)?$)?")

    _flag_map: Dict[flagKeyLiteral, int] = {
        "!": ERROR,
        "+": FORCED_UPDATE,
        "*": 0,
        "=": HEAD_UPTODATE,
        " ": FAST_FORWARD,
        "-": TAG_UPDATE,
    }

    @classmethod
    def refresh(cls) -> Literal[True]:
        """This gets called by the refresh function (see the top level
        __init__).
        """
        # clear the old values in _flag_map
        try:
            del cls._flag_map["t"]
        except KeyError:
            pass

        try:
            del cls._flag_map["-"]
        except KeyError:
            pass

        # set the value given the git version
        if Git().version_info[:2] >= (2, 10):
            cls._flag_map["t"] = cls.TAG_UPDATE
        else:
            cls._flag_map["-"] = cls.TAG_UPDATE

        return True

    def __init__(
        self,
        ref: SymbolicReference,
        flags: int,
        note: str = "",
        old_commit: Union[Commit_ish, None] = None,
        remote_ref_path: Optional[PathLike] = None,
    ) -> None:
        """
        Initialize a new instance
        """
        self.ref = ref
        self.flags = flags
        self.note = note
        self.old_commit = old_commit
        self.remote_ref_path = remote_ref_path

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        """:return: Name of our remote ref"""
        return self.ref.name

    @property
    def commit(self) -> Commit_ish:
        """:return: Commit of our remote ref"""
        return self.ref.commit

    @classmethod
    def _from_line(cls, repo: "Repo", line: str, fetch_line: str) -> "FetchInfo":
        """Parse information from the given line as returned by git-fetch -v
        and return a new FetchInfo object representing this information.

        We can handle a line as follows:
        "%c %-\\*s %-\\*s -> %s%s"

        Where c is either ' ', !, +, -, \\*, or =
        ! means error
        + means success forcing update
        - means a tag was updated
        * means birth of new branch or tag
        = means the head was up to date ( and not moved )
        ' ' means a fast-forward

        fetch line is the corresponding line from FETCH_HEAD, like
        acb0fa8b94ef421ad60c8507b634759a472cd56c    not-for-merge   branch '0.1.7RC' of /tmp/tmpya0vairemote_repo"""
        match = cls._re_fetch_result.match(line)
        if match is None:
            raise ValueError("Failed to parse line: %r" % line)

        # parse lines
        remote_local_ref_str: str
        (
            control_character,
            operation,
            local_remote_ref,
            remote_local_ref_str,
            note,
        ) = match.groups()
        # assert is_flagKeyLiteral(control_character), f"{control_character}"
        control_character = cast(flagKeyLiteral, control_character)
        try:
            _new_hex_sha, _fetch_operation, fetch_note = fetch_line.split("\t")
            ref_type_name, fetch_note = fetch_note.split(" ", 1)
        except ValueError as e:  # unpack error
            raise ValueError("Failed to parse FETCH_HEAD line: %r" % fetch_line) from e

        # parse flags from control_character
        flags = 0
        try:
            flags |= cls._flag_map[control_character]
        except KeyError as e:
            raise ValueError("Control character %r unknown as parsed from line %r" % (control_character, line)) from e
        # END control char exception handling

        # parse operation string for more info - makes no sense for symbolic refs, but we parse it anyway
        old_commit: Union[Commit_ish, None] = None
        is_tag_operation = False
        if "rejected" in operation:
            flags |= cls.REJECTED
        if "new tag" in operation:
            flags |= cls.NEW_TAG
            is_tag_operation = True
        if "tag update" in operation:
            flags |= cls.TAG_UPDATE
            is_tag_operation = True
        if "new branch" in operation:
            flags |= cls.NEW_HEAD
        if "..." in operation or ".." in operation:
            split_token = "..."
            if control_character == " ":
                split_token = split_token[:-1]
            old_commit = repo.rev_parse(operation.split(split_token)[0])
        # END handle refspec

        # handle FETCH_HEAD and figure out ref type
        # If we do not specify a target branch like master:refs/remotes/origin/master,
        # the fetch result is stored in FETCH_HEAD which destroys the rule we usually
        # have. In that case we use a symbolic reference which is detached
        ref_type: Optional[Type[SymbolicReference]] = None
        if remote_local_ref_str == "FETCH_HEAD":
            ref_type = SymbolicReference
        elif ref_type_name == "tag" or is_tag_operation:
            # the ref_type_name can be branch, whereas we are still seeing a tag operation. It happens during
            # testing, which is based on actual git operations
            ref_type = TagReference
        elif ref_type_name in ("remote-tracking", "branch"):
            # note: remote-tracking is just the first part of the 'remote-tracking branch' token.
            # We don't parse it correctly, but its enough to know what to do, and its new in git 1.7something
            ref_type = RemoteReference
        elif "/" in ref_type_name:
            # If the fetch spec look something like this '+refs/pull/*:refs/heads/pull/*', and is thus pretty
            # much anything the user wants, we will have trouble to determine what's going on
            # For now, we assume the local ref is a Head
            ref_type = Head
        else:
            raise TypeError("Cannot handle reference type: %r" % ref_type_name)
        # END handle ref type

        # create ref instance
        if ref_type is SymbolicReference:
            remote_local_ref = ref_type(repo, "FETCH_HEAD")
        else:
            # determine prefix. Tags are usually pulled into refs/tags, they may have subdirectories.
            # It is not clear sometimes where exactly the item is, unless we have an absolute path as indicated
            # by the 'ref/' prefix. Otherwise even a tag could be in refs/remotes, which is when it will have the
            # 'tags/' subdirectory in its path.
            # We don't want to test for actual existence, but try to figure everything out analytically.
            ref_path: Optional[PathLike] = None
            remote_local_ref_str = remote_local_ref_str.strip()

            if remote_local_ref_str.startswith(Reference._common_path_default + "/"):
                # always use actual type if we get absolute paths
                # Will always be the case if something is fetched outside of refs/remotes (if its not a tag)
                ref_path = remote_local_ref_str
                if ref_type is not TagReference and not remote_local_ref_str.startswith(
                    RemoteReference._common_path_default + "/"
                ):
                    ref_type = Reference
                # END downgrade remote reference
            elif ref_type is TagReference and "tags/" in remote_local_ref_str:
                # even though its a tag, it is located in refs/remotes
                ref_path = join_path(RemoteReference._common_path_default, remote_local_ref_str)
            else:
                ref_path = join_path(ref_type._common_path_default, remote_local_ref_str)
            # END obtain refpath

            # even though the path could be within the git conventions, we make
            # sure we respect whatever the user wanted, and disabled path checking
            remote_local_ref = ref_type(repo, ref_path, check_path=False)
        # END create ref instance

        note = (note and note.strip()) or ""

        return cls(remote_local_ref, flags, note, old_commit, local_remote_ref)

    @classmethod
    def iter_items(cls, repo: "Repo", *args: Any, **kwargs: Any) -> NoReturn:  # -> Iterator['FetchInfo']:
        raise NotImplementedError


class Remote(LazyMixin, IterableObj):

    """Provides easy read and write access to a git remote.

    Everything not part of this interface is considered an option for the current
    remote, allowing constructs like remote.pushurl to query the pushurl.

    NOTE: When querying configuration, the configuration accessor will be cached
    to speed up subsequent accesses."""

    __slots__ = ("repo", "name", "_config_reader")
    _id_attribute_ = "name"

    unsafe_git_fetch_options = [
        # This option allows users to execute arbitrary commands.
        # https://git-scm.com/docs/git-fetch#Documentation/git-fetch.txt---upload-packltupload-packgt
        "--upload-pack",
    ]
    unsafe_git_pull_options = [
        # This option allows users to execute arbitrary commands.
        # https://git-scm.com/docs/git-pull#Documentation/git-pull.txt---upload-packltupload-packgt
        "--upload-pack"
    ]
    unsafe_git_push_options = [
        # This option allows users to execute arbitrary commands.
        # https://git-scm.com/docs/git-push#Documentation/git-push.txt---execltgit-receive-packgt
        "--receive-pack",
        "--exec",
    ]

    def __init__(self, repo: "Repo", name: str) -> None:
        """Initialize a remote instance

        :param repo: The repository we are a remote of
        :param name: the name of the remote, i.e. 'origin'"""
        self.repo = repo
        self.name = name
        self.url: str

    def __getattr__(self, attr: str) -> Any:
        """Allows to call this instance like
        remote.special( \\*args, \\*\\*kwargs) to call git-remote special self.name"""
        if attr == "_config_reader":
            return super(Remote, self).__getattr__(attr)

        # sometimes, probably due to a bug in python itself, we are being called
        # even though a slot of the same name exists
        try:
            return self._config_reader.get(attr)
        except cp.NoOptionError:
            return super(Remote, self).__getattr__(attr)
        # END handle exception

    def _config_section_name(self) -> str:
        return 'remote "%s"' % self.name

    def _set_cache_(self, attr: str) -> None:
        if attr == "_config_reader":
            # NOTE: This is cached as __getattr__ is overridden to return remote config values implicitly, such as
            # in print(r.pushurl)
            self._config_reader = SectionConstraint(self.repo.config_reader("repository"), self._config_section_name())
        else:
            super(Remote, self)._set_cache_(attr)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return '<git.%s "%s">' % (self.__class__.__name__, self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.name == other.name

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        return hash(self.name)

    def exists(self) -> bool:
        """
        :return: True if this is a valid, existing remote.
            Valid remotes have an entry in the repository's configuration"""
        try:
            self.config_reader.get("url")
            return True
        except cp.NoOptionError:
            # we have the section at least ...
            return True
        except cp.NoSectionError:
            return False
        # end

    @classmethod
    def iter_items(cls, repo: "Repo", *args: Any, **kwargs: Any) -> Iterator["Remote"]:
        """:return: Iterator yielding Remote objects of the given repository"""
        for section in repo.config_reader("repository").sections():
            if not section.startswith("remote "):
                continue
            lbound = section.find('"')
            rbound = section.rfind('"')
            if lbound == -1 or rbound == -1:
                raise ValueError("Remote-Section has invalid format: %r" % section)
            yield Remote(repo, section[lbound + 1 : rbound])
        # END for each configuration section

    def set_url(
        self, new_url: str, old_url: Optional[str] = None, allow_unsafe_protocols: bool = False, **kwargs: Any
    ) -> "Remote":
        """Configure URLs on current remote (cf command git remote set_url)

        This command manages URLs on the remote.

        :param new_url: string being the URL to add as an extra remote URL
        :param old_url: when set, replaces this URL with new_url for the remote
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :return: self
        """
        if not allow_unsafe_protocols:
            Git.check_unsafe_protocols(new_url)
        scmd = "set-url"
        kwargs["insert_kwargs_after"] = scmd
        if old_url:
            self.repo.git.remote(scmd, "--", self.name, new_url, old_url, **kwargs)
        else:
            self.repo.git.remote(scmd, "--", self.name, new_url, **kwargs)
        return self

    def add_url(self, url: str, allow_unsafe_protocols: bool = False, **kwargs: Any) -> "Remote":
        """Adds a new url on current remote (special case of git remote set_url)

        This command adds new URLs to a given remote, making it possible to have
        multiple URLs for a single remote.

        :param url: string being the URL to add as an extra remote URL
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :return: self
        """
        return self.set_url(url, add=True, allow_unsafe_protocols=allow_unsafe_protocols)

    def delete_url(self, url: str, **kwargs: Any) -> "Remote":
        """Deletes a new url on current remote (special case of git remote set_url)

        This command deletes new URLs to a given remote, making it possible to have
        multiple URLs for a single remote.

        :param url: string being the URL to delete from the remote
        :return: self
        """
        return self.set_url(url, delete=True)

    @property
    def urls(self) -> Iterator[str]:
        """:return: Iterator yielding all configured URL targets on a remote as strings"""
        try:
            remote_details = self.repo.git.remote("get-url", "--all", self.name)
            assert isinstance(remote_details, str)
            for line in remote_details.split("\n"):
                yield line
        except GitCommandError as ex:
            ## We are on git < 2.7 (i.e TravisCI as of Oct-2016),
            #  so `get-utl` command does not exist yet!
            #    see: https://github.com/gitpython-developers/GitPython/pull/528#issuecomment-252976319
            #    and: http://stackoverflow.com/a/32991784/548792
            #
            if "Unknown subcommand: get-url" in str(ex):
                try:
                    remote_details = self.repo.git.remote("show", self.name)
                    assert isinstance(remote_details, str)
                    for line in remote_details.split("\n"):
                        if "  Push  URL:" in line:
                            yield line.split(": ")[-1]
                except GitCommandError as _ex:
                    if any(msg in str(_ex) for msg in ["correct access rights", "cannot run ssh"]):
                        # If ssh is not setup to access this repository, see issue 694
                        remote_details = self.repo.git.config("--get-all", "remote.%s.url" % self.name)
                        assert isinstance(remote_details, str)
                        for line in remote_details.split("\n"):
                            yield line
                    else:
                        raise _ex
            else:
                raise ex

    @property
    def refs(self) -> IterableList[RemoteReference]:
        """
        :return:
            IterableList of RemoteReference objects. It is prefixed, allowing
            you to omit the remote path portion, i.e.::
            remote.refs.master # yields RemoteReference('/refs/remotes/origin/master')"""
        out_refs: IterableList[RemoteReference] = IterableList(RemoteReference._id_attribute_, "%s/" % self.name)
        out_refs.extend(RemoteReference.list_items(self.repo, remote=self.name))
        return out_refs

    @property
    def stale_refs(self) -> IterableList[Reference]:
        """
        :return:
            IterableList RemoteReference objects that do not have a corresponding
            head in the remote reference anymore as they have been deleted on the
            remote side, but are still available locally.

            The IterableList is prefixed, hence the 'origin' must be omitted. See
            'refs' property for an example.

            To make things more complicated, it can be possible for the list to include
            other kinds of references, for example, tag references, if these are stale
            as well. This is a fix for the issue described here:
            https://github.com/gitpython-developers/GitPython/issues/260
        """
        out_refs: IterableList[Reference] = IterableList(RemoteReference._id_attribute_, "%s/" % self.name)
        for line in self.repo.git.remote("prune", "--dry-run", self).splitlines()[2:]:
            # expecting
            # * [would prune] origin/new_branch
            token = " * [would prune] "
            if not line.startswith(token):
                continue
            ref_name = line.replace(token, "")
            # sometimes, paths start with a full ref name, like refs/tags/foo, see #260
            if ref_name.startswith(Reference._common_path_default + "/"):
                out_refs.append(Reference.from_path(self.repo, ref_name))
            else:
                fqhn = "%s/%s" % (RemoteReference._common_path_default, ref_name)
                out_refs.append(RemoteReference(self.repo, fqhn))
            # end special case handling
        # END for each line
        return out_refs

    @classmethod
    def create(cls, repo: "Repo", name: str, url: str, allow_unsafe_protocols: bool = False, **kwargs: Any) -> "Remote":
        """Create a new remote to the given repository

        :param repo: Repository instance that is to receive the new remote
        :param name: Desired name of the remote
        :param url: URL which corresponds to the remote's name
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param kwargs: Additional arguments to be passed to the git-remote add command
        :return: New Remote instance
        :raise GitCommandError: in case an origin with that name already exists"""
        scmd = "add"
        kwargs["insert_kwargs_after"] = scmd
        url = Git.polish_url(url)
        if not allow_unsafe_protocols:
            Git.check_unsafe_protocols(url)
        repo.git.remote(scmd, "--", name, url, **kwargs)
        return cls(repo, name)

    # add is an alias
    @classmethod
    def add(cls, repo: "Repo", name: str, url: str, **kwargs: Any) -> "Remote":
        return cls.create(repo, name, url, **kwargs)

    @classmethod
    def remove(cls, repo: "Repo", name: str) -> str:
        """Remove the remote with the given name

        :return: the passed remote name to remove
        """
        repo.git.remote("rm", name)
        if isinstance(name, cls):
            name._clear_cache()
        return name

    # alias
    rm = remove

    def rename(self, new_name: str) -> "Remote":
        """Rename self to the given new_name

        :return: self"""
        if self.name == new_name:
            return self

        self.repo.git.remote("rename", self.name, new_name)
        self.name = new_name
        self._clear_cache()

        return self

    def update(self, **kwargs: Any) -> "Remote":
        """Fetch all changes for this remote, including new branches which will
        be forced in ( in case your local remote branch is not part the new remote branches
        ancestry anymore ).

        :param kwargs:
            Additional arguments passed to git-remote update

        :return: self"""
        scmd = "update"
        kwargs["insert_kwargs_after"] = scmd
        self.repo.git.remote(scmd, self.name, **kwargs)
        return self

    def _get_fetch_info_from_stderr(
        self,
        proc: "Git.AutoInterrupt",
        progress: Union[Callable[..., Any], RemoteProgress, None],
        kill_after_timeout: Union[None, float] = None,
    ) -> IterableList["FetchInfo"]:

        progress = to_progress_instance(progress)

        # skip first line as it is some remote info we are not interested in
        output: IterableList["FetchInfo"] = IterableList("name")

        # lines which are no progress are fetch info lines
        # this also waits for the command to finish
        # Skip some progress lines that don't provide relevant information
        fetch_info_lines = []
        # Basically we want all fetch info lines which appear to be in regular form, and thus have a
        # command character. Everything else we ignore,
        cmds = set(FetchInfo._flag_map.keys())

        progress_handler = progress.new_message_handler()
        handle_process_output(
            proc,
            None,
            progress_handler,
            finalizer=None,
            decode_streams=False,
            kill_after_timeout=kill_after_timeout,
        )

        stderr_text = progress.error_lines and "\n".join(progress.error_lines) or ""
        proc.wait(stderr=stderr_text)
        if stderr_text:
            log.warning("Error lines received while fetching: %s", stderr_text)

        for line in progress.other_lines:
            line = force_text(line)
            for cmd in cmds:
                if len(line) > 1 and line[0] == " " and line[1] == cmd:
                    fetch_info_lines.append(line)
                    continue

        # read head information
        fetch_head = SymbolicReference(self.repo, "FETCH_HEAD")
        with open(fetch_head.abspath, "rb") as fp:
            fetch_head_info = [line.decode(defenc) for line in fp.readlines()]

        l_fil = len(fetch_info_lines)
        l_fhi = len(fetch_head_info)
        if l_fil != l_fhi:
            msg = "Fetch head lines do not match lines provided via progress information\n"
            msg += "length of progress lines %i should be equal to lines in FETCH_HEAD file %i\n"
            msg += "Will ignore extra progress lines or fetch head lines."
            msg %= (l_fil, l_fhi)
            log.debug(msg)
            log.debug(b"info lines: " + str(fetch_info_lines).encode("UTF-8"))
            log.debug(b"head info: " + str(fetch_head_info).encode("UTF-8"))
            if l_fil < l_fhi:
                fetch_head_info = fetch_head_info[:l_fil]
            else:
                fetch_info_lines = fetch_info_lines[:l_fhi]
            # end truncate correct list
        # end sanity check + sanitization

        for err_line, fetch_line in zip(fetch_info_lines, fetch_head_info):
            try:
                output.append(FetchInfo._from_line(self.repo, err_line, fetch_line))
            except ValueError as exc:
                log.debug("Caught error while parsing line: %s", exc)
                log.warning("Git informed while fetching: %s", err_line.strip())
        return output

    def _get_push_info(
        self,
        proc: "Git.AutoInterrupt",
        progress: Union[Callable[..., Any], RemoteProgress, None],
        kill_after_timeout: Union[None, float] = None,
    ) -> PushInfoList:
        progress = to_progress_instance(progress)

        # read progress information from stderr
        # we hope stdout can hold all the data, it should ...
        # read the lines manually as it will use carriage returns between the messages
        # to override the previous one. This is why we read the bytes manually
        progress_handler = progress.new_message_handler()
        output: PushInfoList = PushInfoList()

        def stdout_handler(line: str) -> None:
            try:
                output.append(PushInfo._from_line(self, line))
            except ValueError:
                # If an error happens, additional info is given which we parse below.
                pass

        handle_process_output(
            proc,
            stdout_handler,
            progress_handler,
            finalizer=None,
            decode_streams=False,
            kill_after_timeout=kill_after_timeout,
        )
        stderr_text = progress.error_lines and "\n".join(progress.error_lines) or ""
        try:
            proc.wait(stderr=stderr_text)
        except Exception as e:
            # This is different than fetch (which fails if there is any std_err
            # even if there is an output)
            if not output:
                raise
            elif stderr_text:
                log.warning("Error lines received while fetching: %s", stderr_text)
                output.error = e

        return output

    def _assert_refspec(self) -> None:
        """Turns out we can't deal with remotes if the refspec is missing"""
        config = self.config_reader
        unset = "placeholder"
        try:
            if config.get_value("fetch", default=unset) is unset:
                msg = "Remote '%s' has no refspec set.\n"
                msg += "You can set it as follows:"
                msg += " 'git config --add \"remote.%s.fetch +refs/heads/*:refs/heads/*\"'."
                raise AssertionError(msg % (self.name, self.name))
        finally:
            config.release()

    def fetch(
        self,
        refspec: Union[str, List[str], None] = None,
        progress: Union[RemoteProgress, None, "UpdateProgress"] = None,
        verbose: bool = True,
        kill_after_timeout: Union[None, float] = None,
        allow_unsafe_protocols: bool = False,
        allow_unsafe_options: bool = False,
        **kwargs: Any,
    ) -> IterableList[FetchInfo]:
        """Fetch the latest changes for this remote

        :param refspec:
            A "refspec" is used by fetch and push to describe the mapping
            between remote ref and local ref. They are combined with a colon in
            the format <src>:<dst>, preceded by an optional plus sign, +.
            For example: git fetch $URL refs/heads/master:refs/heads/origin means
            "grab the master branch head from the $URL and store it as my origin
            branch head". And git push $URL refs/heads/master:refs/heads/to-upstream
            means "publish my master branch head as to-upstream branch at $URL".
            See also git-push(1).

            Taken from the git manual

            Fetch supports multiple refspecs (as the
            underlying git-fetch does) - supplying a list rather than a string
            for 'refspec' will make use of this facility.
        :param progress: See 'push' method
        :param verbose: Boolean for verbose output
        :param kill_after_timeout:
            To specify a timeout in seconds for the git command, after which the process
            should be killed. It is set to None by default.
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --upload-pack
        :param kwargs: Additional arguments to be passed to git-fetch
        :return:
            IterableList(FetchInfo, ...) list of FetchInfo instances providing detailed
            information about the fetch results

        :note:
            As fetch does not provide progress information to non-ttys, we cannot make
            it available here unfortunately as in the 'push' method."""
        if refspec is None:
            # No argument refspec, then ensure the repo's config has a fetch refspec.
            self._assert_refspec()

        kwargs = add_progress(kwargs, self.repo.git, progress)
        if isinstance(refspec, list):
            args: Sequence[Optional[str]] = refspec
        else:
            args = [refspec]

        if not allow_unsafe_protocols:
            for ref in args:
                if ref:
                    Git.check_unsafe_protocols(ref)

        if not allow_unsafe_options:
            Git.check_unsafe_options(options=list(kwargs.keys()), unsafe_options=self.unsafe_git_fetch_options)

        proc = self.repo.git.fetch(
            "--", self, *args, as_process=True, with_stdout=False, universal_newlines=True, v=verbose, **kwargs
        )
        res = self._get_fetch_info_from_stderr(proc, progress, kill_after_timeout=kill_after_timeout)
        if hasattr(self.repo.odb, "update_cache"):
            self.repo.odb.update_cache()
        return res

    def pull(
        self,
        refspec: Union[str, List[str], None] = None,
        progress: Union[RemoteProgress, "UpdateProgress", None] = None,
        kill_after_timeout: Union[None, float] = None,
        allow_unsafe_protocols: bool = False,
        allow_unsafe_options: bool = False,
        **kwargs: Any,
    ) -> IterableList[FetchInfo]:
        """Pull changes from the given branch, being the same as a fetch followed
        by a merge of branch with your local branch.

        :param refspec: see :meth:`fetch` method
        :param progress: see :meth:`push` method
        :param kill_after_timeout: see :meth:`fetch` method
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --upload-pack
        :param kwargs: Additional arguments to be passed to git-pull
        :return: Please see :meth:`fetch` method"""
        if refspec is None:
            # No argument refspec, then ensure the repo's config has a fetch refspec.
            self._assert_refspec()
        kwargs = add_progress(kwargs, self.repo.git, progress)

        refspec = Git._unpack_args(refspec or [])
        if not allow_unsafe_protocols:
            for ref in refspec:
                Git.check_unsafe_protocols(ref)

        if not allow_unsafe_options:
            Git.check_unsafe_options(options=list(kwargs.keys()), unsafe_options=self.unsafe_git_pull_options)

        proc = self.repo.git.pull(
            "--", self, refspec, with_stdout=False, as_process=True, universal_newlines=True, v=True, **kwargs
        )
        res = self._get_fetch_info_from_stderr(proc, progress, kill_after_timeout=kill_after_timeout)
        if hasattr(self.repo.odb, "update_cache"):
            self.repo.odb.update_cache()
        return res

    def push(
        self,
        refspec: Union[str, List[str], None] = None,
        progress: Union[RemoteProgress, "UpdateProgress", Callable[..., RemoteProgress], None] = None,
        kill_after_timeout: Union[None, float] = None,
        allow_unsafe_protocols: bool = False,
        allow_unsafe_options: bool = False,
        **kwargs: Any,
    ) -> PushInfoList:
        """Push changes from source branch in refspec to target branch in refspec.

        :param refspec: see 'fetch' method
        :param progress:
            Can take one of many value types:

            * None to discard progress information
            * A function (callable) that is called with the progress information.
              Signature: ``progress(op_code, cur_count, max_count=None, message='')``.
              `Click here <http://goo.gl/NPa7st>`__ for a description of all arguments
              given to the function.
            * An instance of a class derived from ``git.RemoteProgress`` that
              overrides the ``update()`` function.

        :note: No further progress information is returned after push returns.
        :param kill_after_timeout:
            To specify a timeout in seconds for the git command, after which the process
            should be killed. It is set to None by default.
        :param allow_unsafe_protocols: Allow unsafe protocols to be used, like ext
        :param allow_unsafe_options: Allow unsafe options to be used, like --receive-pack
        :param kwargs: Additional arguments to be passed to git-push
        :return:
            A ``PushInfoList`` object, where each list member
            represents an individual head which had been updated on the remote side.
            If the push contains rejected heads, these will have the PushInfo.ERROR bit set
            in their flags.
            If the operation fails completely, the length of the returned PushInfoList will
            be 0.
            Call ``.raise_if_error()`` on the returned object to raise on any failure."""
        kwargs = add_progress(kwargs, self.repo.git, progress)

        refspec = Git._unpack_args(refspec or [])
        if not allow_unsafe_protocols:
            for ref in refspec:
                Git.check_unsafe_protocols(ref)

        if not allow_unsafe_options:
            Git.check_unsafe_options(options=list(kwargs.keys()), unsafe_options=self.unsafe_git_push_options)

        proc = self.repo.git.push(
            "--",
            self,
            refspec,
            porcelain=True,
            as_process=True,
            universal_newlines=True,
            kill_after_timeout=kill_after_timeout,
            **kwargs,
        )
        return self._get_push_info(proc, progress, kill_after_timeout=kill_after_timeout)

    @property
    def config_reader(self) -> SectionConstraint[GitConfigParser]:
        """
        :return:
            GitConfigParser compatible object able to read options for only our remote.
            Hence you may simple type config.get("pushurl") to obtain the information"""
        return self._config_reader

    def _clear_cache(self) -> None:
        try:
            del self._config_reader
        except AttributeError:
            pass
        # END handle exception

    @property
    def config_writer(self) -> SectionConstraint:
        """
        :return: GitConfigParser compatible object able to write options for this remote.
        :note:
            You can only own one writer at a time - delete it to release the
            configuration file and make it usable by others.

            To assure consistent results, you should only query options through the
            writer. Once you are done writing, you are free to use the config reader
            once again."""
        writer = self.repo.config_writer()

        # clear our cache to assure we re-read the possibly changed configuration
        self._clear_cache()
        return SectionConstraint(writer, self._config_section_name())
