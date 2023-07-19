# commit.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
import datetime
import re
from subprocess import Popen, PIPE
from gitdb import IStream
from git.util import hex_to_bin, Actor, Stats, finalize_process
from git.diff import Diffable
from git.cmd import Git

from .tree import Tree
from . import base
from .util import (
    Serializable,
    TraversableIterableObj,
    parse_date,
    altz_to_utctz_str,
    parse_actor_and_date,
    from_timestamp,
)

from time import time, daylight, altzone, timezone, localtime
import os
from io import BytesIO
import logging
from collections import defaultdict


# typing ------------------------------------------------------------------

from typing import (
    Any,
    IO,
    Iterator,
    List,
    Sequence,
    Tuple,
    Union,
    TYPE_CHECKING,
    cast,
    Dict,
)

from git.types import PathLike, Literal

if TYPE_CHECKING:
    from git.repo import Repo
    from git.refs import SymbolicReference

# ------------------------------------------------------------------------

log = logging.getLogger("git.objects.commit")
log.addHandler(logging.NullHandler())

__all__ = ("Commit",)


class Commit(base.Object, TraversableIterableObj, Diffable, Serializable):

    """Wraps a git Commit object.

    This class will act lazily on some of its attributes and will query the
    value on demand only if it involves calling the git binary."""

    # ENVIRONMENT VARIABLES
    # read when creating new commits
    env_author_date = "GIT_AUTHOR_DATE"
    env_committer_date = "GIT_COMMITTER_DATE"

    # CONFIGURATION KEYS
    conf_encoding = "i18n.commitencoding"

    # INVARIANTS
    default_encoding = "UTF-8"

    # object configuration
    type: Literal["commit"] = "commit"
    __slots__ = (
        "tree",
        "author",
        "authored_date",
        "author_tz_offset",
        "committer",
        "committed_date",
        "committer_tz_offset",
        "message",
        "parents",
        "encoding",
        "gpgsig",
    )
    _id_attribute_ = "hexsha"

    def __init__(
        self,
        repo: "Repo",
        binsha: bytes,
        tree: Union[Tree, None] = None,
        author: Union[Actor, None] = None,
        authored_date: Union[int, None] = None,
        author_tz_offset: Union[None, float] = None,
        committer: Union[Actor, None] = None,
        committed_date: Union[int, None] = None,
        committer_tz_offset: Union[None, float] = None,
        message: Union[str, bytes, None] = None,
        parents: Union[Sequence["Commit"], None] = None,
        encoding: Union[str, None] = None,
        gpgsig: Union[str, None] = None,
    ) -> None:
        """Instantiate a new Commit. All keyword arguments taking None as default will
        be implicitly set on first query.

        :param binsha: 20 byte sha1
        :param parents: tuple( Commit, ... )
            is a tuple of commit ids or actual Commits
        :param tree: Tree object
        :param author: Actor
            is the author Actor object
        :param authored_date: int_seconds_since_epoch
            is the authored DateTime - use time.gmtime() to convert it into a
            different format
        :param author_tz_offset: int_seconds_west_of_utc
            is the timezone that the authored_date is in
        :param committer: Actor
            is the committer string
        :param committed_date: int_seconds_since_epoch
            is the committed DateTime - use time.gmtime() to convert it into a
            different format
        :param committer_tz_offset: int_seconds_west_of_utc
            is the timezone that the committed_date is in
        :param message: string
            is the commit message
        :param encoding: string
            encoding of the message, defaults to UTF-8
        :param parents:
            List or tuple of Commit objects which are our parent(s) in the commit
            dependency graph
        :return: git.Commit

        :note:
            Timezone information is in the same format and in the same sign
            as what time.altzone returns. The sign is inverted compared to git's
            UTC timezone."""
        super(Commit, self).__init__(repo, binsha)
        self.binsha = binsha
        if tree is not None:
            assert isinstance(tree, Tree), "Tree needs to be a Tree instance, was %s" % type(tree)
        if tree is not None:
            self.tree = tree
        if author is not None:
            self.author = author
        if authored_date is not None:
            self.authored_date = authored_date
        if author_tz_offset is not None:
            self.author_tz_offset = author_tz_offset
        if committer is not None:
            self.committer = committer
        if committed_date is not None:
            self.committed_date = committed_date
        if committer_tz_offset is not None:
            self.committer_tz_offset = committer_tz_offset
        if message is not None:
            self.message = message
        if parents is not None:
            self.parents = parents
        if encoding is not None:
            self.encoding = encoding
        if gpgsig is not None:
            self.gpgsig = gpgsig

    @classmethod
    def _get_intermediate_items(cls, commit: "Commit") -> Tuple["Commit", ...]:
        return tuple(commit.parents)

    @classmethod
    def _calculate_sha_(cls, repo: "Repo", commit: "Commit") -> bytes:
        """Calculate the sha of a commit.

        :param repo: Repo object the commit should be part of
        :param commit: Commit object for which to generate the sha
        """

        stream = BytesIO()
        commit._serialize(stream)
        streamlen = stream.tell()
        stream.seek(0)

        istream = repo.odb.store(IStream(cls.type, streamlen, stream))
        return istream.binsha

    def replace(self, **kwargs: Any) -> "Commit":
        """Create new commit object from existing commit object.

        Any values provided as keyword arguments will replace the
        corresponding attribute in the new object.
        """

        attrs = {k: getattr(self, k) for k in self.__slots__}

        for attrname in kwargs:
            if attrname not in self.__slots__:
                raise ValueError("invalid attribute name")

        attrs.update(kwargs)
        new_commit = self.__class__(self.repo, self.NULL_BIN_SHA, **attrs)
        new_commit.binsha = self._calculate_sha_(self.repo, new_commit)

        return new_commit

    def _set_cache_(self, attr: str) -> None:
        if attr in Commit.__slots__:
            # read the data in a chunk, its faster - then provide a file wrapper
            _binsha, _typename, self.size, stream = self.repo.odb.stream(self.binsha)
            self._deserialize(BytesIO(stream.read()))
        else:
            super(Commit, self)._set_cache_(attr)
        # END handle attrs

    @property
    def authored_datetime(self) -> datetime.datetime:
        return from_timestamp(self.authored_date, self.author_tz_offset)

    @property
    def committed_datetime(self) -> datetime.datetime:
        return from_timestamp(self.committed_date, self.committer_tz_offset)

    @property
    def summary(self) -> Union[str, bytes]:
        """:return: First line of the commit message"""
        if isinstance(self.message, str):
            return self.message.split("\n", 1)[0]
        else:
            return self.message.split(b"\n", 1)[0]

    def count(self, paths: Union[PathLike, Sequence[PathLike]] = "", **kwargs: Any) -> int:
        """Count the number of commits reachable from this commit

        :param paths:
            is an optional path or a list of paths restricting the return value
            to commits actually containing the paths

        :param kwargs:
            Additional options to be passed to git-rev-list. They must not alter
            the output style of the command, or parsing will yield incorrect results
        :return: int defining the number of reachable commits"""
        # yes, it makes a difference whether empty paths are given or not in our case
        # as the empty paths version will ignore merge commits for some reason.
        if paths:
            return len(self.repo.git.rev_list(self.hexsha, "--", paths, **kwargs).splitlines())
        return len(self.repo.git.rev_list(self.hexsha, **kwargs).splitlines())

    @property
    def name_rev(self) -> str:
        """
        :return:
            String describing the commits hex sha based on the closest Reference.
            Mostly useful for UI purposes"""
        return self.repo.git.name_rev(self)

    @classmethod
    def iter_items(
        cls,
        repo: "Repo",
        rev: Union[str, "Commit", "SymbolicReference"],  # type: ignore
        paths: Union[PathLike, Sequence[PathLike]] = "",
        **kwargs: Any,
    ) -> Iterator["Commit"]:
        """Find all commits matching the given criteria.

        :param repo: is the Repo
        :param rev: revision specifier, see git-rev-parse for viable options
        :param paths:
            is an optional path or list of paths, if set only Commits that include the path
            or paths will be considered
        :param kwargs:
            optional keyword arguments to git rev-list where
            ``max_count`` is the maximum number of commits to fetch
            ``skip`` is the number of commits to skip
            ``since`` all commits since i.e. '1970-01-01'
        :return: iterator yielding Commit items"""
        if "pretty" in kwargs:
            raise ValueError("--pretty cannot be used as parsing expects single sha's only")
        # END handle pretty

        # use -- in any case, to prevent possibility of ambiguous arguments
        # see https://github.com/gitpython-developers/GitPython/issues/264

        args_list: List[PathLike] = ["--"]

        if paths:
            paths_tup: Tuple[PathLike, ...]
            if isinstance(paths, (str, os.PathLike)):
                paths_tup = (paths,)
            else:
                paths_tup = tuple(paths)

            args_list.extend(paths_tup)
        # END if paths

        proc = repo.git.rev_list(rev, args_list, as_process=True, **kwargs)
        return cls._iter_from_process_or_stream(repo, proc)

    def iter_parents(self, paths: Union[PathLike, Sequence[PathLike]] = "", **kwargs: Any) -> Iterator["Commit"]:
        """Iterate _all_ parents of this commit.

        :param paths:
            Optional path or list of paths limiting the Commits to those that
            contain at least one of the paths
        :param kwargs: All arguments allowed by git-rev-list
        :return: Iterator yielding Commit objects which are parents of self"""
        # skip ourselves
        skip = kwargs.get("skip", 1)
        if skip == 0:  # skip ourselves
            skip = 1
        kwargs["skip"] = skip

        return self.iter_items(self.repo, self, paths, **kwargs)

    @property
    def stats(self) -> Stats:
        """Create a git stat from changes between this commit and its first parent
        or from all changes done if this is the very first commit.

        :return: git.Stats"""
        if not self.parents:
            text = self.repo.git.diff_tree(self.hexsha, "--", numstat=True, no_renames=True, root=True)
            text2 = ""
            for line in text.splitlines()[1:]:
                (insertions, deletions, filename) = line.split("\t")
                text2 += "%s\t%s\t%s\n" % (insertions, deletions, filename)
            text = text2
        else:
            text = self.repo.git.diff(self.parents[0].hexsha, self.hexsha, "--", numstat=True, no_renames=True)
        return Stats._list_from_string(self.repo, text)

    @property
    def trailers(self) -> Dict[str, str]:
        """Get the trailers of the message as a dictionary

        :note: This property is deprecated, please use either ``Commit.trailers_list`` or ``Commit.trailers_dict``.

        :return:
            Dictionary containing whitespace stripped trailer information.
            Only contains the latest instance of each trailer key.
        """
        return {
            k: v[0] for k, v in self.trailers_dict.items()
        }

    @property
    def trailers_list(self) -> List[Tuple[str, str]]:
        """Get the trailers of the message as a list

        Git messages can contain trailer information that are similar to RFC 822
        e-mail headers (see: https://git-scm.com/docs/git-interpret-trailers).

        This functions calls ``git interpret-trailers --parse`` onto the message
        to extract the trailer information, returns the raw trailer data as a list.

        Valid message with trailer::

            Subject line

            some body information

            another information

            key1: value1.1
            key1: value1.2
            key2 :    value 2 with inner spaces


        Returned list will look like this::

            [
                ("key1", "value1.1"),
                ("key1", "value1.2"),
                ("key2", "value 2 with inner spaces"),
            ]


        :return:
            List containing key-value tuples of whitespace stripped trailer information.
        """
        cmd = ["git", "interpret-trailers", "--parse"]
        proc: Git.AutoInterrupt = self.repo.git.execute(cmd, as_process=True, istream=PIPE)  # type: ignore
        trailer: str = proc.communicate(str(self.message).encode())[0].decode("utf8")
        trailer = trailer.strip()

        if not trailer:
            return []

        trailer_list = []
        for t in trailer.split("\n"):
            key, val = t.split(":", 1)
            trailer_list.append((key.strip(), val.strip()))

        return trailer_list

    @property
    def trailers_dict(self) -> Dict[str, List[str]]:
        """Get the trailers of the message as a dictionary

        Git messages can contain trailer information that are similar to RFC 822
        e-mail headers (see: https://git-scm.com/docs/git-interpret-trailers).

        This functions calls ``git interpret-trailers --parse`` onto the message
        to extract the trailer information. The key value pairs are stripped of
        leading and trailing whitespaces before they get saved into a dictionary.

        Valid message with trailer::

            Subject line

            some body information

            another information

            key1: value1.1
            key1: value1.2
            key2 :    value 2 with inner spaces


        Returned dictionary will look like this::

            {
                "key1": ["value1.1", "value1.2"],
                "key2": ["value 2 with inner spaces"],
            }


        :return:
            Dictionary containing whitespace stripped trailer information.
            Mapping trailer keys to a list of their corresponding values.
        """
        d = defaultdict(list)
        for key, val in self.trailers_list:
            d[key].append(val)
        return dict(d)

    @classmethod
    def _iter_from_process_or_stream(cls, repo: "Repo", proc_or_stream: Union[Popen, IO]) -> Iterator["Commit"]:
        """Parse out commit information into a list of Commit objects
        We expect one-line per commit, and parse the actual commit information directly
        from our lighting fast object database

        :param proc: git-rev-list process instance - one sha per line
        :return: iterator returning Commit objects"""

        # def is_proc(inp) -> TypeGuard[Popen]:
        #     return hasattr(proc_or_stream, 'wait') and not hasattr(proc_or_stream, 'readline')

        # def is_stream(inp) -> TypeGuard[IO]:
        #     return hasattr(proc_or_stream, 'readline')

        if hasattr(proc_or_stream, "wait"):
            proc_or_stream = cast(Popen, proc_or_stream)
            if proc_or_stream.stdout is not None:
                stream = proc_or_stream.stdout
        elif hasattr(proc_or_stream, "readline"):
            proc_or_stream = cast(IO, proc_or_stream)
            stream = proc_or_stream

        readline = stream.readline
        while True:
            line = readline()
            if not line:
                break
            hexsha = line.strip()
            if len(hexsha) > 40:
                # split additional information, as returned by bisect for instance
                hexsha, _ = line.split(None, 1)
            # END handle extra info

            assert len(hexsha) == 40, "Invalid line: %s" % hexsha
            yield cls(repo, hex_to_bin(hexsha))
        # END for each line in stream
        # TODO: Review this - it seems process handling got a bit out of control
        # due to many developers trying to fix the open file handles issue
        if hasattr(proc_or_stream, "wait"):
            proc_or_stream = cast(Popen, proc_or_stream)
            finalize_process(proc_or_stream)

    @classmethod
    def create_from_tree(
        cls,
        repo: "Repo",
        tree: Union[Tree, str],
        message: str,
        parent_commits: Union[None, List["Commit"]] = None,
        head: bool = False,
        author: Union[None, Actor] = None,
        committer: Union[None, Actor] = None,
        author_date: Union[None, str, datetime.datetime] = None,
        commit_date: Union[None, str, datetime.datetime] = None,
    ) -> "Commit":
        """Commit the given tree, creating a commit object.

        :param repo: Repo object the commit should be part of
        :param tree: Tree object or hex or bin sha
            the tree of the new commit
        :param message: Commit message. It may be an empty string if no message is provided.
            It will be converted to a string , in any case.
        :param parent_commits:
            Optional Commit objects to use as parents for the new commit.
            If empty list, the commit will have no parents at all and become
            a root commit.
            If None , the current head commit will be the parent of the
            new commit object
        :param head:
            If True, the HEAD will be advanced to the new commit automatically.
            Else the HEAD will remain pointing on the previous commit. This could
            lead to undesired results when diffing files.
        :param author: The name of the author, optional. If unset, the repository
            configuration is used to obtain this value.
        :param committer: The name of the committer, optional. If unset, the
            repository configuration is used to obtain this value.
        :param author_date: The timestamp for the author field
        :param commit_date: The timestamp for the committer field

        :return: Commit object representing the new commit

        :note:
            Additional information about the committer and Author are taken from the
            environment or from the git configuration, see git-commit-tree for
            more information"""
        if parent_commits is None:
            try:
                parent_commits = [repo.head.commit]
            except ValueError:
                # empty repositories have no head commit
                parent_commits = []
            # END handle parent commits
        else:
            for p in parent_commits:
                if not isinstance(p, cls):
                    raise ValueError(f"Parent commit '{p!r}' must be of type {cls}")
            # end check parent commit types
        # END if parent commits are unset

        # retrieve all additional information, create a commit object, and
        # serialize it
        # Generally:
        # * Environment variables override configuration values
        # * Sensible defaults are set according to the git documentation

        # COMMITTER AND AUTHOR INFO
        cr = repo.config_reader()
        env = os.environ

        committer = committer or Actor.committer(cr)
        author = author or Actor.author(cr)

        # PARSE THE DATES
        unix_time = int(time())
        is_dst = daylight and localtime().tm_isdst > 0
        offset = altzone if is_dst else timezone

        author_date_str = env.get(cls.env_author_date, "")
        if author_date:
            author_time, author_offset = parse_date(author_date)
        elif author_date_str:
            author_time, author_offset = parse_date(author_date_str)
        else:
            author_time, author_offset = unix_time, offset
        # END set author time

        committer_date_str = env.get(cls.env_committer_date, "")
        if commit_date:
            committer_time, committer_offset = parse_date(commit_date)
        elif committer_date_str:
            committer_time, committer_offset = parse_date(committer_date_str)
        else:
            committer_time, committer_offset = unix_time, offset
        # END set committer time

        # assume utf8 encoding
        enc_section, enc_option = cls.conf_encoding.split(".")
        conf_encoding = cr.get_value(enc_section, enc_option, cls.default_encoding)
        if not isinstance(conf_encoding, str):
            raise TypeError("conf_encoding could not be coerced to str")

        # if the tree is no object, make sure we create one - otherwise
        # the created commit object is invalid
        if isinstance(tree, str):
            tree = repo.tree(tree)
        # END tree conversion

        # CREATE NEW COMMIT
        new_commit = cls(
            repo,
            cls.NULL_BIN_SHA,
            tree,
            author,
            author_time,
            author_offset,
            committer,
            committer_time,
            committer_offset,
            message,
            parent_commits,
            conf_encoding,
        )

        new_commit.binsha = cls._calculate_sha_(repo, new_commit)

        if head:
            # need late import here, importing git at the very beginning throws
            # as well ...
            import git.refs

            try:
                repo.head.set_commit(new_commit, logmsg=message)
            except ValueError:
                # head is not yet set to the ref our HEAD points to
                # Happens on first commit
                master = git.refs.Head.create(
                    repo,
                    repo.head.ref,
                    new_commit,
                    logmsg="commit (initial): %s" % message,
                )
                repo.head.set_reference(master, logmsg="commit: Switching to %s" % master)
            # END handle empty repositories
        # END advance head handling

        return new_commit

    # { Serializable Implementation

    def _serialize(self, stream: BytesIO) -> "Commit":
        write = stream.write
        write(("tree %s\n" % self.tree).encode("ascii"))
        for p in self.parents:
            write(("parent %s\n" % p).encode("ascii"))

        a = self.author
        aname = a.name
        c = self.committer
        fmt = "%s %s <%s> %s %s\n"
        write(
            (
                fmt
                % (
                    "author",
                    aname,
                    a.email,
                    self.authored_date,
                    altz_to_utctz_str(self.author_tz_offset),
                )
            ).encode(self.encoding)
        )

        # encode committer
        aname = c.name
        write(
            (
                fmt
                % (
                    "committer",
                    aname,
                    c.email,
                    self.committed_date,
                    altz_to_utctz_str(self.committer_tz_offset),
                )
            ).encode(self.encoding)
        )

        if self.encoding != self.default_encoding:
            write(("encoding %s\n" % self.encoding).encode("ascii"))

        try:
            if self.__getattribute__("gpgsig"):
                write(b"gpgsig")
                for sigline in self.gpgsig.rstrip("\n").split("\n"):
                    write((" " + sigline + "\n").encode("ascii"))
        except AttributeError:
            pass

        write(b"\n")

        # write plain bytes, be sure its encoded according to our encoding
        if isinstance(self.message, str):
            write(self.message.encode(self.encoding))
        else:
            write(self.message)
        # END handle encoding
        return self

    def _deserialize(self, stream: BytesIO) -> "Commit":
        """
        :param from_rev_list: if true, the stream format is coming from the rev-list command
            Otherwise it is assumed to be a plain data stream from our object
        """
        readline = stream.readline
        self.tree = Tree(self.repo, hex_to_bin(readline().split()[1]), Tree.tree_id << 12, "")

        self.parents = []
        next_line = None
        while True:
            parent_line = readline()
            if not parent_line.startswith(b"parent"):
                next_line = parent_line
                break
            # END abort reading parents
            self.parents.append(type(self)(self.repo, hex_to_bin(parent_line.split()[-1].decode("ascii"))))
        # END for each parent line
        self.parents = tuple(self.parents)

        # we don't know actual author encoding before we have parsed it, so keep the lines around
        author_line = next_line
        committer_line = readline()

        # we might run into one or more mergetag blocks, skip those for now
        next_line = readline()
        while next_line.startswith(b"mergetag "):
            next_line = readline()
            while next_line.startswith(b" "):
                next_line = readline()
        # end skip mergetags

        # now we can have the encoding line, or an empty line followed by the optional
        # message.
        self.encoding = self.default_encoding
        self.gpgsig = ""

        # read headers
        enc = next_line
        buf = enc.strip()
        while buf:
            if buf[0:10] == b"encoding ":
                self.encoding = buf[buf.find(b" ") + 1 :].decode(self.encoding, "ignore")
            elif buf[0:7] == b"gpgsig ":
                sig = buf[buf.find(b" ") + 1 :] + b"\n"
                is_next_header = False
                while True:
                    sigbuf = readline()
                    if not sigbuf:
                        break
                    if sigbuf[0:1] != b" ":
                        buf = sigbuf.strip()
                        is_next_header = True
                        break
                    sig += sigbuf[1:]
                # end read all signature
                self.gpgsig = sig.rstrip(b"\n").decode(self.encoding, "ignore")
                if is_next_header:
                    continue
            buf = readline().strip()
        # decode the authors name

        try:
            (
                self.author,
                self.authored_date,
                self.author_tz_offset,
            ) = parse_actor_and_date(author_line.decode(self.encoding, "replace"))
        except UnicodeDecodeError:
            log.error(
                "Failed to decode author line '%s' using encoding %s",
                author_line,
                self.encoding,
                exc_info=True,
            )

        try:
            (
                self.committer,
                self.committed_date,
                self.committer_tz_offset,
            ) = parse_actor_and_date(committer_line.decode(self.encoding, "replace"))
        except UnicodeDecodeError:
            log.error(
                "Failed to decode committer line '%s' using encoding %s",
                committer_line,
                self.encoding,
                exc_info=True,
            )
        # END handle author's encoding

        # a stream from our data simply gives us the plain message
        # The end of our message stream is marked with a newline that we strip
        self.message = stream.read()
        try:
            self.message = self.message.decode(self.encoding, "replace")
        except UnicodeDecodeError:
            log.error(
                "Failed to decode message '%s' using encoding %s",
                self.message,
                self.encoding,
                exc_info=True,
            )
        # END exception handling

        return self

    # } END serializable implementation

    @property
    def co_authors(self) -> List[Actor]:
        """
        Search the commit message for any co-authors of this commit.
        Details on co-authors: https://github.blog/2018-01-29-commit-together-with-co-authors/

        :return: List of co-authors for this commit (as Actor objects).
        """
        co_authors = []

        if self.message:
            results = re.findall(
                r"^Co-authored-by: (.*) <(.*?)>$",
                self.message,
                re.MULTILINE,
            )
            for author in results:
                co_authors.append(Actor(*author))

        return co_authors
