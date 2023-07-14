# porcelain.py -- Porcelain-like layer on top of Dulwich
# Copyright (C) 2013 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Simple wrapper that provides porcelain-like functions on top of Dulwich.

Currently implemented:
 * archive
 * add
 * branch{_create,_delete,_list}
 * check-ignore
 * checkout_branch
 * clone
 * commit
 * commit-tree
 * daemon
 * describe
 * diff-tree
 * fetch
 * init
 * ls-files
 * ls-remote
 * ls-tree
 * pull
 * push
 * rm
 * remote{_add}
 * receive-pack
 * reset
 * submodule_add
 * submodule_init
 * submodule_list
 * rev-list
 * tag{_create,_delete,_list}
 * upload-pack
 * update-server-info
 * status
 * symbolic-ref

These functions are meant to behave similarly to the git subcommands.
Differences in behaviour are considered bugs.

Note: one of the consequences of this is that paths tend to be
interpreted relative to the current working directory rather than relative
to the repository root.

Functions should generally accept both unicode strings and bytestrings
"""

import datetime
import os
import posixpath
import stat
import sys
import time
from collections import namedtuple
from contextlib import closing, contextmanager
from io import BytesIO, RawIOBase
from pathlib import Path
from typing import Optional, Tuple, Union

from .archive import tar_stream
from .client import get_transport_and_path
from .config import Config, ConfigFile, StackedConfig, read_submodules
from .diff_tree import (CHANGE_ADD, CHANGE_COPY, CHANGE_DELETE, CHANGE_MODIFY,
                        CHANGE_RENAME, RENAME_CHANGE_TYPES)
from .errors import SendPackError
from .file import ensure_dir_exists
from .graph import can_fast_forward
from .ignore import IgnoreFilterManager
from .index import (_fs_to_tree_path, blob_from_path_and_stat,
                    build_file_from_blob, get_unstaged_changes,
                    index_entry_from_stat)
from .object_store import iter_tree_contents, tree_lookup_path
from .objects import (Commit, Tag, format_timezone, parse_timezone,
                      pretty_format_tree_entry)
from .objectspec import (parse_commit, parse_object, parse_ref,
                         parse_reftuples, parse_tree, to_bytes)
from .pack import write_pack_from_container, write_pack_index
from .patch import write_tree_diff
from .protocol import ZERO_SHA, Protocol
from .refs import (LOCAL_BRANCH_PREFIX, LOCAL_REMOTE_PREFIX, LOCAL_TAG_PREFIX,
                   _import_remote_refs)
from .repo import BaseRepo, Repo
from .server import (FileSystemBackend, ReceivePackHandler, TCPGitServer,
                     UploadPackHandler)
from .server import update_server_info as server_update_server_info

# Module level tuple definition for status output
GitStatus = namedtuple("GitStatus", "staged unstaged untracked")


class NoneStream(RawIOBase):
    """Fallback if stdout or stderr are unavailable, does nothing."""

    def read(self, size=-1):
        return None

    def readall(self):
        return None

    def readinto(self, b):
        return None

    def write(self, b):
        return None


default_bytes_out_stream = getattr(sys.stdout, "buffer", None) or NoneStream()
default_bytes_err_stream = getattr(sys.stderr, "buffer", None) or NoneStream()


DEFAULT_ENCODING = "utf-8"


class Error(Exception):
    """Porcelain-based error. """

    def __init__(self, msg):
        super().__init__(msg)


class RemoteExists(Error):
    """Raised when the remote already exists."""


class TimezoneFormatError(Error):
    """Raised when the timezone cannot be determined from a given string."""


class CheckoutError(Error):
    """Indicates that a checkout cannot be performed."""


def parse_timezone_format(tz_str):
    """Parse given string and attempt to return a timezone offset.

    Different formats are considered in the following order:

     - Git internal format: <unix timestamp> <timezone offset>
     - RFC 2822: e.g. Mon, 20 Nov 1995 19:12:08 -0500
     - ISO 8601: e.g. 1995-11-20T19:12:08-0500

    Args:
      tz_str: datetime string
    Returns: Timezone offset as integer
    Raises:
      TimezoneFormatError: if timezone information cannot be extracted
   """
    import re

    # Git internal format
    internal_format_pattern = re.compile("^[0-9]+ [+-][0-9]{,4}$")
    if re.match(internal_format_pattern, tz_str):
        try:
            tz_internal = parse_timezone(tz_str.split(" ")[1].encode(DEFAULT_ENCODING))
            return tz_internal[0]
        except ValueError:
            pass

    # RFC 2822
    import email.utils
    rfc_2822 = email.utils.parsedate_tz(tz_str)
    if rfc_2822:
        return rfc_2822[9]

    # ISO 8601

    # Supported offsets:
    # sHHMM, sHH:MM, sHH
    iso_8601_pattern = re.compile("[0-9] ?([+-])([0-9]{2})(?::(?=[0-9]{2}))?([0-9]{2})?$")
    match = re.search(iso_8601_pattern, tz_str)
    total_secs = 0
    if match:
        sign, hours, minutes = match.groups()
        total_secs += int(hours) * 3600
        if minutes:
            total_secs += int(minutes) * 60
        total_secs = -total_secs if sign == "-" else total_secs
        return total_secs

    # YYYY.MM.DD, MM/DD/YYYY, DD.MM.YYYY contain no timezone information

    raise TimezoneFormatError(tz_str)


def get_user_timezones():
    """Retrieve local timezone as described in
    https://raw.githubusercontent.com/git/git/v2.3.0/Documentation/date-formats.txt
    Returns: A tuple containing author timezone, committer timezone
    """
    local_timezone = time.localtime().tm_gmtoff

    if os.environ.get("GIT_AUTHOR_DATE"):
        author_timezone = parse_timezone_format(os.environ["GIT_AUTHOR_DATE"])
    else:
        author_timezone = local_timezone
    if os.environ.get("GIT_COMMITTER_DATE"):
        commit_timezone = parse_timezone_format(os.environ["GIT_COMMITTER_DATE"])
    else:
        commit_timezone = local_timezone

    return author_timezone, commit_timezone


def open_repo(path_or_repo):
    """Open an argument that can be a repository or a path for a repository."""
    if isinstance(path_or_repo, BaseRepo):
        return path_or_repo
    return Repo(path_or_repo)


@contextmanager
def _noop_context_manager(obj):
    """Context manager that has the same api as closing but does nothing."""
    yield obj


def open_repo_closing(path_or_repo):
    """Open an argument that can be a repository or a path for a repository.
    returns a context manager that will close the repo on exit if the argument
    is a path, else does nothing if the argument is a repo.
    """
    if isinstance(path_or_repo, BaseRepo):
        return _noop_context_manager(path_or_repo)
    return closing(Repo(path_or_repo))


def path_to_tree_path(repopath, path, tree_encoding=DEFAULT_ENCODING):
    """Convert a path to a path usable in an index, e.g. bytes and relative to
    the repository root.

    Args:
      repopath: Repository path, absolute or relative to the cwd
      path: A path, absolute or relative to the cwd
    Returns: A path formatted for use in e.g. an index
    """
    # Resolve might returns a relative path on Windows
    # https://bugs.python.org/issue38671
    if sys.platform == "win32":
        path = os.path.abspath(path)

    path = Path(path)
    resolved_path = path.resolve()

    # Resolve and abspath seems to behave differently regarding symlinks,
    # as we are doing abspath on the file path, we need to do the same on
    # the repo path or they might not match
    if sys.platform == "win32":
        repopath = os.path.abspath(repopath)

    repopath = Path(repopath).resolve()

    try:
        relpath = resolved_path.relative_to(repopath)
    except ValueError:
        # If path is a symlink that points to a file outside the repo, we
        # want the relpath for the link itself, not the resolved target
        if path.is_symlink():
            parent = path.parent.resolve()
            relpath = (parent / path.name).relative_to(repopath)
        else:
            raise
    if sys.platform == "win32":
        return str(relpath).replace(os.path.sep, "/").encode(tree_encoding)
    else:
        return bytes(relpath)


class DivergedBranches(Error):
    """Branches have diverged and fast-forward is not possible."""

    def __init__(self, current_sha, new_sha):
        self.current_sha = current_sha
        self.new_sha = new_sha


def check_diverged(repo, current_sha, new_sha):
    """Check if updating to a sha can be done with fast forwarding.

    Args:
      repo: Repository object
      current_sha: Current head sha
      new_sha: New head sha
    """
    try:
        can = can_fast_forward(repo, current_sha, new_sha)
    except KeyError:
        can = False
    if not can:
        raise DivergedBranches(current_sha, new_sha)


def archive(
    repo,
    committish=None,
    outstream=default_bytes_out_stream,
    errstream=default_bytes_err_stream,
):
    """Create an archive.

    Args:
      repo: Path of repository for which to generate an archive.
      committish: Commit SHA1 or ref to use
      outstream: Output stream (defaults to stdout)
      errstream: Error stream (defaults to stderr)
    """

    if committish is None:
        committish = "HEAD"
    with open_repo_closing(repo) as repo_obj:
        c = parse_commit(repo_obj, committish)
        for chunk in tar_stream(
            repo_obj.object_store, repo_obj.object_store[c.tree], c.commit_time
        ):
            outstream.write(chunk)


def update_server_info(repo="."):
    """Update server info files for a repository.

    Args:
      repo: path to the repository
    """
    with open_repo_closing(repo) as r:
        server_update_server_info(r)


def symbolic_ref(repo, ref_name, force=False):
    """Set git symbolic ref into HEAD.

    Args:
      repo: path to the repository
      ref_name: short name of the new ref
      force: force settings without checking if it exists in refs/heads
    """
    with open_repo_closing(repo) as repo_obj:
        ref_path = _make_branch_ref(ref_name)
        if not force and ref_path not in repo_obj.refs.keys():
            raise Error("fatal: ref `%s` is not a ref" % ref_name)
        repo_obj.refs.set_symbolic_ref(b"HEAD", ref_path)


def pack_refs(repo, all=False):
    with open_repo_closing(repo) as repo_obj:
        refs = repo_obj.refs
        packed_refs = {
            ref: refs[ref]
            for ref in refs
            if (all or ref.startswith(LOCAL_TAG_PREFIX)) and ref != b"HEAD"
        }

        refs.add_packed_refs(packed_refs)


def commit(
    repo=".",
    message=None,
    author=None,
    author_timezone=None,
    committer=None,
    commit_timezone=None,
    encoding=None,
    no_verify=False,
    signoff=False,
):
    """Create a new commit.

    Args:
      repo: Path to repository
      message: Optional commit message
      author: Optional author name and email
      author_timezone: Author timestamp timezone
      committer: Optional committer name and email
      commit_timezone: Commit timestamp timezone
      no_verify: Skip pre-commit and commit-msg hooks
      signoff: GPG Sign the commit (bool, defaults to False,
        pass True to use default GPG key,
        pass a str containing Key ID to use a specific GPG key)
    Returns: SHA1 of the new commit
    """
    # FIXME: Support --all argument
    if getattr(message, "encode", None):
        message = message.encode(encoding or DEFAULT_ENCODING)
    if getattr(author, "encode", None):
        author = author.encode(encoding or DEFAULT_ENCODING)
    if getattr(committer, "encode", None):
        committer = committer.encode(encoding or DEFAULT_ENCODING)
    local_timezone = get_user_timezones()
    if author_timezone is None:
        author_timezone = local_timezone[0]
    if commit_timezone is None:
        commit_timezone = local_timezone[1]
    with open_repo_closing(repo) as r:
        return r.do_commit(
            message=message,
            author=author,
            author_timezone=author_timezone,
            committer=committer,
            commit_timezone=commit_timezone,
            encoding=encoding,
            no_verify=no_verify,
            sign=signoff if isinstance(signoff, (str, bool)) else None,
        )


def commit_tree(repo, tree, message=None, author=None, committer=None):
    """Create a new commit object.

    Args:
      repo: Path to repository
      tree: An existing tree object
      author: Optional author name and email
      committer: Optional committer name and email
    """
    with open_repo_closing(repo) as r:
        return r.do_commit(
            message=message, tree=tree, committer=committer, author=author
        )


def init(path=".", *, bare=False, symlinks: Optional[bool] = None):
    """Create a new git repository.

    Args:
      path: Path to repository.
      bare: Whether to create a bare repository.
      symlinks: Whether to create actual symlinks (defaults to autodetect)
    Returns: A Repo instance
    """
    if not os.path.exists(path):
        os.mkdir(path)

    if bare:
        return Repo.init_bare(path)
    else:
        return Repo.init(path, symlinks=symlinks)


def clone(
    source,
    target=None,
    bare=False,
    checkout=None,
    errstream=default_bytes_err_stream,
    outstream=None,
    origin: Optional[str] = "origin",
    depth: Optional[int] = None,
    branch: Optional[Union[str, bytes]] = None,
    config: Optional[Config] = None,
    **kwargs
):
    """Clone a local or remote git repository.

    Args:
      source: Path or URL for source repository
      target: Path to target repository (optional)
      bare: Whether or not to create a bare repository
      checkout: Whether or not to check-out HEAD after cloning
      errstream: Optional stream to write progress to
      outstream: Optional stream to write progress to (deprecated)
      origin: Name of remote from the repository used to clone
      depth: Depth to fetch at
      branch: Optional branch or tag to be used as HEAD in the new repository
        instead of the cloned repository's HEAD.
      config: Configuration to use
    Returns: The new repository
    """
    if outstream is not None:
        import warnings

        warnings.warn(
            "outstream= has been deprecated in favour of errstream=.",
            DeprecationWarning,
            stacklevel=3,
        )
        # TODO(jelmer): Capture logging output and stream to errstream

    if config is None:
        config = StackedConfig.default()

    if checkout is None:
        checkout = not bare
    if checkout and bare:
        raise Error("checkout and bare are incompatible")

    if target is None:
        target = source.split("/")[-1]

    if isinstance(branch, str):
        branch = branch.encode(DEFAULT_ENCODING)

    mkdir = not os.path.exists(target)

    (client, path) = get_transport_and_path(
        source, config=config, **kwargs)

    return client.clone(
        path,
        target,
        mkdir=mkdir,
        bare=bare,
        origin=origin,
        checkout=checkout,
        branch=branch,
        progress=errstream.write,
        depth=depth,
    )


def add(repo=".", paths=None):
    """Add files to the staging area.

    Args:
      repo: Repository for the files
      paths: Paths to add.  No value passed stages all modified files.
    Returns: Tuple with set of added files and ignored files

    If the repository contains ignored directories, the returned set will
    contain the path to an ignored directory (with trailing slash). Individual
    files within ignored directories will not be returned.
    """
    ignored = set()
    with open_repo_closing(repo) as r:
        repo_path = Path(r.path).resolve()
        ignore_manager = IgnoreFilterManager.from_repo(r)
        if not paths:
            paths = list(
                get_untracked_paths(
                    str(Path(os.getcwd()).resolve()),
                    str(repo_path),
                    r.open_index(),
                )
            )
        relpaths = []
        if not isinstance(paths, list):
            paths = [paths]
        for p in paths:
            path = Path(p)
            relpath = str(path.resolve().relative_to(repo_path))
            # FIXME: Support patterns
            if path.is_dir():
                relpath = os.path.join(relpath, "")
            if ignore_manager.is_ignored(relpath):
                ignored.add(relpath)
                continue
            relpaths.append(relpath)
        r.stage(relpaths)
    return (relpaths, ignored)


def _is_subdir(subdir, parentdir):
    """Check whether subdir is parentdir or a subdir of parentdir

    If parentdir or subdir is a relative path, it will be disamgibuated
    relative to the pwd.
    """
    parentdir_abs = os.path.realpath(parentdir) + os.path.sep
    subdir_abs = os.path.realpath(subdir) + os.path.sep
    return subdir_abs.startswith(parentdir_abs)


# TODO: option to remove ignored files also, in line with `git clean -fdx`
def clean(repo=".", target_dir=None):
    """Remove any untracked files from the target directory recursively

    Equivalent to running ``git clean -fd`` in target_dir.

    Args:
      repo: Repository where the files may be tracked
      target_dir: Directory to clean - current directory if None
    """
    if target_dir is None:
        target_dir = os.getcwd()

    with open_repo_closing(repo) as r:
        if not _is_subdir(target_dir, r.path):
            raise Error("target_dir must be in the repo's working dir")

        config = r.get_config_stack()
        require_force = config.get_boolean(  # noqa: F841
            (b"clean",), b"requireForce", True
        )

        # TODO(jelmer): if require_force is set, then make sure that -f, -i or
        # -n is specified.

        index = r.open_index()
        ignore_manager = IgnoreFilterManager.from_repo(r)

        paths_in_wd = _walk_working_dir_paths(target_dir, r.path)
        # Reverse file visit order, so that files and subdirectories are
        # removed before containing directory
        for ap, is_dir in reversed(list(paths_in_wd)):
            if is_dir:
                # All subdirectories and files have been removed if untracked,
                # so dir contains no tracked files iff it is empty.
                is_empty = len(os.listdir(ap)) == 0
                if is_empty:
                    os.rmdir(ap)
            else:
                ip = path_to_tree_path(r.path, ap)
                is_tracked = ip in index

                rp = os.path.relpath(ap, r.path)
                is_ignored = ignore_manager.is_ignored(rp)

                if not is_tracked and not is_ignored:
                    os.remove(ap)


def remove(repo=".", paths=None, cached=False):
    """Remove files from the staging area.

    Args:
      repo: Repository for the files
      paths: Paths to remove
    """
    with open_repo_closing(repo) as r:
        index = r.open_index()
        for p in paths:
            full_path = os.fsencode(os.path.abspath(p))
            tree_path = path_to_tree_path(r.path, p)
            try:
                index_sha = index[tree_path].sha
            except KeyError as exc:
                raise Error("%s did not match any files" % p) from exc

            if not cached:
                try:
                    st = os.lstat(full_path)
                except OSError:
                    pass
                else:
                    try:
                        blob = blob_from_path_and_stat(full_path, st)
                    except OSError:
                        pass
                    else:
                        try:
                            committed_sha = tree_lookup_path(
                                r.__getitem__, r[r.head()].tree, tree_path
                            )[1]
                        except KeyError:
                            committed_sha = None

                        if blob.id != index_sha and index_sha != committed_sha:
                            raise Error(
                                "file has staged content differing "
                                "from both the file and head: %s" % p
                            )

                        if index_sha != committed_sha:
                            raise Error("file has staged changes: %s" % p)
                        os.remove(full_path)
            del index[tree_path]
        index.write()


rm = remove


def commit_decode(commit, contents, default_encoding=DEFAULT_ENCODING):
    if commit.encoding:
        encoding = commit.encoding.decode("ascii")
    else:
        encoding = default_encoding
    return contents.decode(encoding, "replace")


def commit_encode(commit, contents, default_encoding=DEFAULT_ENCODING):
    if commit.encoding:
        encoding = commit.encoding.decode("ascii")
    else:
        encoding = default_encoding
    return contents.encode(encoding)


def print_commit(commit, decode, outstream=sys.stdout):
    """Write a human-readable commit log entry.

    Args:
      commit: A `Commit` object
      outstream: A stream file to write to
    """
    outstream.write("-" * 50 + "\n")
    outstream.write("commit: " + commit.id.decode("ascii") + "\n")
    if len(commit.parents) > 1:
        outstream.write(
            "merge: "
            + "...".join([c.decode("ascii") for c in commit.parents[1:]])
            + "\n"
        )
    outstream.write("Author: " + decode(commit.author) + "\n")
    if commit.author != commit.committer:
        outstream.write("Committer: " + decode(commit.committer) + "\n")

    time_tuple = time.gmtime(commit.author_time + commit.author_timezone)
    time_str = time.strftime("%a %b %d %Y %H:%M:%S", time_tuple)
    timezone_str = format_timezone(commit.author_timezone).decode("ascii")
    outstream.write("Date:   " + time_str + " " + timezone_str + "\n")
    outstream.write("\n")
    outstream.write(decode(commit.message) + "\n")
    outstream.write("\n")


def print_tag(tag, decode, outstream=sys.stdout):
    """Write a human-readable tag.

    Args:
      tag: A `Tag` object
      decode: Function for decoding bytes to unicode string
      outstream: A stream to write to
    """
    outstream.write("Tagger: " + decode(tag.tagger) + "\n")
    time_tuple = time.gmtime(tag.tag_time + tag.tag_timezone)
    time_str = time.strftime("%a %b %d %Y %H:%M:%S", time_tuple)
    timezone_str = format_timezone(tag.tag_timezone).decode("ascii")
    outstream.write("Date:   " + time_str + " " + timezone_str + "\n")
    outstream.write("\n")
    outstream.write(decode(tag.message))
    outstream.write("\n")


def show_blob(repo, blob, decode, outstream=sys.stdout):
    """Write a blob to a stream.

    Args:
      repo: A `Repo` object
      blob: A `Blob` object
      decode: Function for decoding bytes to unicode string
      outstream: A stream file to write to
    """
    outstream.write(decode(blob.data))


def show_commit(repo, commit, decode, outstream=sys.stdout):
    """Show a commit to a stream.

    Args:
      repo: A `Repo` object
      commit: A `Commit` object
      decode: Function for decoding bytes to unicode string
      outstream: Stream to write to
    """
    print_commit(commit, decode=decode, outstream=outstream)
    if commit.parents:
        parent_commit = repo[commit.parents[0]]
        base_tree = parent_commit.tree
    else:
        base_tree = None
    diffstream = BytesIO()
    write_tree_diff(diffstream, repo.object_store, base_tree, commit.tree)
    diffstream.seek(0)
    outstream.write(commit_decode(commit, diffstream.getvalue()))


def show_tree(repo, tree, decode, outstream=sys.stdout):
    """Print a tree to a stream.

    Args:
      repo: A `Repo` object
      tree: A `Tree` object
      decode: Function for decoding bytes to unicode string
      outstream: Stream to write to
    """
    for n in tree:
        outstream.write(decode(n) + "\n")


def show_tag(repo, tag, decode, outstream=sys.stdout):
    """Print a tag to a stream.

    Args:
      repo: A `Repo` object
      tag: A `Tag` object
      decode: Function for decoding bytes to unicode string
      outstream: Stream to write to
    """
    print_tag(tag, decode, outstream)
    show_object(repo, repo[tag.object[1]], decode, outstream)


def show_object(repo, obj, decode, outstream):
    return {
        b"tree": show_tree,
        b"blob": show_blob,
        b"commit": show_commit,
        b"tag": show_tag,
    }[obj.type_name](repo, obj, decode, outstream)


def print_name_status(changes):
    """Print a simple status summary, listing changed files."""
    for change in changes:
        if not change:
            continue
        if isinstance(change, list):
            change = change[0]
        if change.type == CHANGE_ADD:
            path1 = change.new.path
            path2 = ""
            kind = "A"
        elif change.type == CHANGE_DELETE:
            path1 = change.old.path
            path2 = ""
            kind = "D"
        elif change.type == CHANGE_MODIFY:
            path1 = change.new.path
            path2 = ""
            kind = "M"
        elif change.type in RENAME_CHANGE_TYPES:
            path1 = change.old.path
            path2 = change.new.path
            if change.type == CHANGE_RENAME:
                kind = "R"
            elif change.type == CHANGE_COPY:
                kind = "C"
        yield "%-8s%-20s%-20s" % (kind, path1, path2)


def log(
    repo=".",
    paths=None,
    outstream=sys.stdout,
    max_entries=None,
    reverse=False,
    name_status=False,
):
    """Write commit logs.

    Args:
      repo: Path to repository
      paths: Optional set of specific paths to print entries for
      outstream: Stream to write log output to
      reverse: Reverse order in which entries are printed
      name_status: Print name status
      max_entries: Optional maximum number of entries to display
    """
    with open_repo_closing(repo) as r:
        walker = r.get_walker(max_entries=max_entries, paths=paths, reverse=reverse)
        for entry in walker:

            def decode(x):
                return commit_decode(entry.commit, x)

            print_commit(entry.commit, decode, outstream)
            if name_status:
                outstream.writelines(
                    [line + "\n" for line in print_name_status(entry.changes())]
                )


# TODO(jelmer): better default for encoding?
def show(
    repo=".",
    objects=None,
    outstream=sys.stdout,
    default_encoding=DEFAULT_ENCODING,
):
    """Print the changes in a commit.

    Args:
      repo: Path to repository
      objects: Objects to show (defaults to [HEAD])
      outstream: Stream to write to
      default_encoding: Default encoding to use if none is set in the
        commit
    """
    if objects is None:
        objects = ["HEAD"]
    if not isinstance(objects, list):
        objects = [objects]
    with open_repo_closing(repo) as r:
        for objectish in objects:
            o = parse_object(r, objectish)
            if isinstance(o, Commit):

                def decode(x):
                    return commit_decode(o, x, default_encoding)

            else:

                def decode(x):
                    return x.decode(default_encoding)

            show_object(r, o, decode, outstream)


def diff_tree(repo, old_tree, new_tree, outstream=default_bytes_out_stream):
    """Compares the content and mode of blobs found via two tree objects.

    Args:
      repo: Path to repository
      old_tree: Id of old tree
      new_tree: Id of new tree
      outstream: Stream to write to
    """
    with open_repo_closing(repo) as r:
        write_tree_diff(outstream, r.object_store, old_tree, new_tree)


def rev_list(repo, commits, outstream=sys.stdout):
    """Lists commit objects in reverse chronological order.

    Args:
      repo: Path to repository
      commits: Commits over which to iterate
      outstream: Stream to write to
    """
    with open_repo_closing(repo) as r:
        for entry in r.get_walker(include=[r[c].id for c in commits]):
            outstream.write(entry.commit.id + b"\n")


def _canonical_part(url: str) -> str:
    name = url.rsplit('/', 1)[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name


def submodule_add(repo, url, path=None, name=None):
    """Add a new submodule.

    Args:
      repo: Path to repository
      url: URL of repository to add as submodule
      path: Path where submodule should live
    """
    with open_repo_closing(repo) as r:
        if path is None:
            path = os.path.relpath(_canonical_part(url), r.path)
        if name is None:
            name = path

        # TODO(jelmer): Move this logic to dulwich.submodule
        gitmodules_path = os.path.join(r.path, ".gitmodules")
        try:
            config = ConfigFile.from_path(gitmodules_path)
        except FileNotFoundError:
            config = ConfigFile()
            config.path = gitmodules_path
        config.set(("submodule", name), "url", url)
        config.set(("submodule", name), "path", path)
        config.write_to_path()


def submodule_init(repo):
    """Initialize submodules.

    Args:
      repo: Path to repository
    """
    with open_repo_closing(repo) as r:
        config = r.get_config()
        gitmodules_path = os.path.join(r.path, '.gitmodules')
        for path, url, name in read_submodules(gitmodules_path):
            config.set((b'submodule', name), b'active', True)
            config.set((b'submodule', name), b'url', url)
        config.write_to_path()


def submodule_list(repo):
    """List submodules.

    Args:
      repo: Path to repository
    """
    from .submodule import iter_cached_submodules
    with open_repo_closing(repo) as r:
        for path, sha in iter_cached_submodules(r.object_store, r[r.head()].tree):
            yield path, sha.decode(DEFAULT_ENCODING)


def tag_create(
    repo,
    tag,
    author=None,
    message=None,
    annotated=False,
    objectish="HEAD",
    tag_time=None,
    tag_timezone=None,
    sign=False,
    encoding=DEFAULT_ENCODING
):
    """Creates a tag in git via dulwich calls:

    Args:
      repo: Path to repository
      tag: tag string
      author: tag author (optional, if annotated is set)
      message: tag message (optional)
      annotated: whether to create an annotated tag
      objectish: object the tag should point at, defaults to HEAD
      tag_time: Optional time for annotated tag
      tag_timezone: Optional timezone for annotated tag
      sign: GPG Sign the tag (bool, defaults to False,
        pass True to use default GPG key,
        pass a str containing Key ID to use a specific GPG key)
    """

    with open_repo_closing(repo) as r:
        object = parse_object(r, objectish)

        if annotated:
            # Create the tag object
            tag_obj = Tag()
            if author is None:
                # TODO(jelmer): Don't use repo private method.
                author = r._get_user_identity(r.get_config_stack())
            tag_obj.tagger = author
            tag_obj.message = message + "\n".encode(encoding)
            tag_obj.name = tag
            tag_obj.object = (type(object), object.id)
            if tag_time is None:
                tag_time = int(time.time())
            tag_obj.tag_time = tag_time
            if tag_timezone is None:
                tag_timezone = get_user_timezones()[1]
            elif isinstance(tag_timezone, str):
                tag_timezone = parse_timezone(tag_timezone)
            tag_obj.tag_timezone = tag_timezone
            if sign:
                tag_obj.sign(sign if isinstance(sign, str) else None)

            r.object_store.add_object(tag_obj)
            tag_id = tag_obj.id
        else:
            tag_id = object.id

        r.refs[_make_tag_ref(tag)] = tag_id


def tag_list(repo, outstream=sys.stdout):
    """List all tags.

    Args:
      repo: Path to repository
      outstream: Stream to write tags to
    """
    with open_repo_closing(repo) as r:
        tags = sorted(r.refs.as_dict(b"refs/tags"))
        return tags


def tag_delete(repo, name):
    """Remove a tag.

    Args:
      repo: Path to repository
      name: Name of tag to remove
    """
    with open_repo_closing(repo) as r:
        if isinstance(name, bytes):
            names = [name]
        elif isinstance(name, list):
            names = name
        else:
            raise Error("Unexpected tag name type %r" % name)
        for name in names:
            del r.refs[_make_tag_ref(name)]


def reset(repo, mode, treeish="HEAD"):
    """Reset current HEAD to the specified state.

    Args:
      repo: Path to repository
      mode: Mode ("hard", "soft", "mixed")
      treeish: Treeish to reset to
    """

    if mode != "hard":
        raise Error("hard is the only mode currently supported")

    with open_repo_closing(repo) as r:
        tree = parse_tree(r, treeish)
        r.reset_index(tree.id)


def get_remote_repo(
    repo: Repo, remote_location: Optional[Union[str, bytes]] = None
) -> Tuple[Optional[str], str]:
    config = repo.get_config()
    if remote_location is None:
        remote_location = get_branch_remote(repo)
    if isinstance(remote_location, str):
        encoded_location = remote_location.encode()
    else:
        encoded_location = remote_location

    section = (b"remote", encoded_location)

    remote_name: Optional[str] = None

    if config.has_section(section):
        remote_name = encoded_location.decode()
        encoded_location = config.get(section, "url")
    else:
        remote_name = None

    return (remote_name, encoded_location.decode())


def push(
    repo,
    remote_location=None,
    refspecs=None,
    outstream=default_bytes_out_stream,
    errstream=default_bytes_err_stream,
    force=False,
    **kwargs
):
    """Remote push with dulwich via dulwich.client

    Args:
      repo: Path to repository
      remote_location: Location of the remote
      refspecs: Refs to push to remote
      outstream: A stream file to write output
      errstream: A stream file to write errors
      force: Force overwriting refs
    """

    # Open the repo
    with open_repo_closing(repo) as r:
        if refspecs is None:
            refspecs = [active_branch(r)]
        (remote_name, remote_location) = get_remote_repo(r, remote_location)

        # Get the client and path
        client, path = get_transport_and_path(
            remote_location, config=r.get_config_stack(), **kwargs
        )

        selected_refs = []
        remote_changed_refs = {}

        def update_refs(refs):
            selected_refs.extend(parse_reftuples(r.refs, refs, refspecs, force=force))
            new_refs = {}
            # TODO: Handle selected_refs == {None: None}
            for (lh, rh, force_ref) in selected_refs:
                if lh is None:
                    new_refs[rh] = ZERO_SHA
                    remote_changed_refs[rh] = None
                else:
                    try:
                        localsha = r.refs[lh]
                    except KeyError as exc:
                        raise Error(
                            "No valid ref %s in local repository" % lh
                        ) from exc
                    if not force_ref and rh in refs:
                        check_diverged(r, refs[rh], localsha)
                    new_refs[rh] = localsha
                    remote_changed_refs[rh] = localsha
            return new_refs

        err_encoding = getattr(errstream, "encoding", None) or DEFAULT_ENCODING
        remote_location = client.get_url(path)
        try:
            result = client.send_pack(
                path,
                update_refs,
                generate_pack_data=r.generate_pack_data,
                progress=errstream.write,
            )
        except SendPackError as exc:
            raise Error(
                "Push to " + remote_location + " failed -> " + exc.args[0].decode(),
            ) from exc
        else:
            errstream.write(
                b"Push to " + remote_location.encode(err_encoding) + b" successful.\n"
            )

        for ref, error in (result.ref_status or {}).items():
            if error is not None:
                errstream.write(
                    b"Push of ref %s failed: %s\n" % (ref, error.encode(err_encoding))
                )
            else:
                errstream.write(b"Ref %s updated\n" % ref)

        if remote_name is not None:
            _import_remote_refs(r.refs, remote_name, remote_changed_refs)


def pull(
    repo,
    remote_location=None,
    refspecs=None,
    outstream=default_bytes_out_stream,
    errstream=default_bytes_err_stream,
    fast_forward=True,
    force=False,
    **kwargs
):
    """Pull from remote via dulwich.client

    Args:
      repo: Path to repository
      remote_location: Location of the remote
      refspecs: refspecs to fetch
      outstream: A stream file to write to output
      errstream: A stream file to write to errors
    """
    # Open the repo
    with open_repo_closing(repo) as r:
        (remote_name, remote_location) = get_remote_repo(r, remote_location)

        if refspecs is None:
            refspecs = [b"HEAD"]
        selected_refs = []

        def determine_wants(remote_refs, **kwargs):
            selected_refs.extend(
                parse_reftuples(remote_refs, r.refs, refspecs, force=force)
            )
            return [
                remote_refs[lh]
                for (lh, rh, force_ref) in selected_refs
                if remote_refs[lh] not in r.object_store
            ]

        client, path = get_transport_and_path(
            remote_location, config=r.get_config_stack(), **kwargs
        )
        fetch_result = client.fetch(
            path, r, progress=errstream.write, determine_wants=determine_wants
        )
        for (lh, rh, force_ref) in selected_refs:
            if not force_ref and rh in r.refs:
                try:
                    check_diverged(r, r.refs.follow(rh)[1], fetch_result.refs[lh])
                except DivergedBranches as exc:
                    if fast_forward:
                        raise
                    else:
                        raise NotImplementedError(
                            "merge is not yet supported") from exc
            r.refs[rh] = fetch_result.refs[lh]
        if selected_refs:
            r[b"HEAD"] = fetch_result.refs[selected_refs[0][1]]

        # Perform 'git checkout .' - syncs staged changes
        tree = r[b"HEAD"].tree
        r.reset_index(tree=tree)
        if remote_name is not None:
            _import_remote_refs(r.refs, remote_name, fetch_result.refs)


def status(repo=".", ignored=False, untracked_files="all"):
    """Returns staged, unstaged, and untracked changes relative to the HEAD.

    Args:
      repo: Path to repository or repository object
      ignored: Whether to include ignored files in untracked
      untracked_files: How to handle untracked files, defaults to "all":
          "no": do not return untracked files
          "all": include all files in untracked directories
        Using untracked_files="no" can be faster than "all" when the worktreee
          contains many untracked files/directories.

    Note: untracked_files="normal" (git's default) is not implemented.

    Returns: GitStatus tuple,
        staged -  dict with lists of staged paths (diff index/HEAD)
        unstaged -  list of unstaged paths (diff index/working-tree)
        untracked - list of untracked, un-ignored & non-.git paths
    """
    with open_repo_closing(repo) as r:
        # 1. Get status of staged
        tracked_changes = get_tree_changes(r)
        # 2. Get status of unstaged
        index = r.open_index()
        normalizer = r.get_blob_normalizer()
        filter_callback = normalizer.checkin_normalize
        unstaged_changes = list(get_unstaged_changes(index, r.path, filter_callback))

        untracked_paths = get_untracked_paths(
            r.path,
            r.path,
            index,
            exclude_ignored=not ignored,
            untracked_files=untracked_files,
        )
        if sys.platform == "win32":
            untracked_changes = [
                path.replace(os.path.sep, "/") for path in untracked_paths
            ]
        else:
            untracked_changes = list(untracked_paths)

        return GitStatus(tracked_changes, unstaged_changes, untracked_changes)


def _walk_working_dir_paths(frompath, basepath, prune_dirnames=None):
    """Get path, is_dir for files in working dir from frompath

    Args:
      frompath: Path to begin walk
      basepath: Path to compare to
      prune_dirnames: Optional callback to prune dirnames during os.walk
        dirnames will be set to result of prune_dirnames(dirpath, dirnames)
    """
    for dirpath, dirnames, filenames in os.walk(frompath):
        # Skip .git and below.
        if ".git" in dirnames:
            dirnames.remove(".git")
            if dirpath != basepath:
                continue

        if ".git" in filenames:
            filenames.remove(".git")
            if dirpath != basepath:
                continue

        if dirpath != frompath:
            yield dirpath, True

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            yield filepath, False

        if prune_dirnames:
            dirnames[:] = prune_dirnames(dirpath, dirnames)


def get_untracked_paths(
    frompath, basepath, index, exclude_ignored=False, untracked_files="all"
):
    """Get untracked paths.

    Args:
      frompath: Path to walk
      basepath: Path to compare to
      index: Index to check against
      exclude_ignored: Whether to exclude ignored paths
      untracked_files: How to handle untracked files:
        - "no": return an empty list
        - "all": return all files in untracked directories
        - "normal": Not implemented

    Note: ignored directories will never be walked for performance reasons.
      If exclude_ignored is False, only the path to an ignored directory will
      be yielded, no files inside the directory will be returned
    """
    if untracked_files == "normal":
        raise NotImplementedError("normal is not yet supported")

    if untracked_files not in ("no", "all"):
        raise ValueError("untracked_files must be one of (no, all)")

    if untracked_files == "no":
        return

    with open_repo_closing(basepath) as r:
        ignore_manager = IgnoreFilterManager.from_repo(r)

    ignored_dirs = []

    def prune_dirnames(dirpath, dirnames):
        for i in range(len(dirnames) - 1, -1, -1):
            path = os.path.join(dirpath, dirnames[i])
            ip = os.path.join(os.path.relpath(path, basepath), "")
            if ignore_manager.is_ignored(ip):
                if not exclude_ignored:
                    ignored_dirs.append(
                        os.path.join(os.path.relpath(path, frompath), "")
                    )
                del dirnames[i]
        return dirnames

    for ap, is_dir in _walk_working_dir_paths(
        frompath, basepath, prune_dirnames=prune_dirnames
    ):
        if not is_dir:
            ip = path_to_tree_path(basepath, ap)
            if ip not in index:
                if not exclude_ignored or not ignore_manager.is_ignored(
                    os.path.relpath(ap, basepath)
                ):
                    yield os.path.relpath(ap, frompath)

    yield from ignored_dirs


def get_tree_changes(repo):
    """Return add/delete/modify changes to tree by comparing index to HEAD.

    Args:
      repo: repo path or object
    Returns: dict with lists for each type of change
    """
    with open_repo_closing(repo) as r:
        index = r.open_index()

        # Compares the Index to the HEAD & determines changes
        # Iterate through the changes and report add/delete/modify
        # TODO: call out to dulwich.diff_tree somehow.
        tracked_changes = {
            "add": [],
            "delete": [],
            "modify": [],
        }
        try:
            tree_id = r[b"HEAD"].tree
        except KeyError:
            tree_id = None

        for change in index.changes_from_tree(r.object_store, tree_id):
            if not change[0][0]:
                tracked_changes["add"].append(change[0][1])
            elif not change[0][1]:
                tracked_changes["delete"].append(change[0][0])
            elif change[0][0] == change[0][1]:
                tracked_changes["modify"].append(change[0][0])
            else:
                raise NotImplementedError("git mv ops not yet supported")
        return tracked_changes


def daemon(path=".", address=None, port=None):
    """Run a daemon serving Git requests over TCP/IP.

    Args:
      path: Path to the directory to serve.
      address: Optional address to listen on (defaults to ::)
      port: Optional port to listen on (defaults to TCP_GIT_PORT)
    """
    # TODO(jelmer): Support git-daemon-export-ok and --export-all.
    backend = FileSystemBackend(path)
    server = TCPGitServer(backend, address, port)
    server.serve_forever()


def web_daemon(path=".", address=None, port=None):
    """Run a daemon serving Git requests over HTTP.

    Args:
      path: Path to the directory to serve
      address: Optional address to listen on (defaults to ::)
      port: Optional port to listen on (defaults to 80)
    """
    from .web import (WSGIRequestHandlerLogger, WSGIServerLogger, make_server,
                      make_wsgi_chain)

    backend = FileSystemBackend(path)
    app = make_wsgi_chain(backend)
    server = make_server(
        address,
        port,
        app,
        handler_class=WSGIRequestHandlerLogger,
        server_class=WSGIServerLogger,
    )
    server.serve_forever()


def upload_pack(path=".", inf=None, outf=None):
    """Upload a pack file after negotiating its contents using smart protocol.

    Args:
      path: Path to the repository
      inf: Input stream to communicate with client
      outf: Output stream to communicate with client
    """
    if outf is None:
        outf = getattr(sys.stdout, "buffer", sys.stdout)
    if inf is None:
        inf = getattr(sys.stdin, "buffer", sys.stdin)
    path = os.path.expanduser(path)
    backend = FileSystemBackend(path)

    def send_fn(data):
        outf.write(data)
        outf.flush()

    proto = Protocol(inf.read, send_fn)
    handler = UploadPackHandler(backend, [path], proto)
    # FIXME: Catch exceptions and write a single-line summary to outf.
    handler.handle()
    return 0


def receive_pack(path=".", inf=None, outf=None):
    """Receive a pack file after negotiating its contents using smart protocol.

    Args:
      path: Path to the repository
      inf: Input stream to communicate with client
      outf: Output stream to communicate with client
    """
    if outf is None:
        outf = getattr(sys.stdout, "buffer", sys.stdout)
    if inf is None:
        inf = getattr(sys.stdin, "buffer", sys.stdin)
    path = os.path.expanduser(path)
    backend = FileSystemBackend(path)

    def send_fn(data):
        outf.write(data)
        outf.flush()

    proto = Protocol(inf.read, send_fn)
    handler = ReceivePackHandler(backend, [path], proto)
    # FIXME: Catch exceptions and write a single-line summary to outf.
    handler.handle()
    return 0


def _make_branch_ref(name):
    if getattr(name, "encode", None):
        name = name.encode(DEFAULT_ENCODING)
    return LOCAL_BRANCH_PREFIX + name


def _make_tag_ref(name):
    if getattr(name, "encode", None):
        name = name.encode(DEFAULT_ENCODING)
    return LOCAL_TAG_PREFIX + name


def branch_delete(repo, name):
    """Delete a branch.

    Args:
      repo: Path to the repository
      name: Name of the branch
    """
    with open_repo_closing(repo) as r:
        if isinstance(name, list):
            names = name
        else:
            names = [name]
        for name in names:
            del r.refs[_make_branch_ref(name)]


def branch_create(repo, name, objectish=None, force=False):
    """Create a branch.

    Args:
      repo: Path to the repository
      name: Name of the new branch
      objectish: Target object to point new branch at (defaults to HEAD)
      force: Force creation of branch, even if it already exists
    """
    with open_repo_closing(repo) as r:
        if objectish is None:
            objectish = "HEAD"
        object = parse_object(r, objectish)
        refname = _make_branch_ref(name)
        ref_message = b"branch: Created from " + objectish.encode(DEFAULT_ENCODING)
        if force:
            r.refs.set_if_equals(refname, None, object.id, message=ref_message)
        else:
            if not r.refs.add_if_new(refname, object.id, message=ref_message):
                raise Error("Branch with name %s already exists." % name)


def branch_list(repo):
    """List all branches.

    Args:
      repo: Path to the repository
    """
    with open_repo_closing(repo) as r:
        return r.refs.keys(base=LOCAL_BRANCH_PREFIX)


def active_branch(repo):
    """Return the active branch in the repository, if any.

    Args:
      repo: Repository to open
    Returns:
      branch name
    Raises:
      KeyError: if the repository does not have a working tree
      IndexError: if HEAD is floating
    """
    with open_repo_closing(repo) as r:
        active_ref = r.refs.follow(b"HEAD")[0][1]
        if not active_ref.startswith(LOCAL_BRANCH_PREFIX):
            raise ValueError(active_ref)
        return active_ref[len(LOCAL_BRANCH_PREFIX) :]


def get_branch_remote(repo):
    """Return the active branch's remote name, if any.

    Args:
      repo: Repository to open
    Returns:
      remote name
    Raises:
      KeyError: if the repository does not have a working tree
    """
    with open_repo_closing(repo) as r:
        branch_name = active_branch(r.path)
        config = r.get_config()
        try:
            remote_name = config.get((b"branch", branch_name), b"remote")
        except KeyError:
            remote_name = b"origin"
    return remote_name


def fetch(
    repo,
    remote_location=None,
    outstream=sys.stdout,
    errstream=default_bytes_err_stream,
    message=None,
    depth=None,
    prune=False,
    prune_tags=False,
    force=False,
    **kwargs
):
    """Fetch objects from a remote server.

    Args:
      repo: Path to the repository
      remote_location: String identifying a remote server
      outstream: Output stream (defaults to stdout)
      errstream: Error stream (defaults to stderr)
      message: Reflog message (defaults to b"fetch: from <remote_name>")
      depth: Depth to fetch at
      prune: Prune remote removed refs
      prune_tags: Prune reomte removed tags
    Returns:
      Dictionary with refs on the remote
    """
    with open_repo_closing(repo) as r:
        (remote_name, remote_location) = get_remote_repo(r, remote_location)
        if message is None:
            message = b"fetch: from " + remote_location.encode(DEFAULT_ENCODING)
        client, path = get_transport_and_path(
            remote_location, config=r.get_config_stack(), **kwargs
        )
        fetch_result = client.fetch(path, r, progress=errstream.write, depth=depth)
        if remote_name is not None:
            _import_remote_refs(
                r.refs,
                remote_name,
                fetch_result.refs,
                message,
                prune=prune,
                prune_tags=prune_tags,
            )
    return fetch_result


def ls_remote(remote, config: Optional[Config] = None, **kwargs):
    """List the refs in a remote.

    Args:
      remote: Remote repository location
      config: Configuration to use
    Returns:
      Dictionary with remote refs
    """
    if config is None:
        config = StackedConfig.default()
    client, host_path = get_transport_and_path(remote, config=config, **kwargs)
    return client.get_refs(host_path)


def repack(repo):
    """Repack loose files in a repository.

    Currently this only packs loose objects.

    Args:
      repo: Path to the repository
    """
    with open_repo_closing(repo) as r:
        r.object_store.pack_loose_objects()


def pack_objects(repo, object_ids, packf, idxf, delta_window_size=None, deltify=None, reuse_deltas=True):
    """Pack objects into a file.

    Args:
      repo: Path to the repository
      object_ids: List of object ids to write
      packf: File-like object to write to
      idxf: File-like object to write to (can be None)
      delta_window_size: Sliding window size for searching for deltas;
                         Set to None for default window size.
      deltify: Whether to deltify objects
      reuse_deltas: Allow reuse of existing deltas while deltifying
    """
    with open_repo_closing(repo) as r:
        entries, data_sum = write_pack_from_container(
            packf.write,
            r.object_store,
            [(oid, None) for oid in object_ids],
            deltify=deltify,
            delta_window_size=delta_window_size,
            reuse_deltas=reuse_deltas,
        )
    if idxf is not None:
        entries = sorted([(k, v[0], v[1]) for (k, v) in entries.items()])
        write_pack_index(idxf, entries, data_sum)


def ls_tree(
    repo,
    treeish=b"HEAD",
    outstream=sys.stdout,
    recursive=False,
    name_only=False,
):
    """List contents of a tree.

    Args:
      repo: Path to the repository
      treeish: Tree id to list
      outstream: Output stream (defaults to stdout)
      recursive: Whether to recursively list files
      name_only: Only print item name
    """

    def list_tree(store, treeid, base):
        for (name, mode, sha) in store[treeid].iteritems():
            if base:
                name = posixpath.join(base, name)
            if name_only:
                outstream.write(name + b"\n")
            else:
                outstream.write(pretty_format_tree_entry(name, mode, sha))
            if stat.S_ISDIR(mode) and recursive:
                list_tree(store, sha, name)

    with open_repo_closing(repo) as r:
        tree = parse_tree(r, treeish)
        list_tree(r.object_store, tree.id, "")


def remote_add(repo: Repo, name: Union[bytes, str], url: Union[bytes, str]):
    """Add a remote.

    Args:
      repo: Path to the repository
      name: Remote name
      url: Remote URL
    """
    if not isinstance(name, bytes):
        name = name.encode(DEFAULT_ENCODING)
    if not isinstance(url, bytes):
        url = url.encode(DEFAULT_ENCODING)
    with open_repo_closing(repo) as r:
        c = r.get_config()
        section = (b"remote", name)
        if c.has_section(section):
            raise RemoteExists(section)
        c.set(section, b"url", url)
        c.write_to_path()


def remote_remove(repo: Repo, name: Union[bytes, str]):
    """Remove a remote

    Args:
      repo: Path to the repository
      name: Remote name
    """
    if not isinstance(name, bytes):
        name = name.encode(DEFAULT_ENCODING)
    with open_repo_closing(repo) as r:
        c = r.get_config()
        section = (b"remote", name)
        del c[section]
        c.write_to_path()


def check_ignore(repo, paths, no_index=False):
    """Debug gitignore files.

    Args:
      repo: Path to the repository
      paths: List of paths to check for
      no_index: Don't check index
    Returns: List of ignored files
    """
    with open_repo_closing(repo) as r:
        index = r.open_index()
        ignore_manager = IgnoreFilterManager.from_repo(r)
        for path in paths:
            if not no_index and path_to_tree_path(r.path, path) in index:
                continue
            if os.path.isabs(path):
                path = os.path.relpath(path, r.path)
            if ignore_manager.is_ignored(path):
                yield path


def update_head(repo, target, detached=False, new_branch=None):
    """Update HEAD to point at a new branch/commit.

    Note that this does not actually update the working tree.

    Args:
      repo: Path to the repository
      detached: Create a detached head
      target: Branch or committish to switch to
      new_branch: New branch to create
    """
    with open_repo_closing(repo) as r:
        if new_branch is not None:
            to_set = _make_branch_ref(new_branch)
        else:
            to_set = b"HEAD"
        if detached:
            # TODO(jelmer): Provide some way so that the actual ref gets
            # updated rather than what it points to, so the delete isn't
            # necessary.
            del r.refs[to_set]
            r.refs[to_set] = parse_commit(r, target).id
        else:
            r.refs.set_symbolic_ref(to_set, parse_ref(r, target))
        if new_branch is not None:
            r.refs.set_symbolic_ref(b"HEAD", to_set)


def reset_file(repo, file_path: str, target: bytes = b'HEAD',
               symlink_fn=None):
    """Reset the file to specific commit or branch.

    Args:
      repo: dulwich Repo object
      file_path: file to reset, relative to the repository path
      target: branch or commit or b'HEAD' to reset
    """
    tree = parse_tree(repo, treeish=target)
    tree_path = _fs_to_tree_path(file_path)

    file_entry = tree.lookup_path(repo.object_store.__getitem__, tree_path)
    full_path = os.path.join(os.fsencode(repo.path), tree_path)
    blob = repo.object_store[file_entry[1]]
    mode = file_entry[0]
    build_file_from_blob(blob, mode, full_path, symlink_fn=symlink_fn)


def _update_head_during_checkout_branch(repo, target):
    checkout_target = None
    if target == b'HEAD':  # Do not update head while trying to checkout to HEAD.
        pass
    elif target in repo.refs.keys(base=LOCAL_BRANCH_PREFIX):
        update_head(repo, target)
    else:
        # If checking out a remote branch, create a local one without the remote name prefix.
        config = repo.get_config()
        name = target.split(b"/")[0]
        section = (b"remote", name)
        if config.has_section(section):
            checkout_target = target.replace(name + b"/", b"")
            try:
                branch_create(repo, checkout_target, (LOCAL_REMOTE_PREFIX + target).decode())
            except Error:
                pass
            update_head(repo, LOCAL_BRANCH_PREFIX + checkout_target)
        else:
            update_head(repo, target, detached=True)

    return checkout_target


def checkout_branch(repo, target: Union[bytes, str], force: bool = False):
    """switch branches or restore working tree files.

    The implementation of this function will probably not scale well
    for branches with lots of local changes.
    This is due to the analysis of a diff between branches before any
    changes are applied.

    Args:
      repo: dulwich Repo object
      target: branch name or commit sha to checkout
      force: true or not to force checkout
    """
    target = to_bytes(target)

    current_tree = parse_tree(repo, repo.head())
    target_tree = parse_tree(repo, target)

    if force:
        repo.reset_index(target_tree.id)
        _update_head_during_checkout_branch(repo, target)
    else:
        status_report = status(repo)
        changes = list(set(status_report[0]['add'] + status_report[0]['delete'] + status_report[0]['modify'] + status_report[1]))
        index = 0
        while index < len(changes):
            change = changes[index]
            try:
                current_tree.lookup_path(repo.object_store.__getitem__, change)
                try:
                    target_tree.lookup_path(repo.object_store.__getitem__, change)
                    index += 1
                except KeyError:
                    raise CheckoutError('Your local changes to the following files would be overwritten by checkout: ' + change.decode())
            except KeyError:
                changes.pop(index)

        # Update head.
        checkout_target = _update_head_during_checkout_branch(repo, target)
        if checkout_target is not None:
            target_tree = parse_tree(repo, checkout_target)

        dealt_with = set()
        repo_index = repo.open_index()
        for entry in iter_tree_contents(repo.object_store, target_tree.id):
            dealt_with.add(entry.path)
            if entry.path in changes:
                continue
            full_path = os.path.join(os.fsencode(repo.path), entry.path)
            blob = repo.object_store[entry.sha]
            ensure_dir_exists(os.path.dirname(full_path))
            st = build_file_from_blob(blob, entry.mode, full_path)
            repo_index[entry.path] = index_entry_from_stat(st, entry.sha, 0)

        repo_index.write()

        for entry in iter_tree_contents(repo.object_store, current_tree.id):
            if entry.path not in dealt_with:
                repo.unstage([entry.path])

    # Remove the untracked files which are in the current_file_set.
    repo_index = repo.open_index()
    for change in repo_index.changes_from_tree(repo.object_store, current_tree.id):
        path_change = change[0]
        if path_change[1] is None:
            file_name = path_change[0]
            full_path = os.path.join(repo.path, file_name.decode())
            if os.path.isfile(full_path):
                os.remove(full_path)
            dir_path = os.path.dirname(full_path)
            while dir_path != repo.path:
                is_empty = len(os.listdir(dir_path)) == 0
                if is_empty:
                    os.rmdir(dir_path)
                dir_path = os.path.dirname(dir_path)


def check_mailmap(repo, contact):
    """Check canonical name and email of contact.

    Args:
      repo: Path to the repository
      contact: Contact name and/or email
    Returns: Canonical contact data
    """
    with open_repo_closing(repo) as r:
        from .mailmap import Mailmap

        try:
            mailmap = Mailmap.from_path(os.path.join(r.path, ".mailmap"))
        except FileNotFoundError:
            mailmap = Mailmap()
        return mailmap.lookup(contact)


def fsck(repo):
    """Check a repository.

    Args:
      repo: A path to the repository
    Returns: Iterator over errors/warnings
    """
    with open_repo_closing(repo) as r:
        # TODO(jelmer): check pack files
        # TODO(jelmer): check graph
        # TODO(jelmer): check refs
        for sha in r.object_store:
            o = r.object_store[sha]
            try:
                o.check()
            except Exception as e:
                yield (sha, e)


def stash_list(repo):
    """List all stashes in a repository."""
    with open_repo_closing(repo) as r:
        from .stash import Stash

        stash = Stash.from_repo(r)
        return enumerate(list(stash.stashes()))


def stash_push(repo):
    """Push a new stash onto the stack."""
    with open_repo_closing(repo) as r:
        from .stash import Stash

        stash = Stash.from_repo(r)
        stash.push()


def stash_pop(repo, index):
    """Pop a stash from the stack."""
    with open_repo_closing(repo) as r:
        from .stash import Stash

        stash = Stash.from_repo(r)
        stash.pop(index)


def stash_drop(repo, index):
    """Drop a stash from the stack."""
    with open_repo_closing(repo) as r:
        from .stash import Stash

        stash = Stash.from_repo(r)
        stash.drop(index)


def ls_files(repo):
    """List all files in an index."""
    with open_repo_closing(repo) as r:
        return sorted(r.open_index())


def find_unique_abbrev(object_store, object_id):
    """For now, just return 7 characters."""
    # TODO(jelmer): Add some logic here to return a number of characters that
    # scales relative with the size of the repository
    return object_id.decode("ascii")[:7]


def describe(repo, abbrev=7):
    """Describe the repository version.

    Args:
      repo: git repository
      abbrev: number of characters of commit to take, default is 7
    Returns: a string description of the current git revision

    Examples: "gabcdefh", "v0.1" or "v0.1-5-gabcdefh".
    """
    # Get the repository
    with open_repo_closing(repo) as r:
        # Get a list of all tags
        refs = r.get_refs()
        tags = {}
        for key, value in refs.items():
            key = key.decode()
            obj = r.get_object(value)
            if "tags" not in key:
                continue

            _, tag = key.rsplit("/", 1)

            try:
                commit = obj.object
            except AttributeError:
                continue
            else:
                commit = r.get_object(commit[1])
            tags[tag] = [
                datetime.datetime(*time.gmtime(commit.commit_time)[:6]),
                commit.id.decode("ascii"),
            ]

        sorted_tags = sorted(tags.items(), key=lambda tag: tag[1][0], reverse=True)

        # If there are no tags, return the current commit
        if len(sorted_tags) == 0:
            return f"g{find_unique_abbrev(r.object_store, r[r.head()].id)}"

        # We're now 0 commits from the top
        commit_count = 0

        # Get the latest commit
        latest_commit = r[r.head()]

        # Walk through all commits
        walker = r.get_walker()
        for entry in walker:
            # Check if tag
            commit_id = entry.commit.id.decode("ascii")
            for tag in sorted_tags:
                tag_name = tag[0]
                tag_commit = tag[1][1]
                if commit_id == tag_commit:
                    if commit_count == 0:
                        return tag_name
                    else:
                        return "{}-{}-g{}".format(
                            tag_name,
                            commit_count,
                            latest_commit.id.decode("ascii")[:abbrev],
                        )

            commit_count += 1

        # Return plain commit if no parent tag can be found
        return "g{}".format(latest_commit.id.decode("ascii")[:abbrev])


def get_object_by_path(repo, path, committish=None):
    """Get an object by path.

    Args:
      repo: A path to the repository
      path: Path to look up
      committish: Commit to look up path in
    Returns: A `ShaFile` object
    """
    if committish is None:
        committish = "HEAD"
    # Get the repository
    with open_repo_closing(repo) as r:
        commit = parse_commit(r, committish)
        base_tree = commit.tree
        if not isinstance(path, bytes):
            path = commit_encode(commit, path)
        (mode, sha) = tree_lookup_path(r.object_store.__getitem__, base_tree, path)
        return r[sha]


def write_tree(repo):
    """Write a tree object from the index.

    Args:
      repo: Repository for which to write tree
    Returns: tree id for the tree that was written
    """
    with open_repo_closing(repo) as r:
        return r.open_index().commit(r.object_store)
