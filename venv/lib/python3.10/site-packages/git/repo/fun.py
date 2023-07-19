"""Package with general repository related functions"""
from __future__ import annotations
import os
import stat
from pathlib import Path
from string import digits

from git.exc import WorkTreeRepositoryUnsupported
from git.objects import Object
from git.refs import SymbolicReference
from git.util import hex_to_bin, bin_to_hex, cygpath
from gitdb.exc import (
    BadObject,
    BadName,
)

import os.path as osp
from git.cmd import Git

# Typing ----------------------------------------------------------------------

from typing import Union, Optional, cast, TYPE_CHECKING
from git.types import Commit_ish

if TYPE_CHECKING:
    from git.types import PathLike
    from .base import Repo
    from git.db import GitCmdObjectDB
    from git.refs.reference import Reference
    from git.objects import Commit, TagObject, Blob, Tree
    from git.refs.tag import Tag

# ----------------------------------------------------------------------------

__all__ = (
    "rev_parse",
    "is_git_dir",
    "touch",
    "find_submodule_git_dir",
    "name_to_object",
    "short_to_long",
    "deref_tag",
    "to_commit",
    "find_worktree_git_dir",
)


def touch(filename: str) -> str:
    with open(filename, "ab"):
        pass
    return filename


def is_git_dir(d: "PathLike") -> bool:
    """This is taken from the git setup.c:is_git_directory
    function.

    @throws WorkTreeRepositoryUnsupported if it sees a worktree directory. It's quite hacky to do that here,
            but at least clearly indicates that we don't support it.
            There is the unlikely danger to throw if we see directories which just look like a worktree dir,
            but are none."""
    if osp.isdir(d):
        if (osp.isdir(osp.join(d, "objects")) or "GIT_OBJECT_DIRECTORY" in os.environ) and osp.isdir(
            osp.join(d, "refs")
        ):
            headref = osp.join(d, "HEAD")
            return osp.isfile(headref) or (osp.islink(headref) and os.readlink(headref).startswith("refs"))
        elif (
            osp.isfile(osp.join(d, "gitdir"))
            and osp.isfile(osp.join(d, "commondir"))
            and osp.isfile(osp.join(d, "gitfile"))
        ):
            raise WorkTreeRepositoryUnsupported(d)
    return False


def find_worktree_git_dir(dotgit: "PathLike") -> Optional[str]:
    """Search for a gitdir for this worktree."""
    try:
        statbuf = os.stat(dotgit)
    except OSError:
        return None
    if not stat.S_ISREG(statbuf.st_mode):
        return None

    try:
        lines = Path(dotgit).read_text().splitlines()
        for key, value in [line.strip().split(": ") for line in lines]:
            if key == "gitdir":
                return value
    except ValueError:
        pass
    return None


def find_submodule_git_dir(d: "PathLike") -> Optional["PathLike"]:
    """Search for a submodule repo."""
    if is_git_dir(d):
        return d

    try:
        with open(d) as fp:
            content = fp.read().rstrip()
    except IOError:
        # it's probably not a file
        pass
    else:
        if content.startswith("gitdir: "):
            path = content[8:]

            if Git.is_cygwin():
                ## Cygwin creates submodules prefixed with `/cygdrive/...` suffixes.
                # Cygwin git understands Cygwin paths much better than Windows ones
                # Also the Cygwin tests are assuming Cygwin paths.
                path = cygpath(path)
            if not osp.isabs(path):
                path = osp.normpath(osp.join(osp.dirname(d), path))
            return find_submodule_git_dir(path)
    # end handle exception
    return None


def short_to_long(odb: "GitCmdObjectDB", hexsha: str) -> Optional[bytes]:
    """:return: long hexadecimal sha1 from the given less-than-40 byte hexsha
        or None if no candidate could be found.
    :param hexsha: hexsha with less than 40 byte"""
    try:
        return bin_to_hex(odb.partial_to_complete_sha_hex(hexsha))
    except BadObject:
        return None
    # END exception handling


def name_to_object(
    repo: "Repo", name: str, return_ref: bool = False
) -> Union[SymbolicReference, "Commit", "TagObject", "Blob", "Tree"]:
    """
    :return: object specified by the given name, hexshas ( short and long )
        as well as references are supported
    :param return_ref: if name specifies a reference, we will return the reference
        instead of the object. Otherwise it will raise BadObject or BadName
    """
    hexsha: Union[None, str, bytes] = None

    # is it a hexsha ? Try the most common ones, which is 7 to 40
    if repo.re_hexsha_shortened.match(name):
        if len(name) != 40:
            # find long sha for short sha
            hexsha = short_to_long(repo.odb, name)
        else:
            hexsha = name
        # END handle short shas
    # END find sha if it matches

    # if we couldn't find an object for what seemed to be a short hexsha
    # try to find it as reference anyway, it could be named 'aaa' for instance
    if hexsha is None:
        for base in (
            "%s",
            "refs/%s",
            "refs/tags/%s",
            "refs/heads/%s",
            "refs/remotes/%s",
            "refs/remotes/%s/HEAD",
        ):
            try:
                hexsha = SymbolicReference.dereference_recursive(repo, base % name)
                if return_ref:
                    return SymbolicReference(repo, base % name)
                # END handle symbolic ref
                break
            except ValueError:
                pass
        # END for each base
    # END handle hexsha

    # didn't find any ref, this is an error
    if return_ref:
        raise BadObject("Couldn't find reference named %r" % name)
    # END handle return ref

    # tried everything ? fail
    if hexsha is None:
        raise BadName(name)
    # END assert hexsha was found

    return Object.new_from_sha(repo, hex_to_bin(hexsha))


def deref_tag(tag: "Tag") -> "TagObject":
    """Recursively dereference a tag and return the resulting object"""
    while True:
        try:
            tag = tag.object
        except AttributeError:
            break
    # END dereference tag
    return tag


def to_commit(obj: Object) -> Union["Commit", "TagObject"]:
    """Convert the given object to a commit if possible and return it"""
    if obj.type == "tag":
        obj = deref_tag(obj)

    if obj.type != "commit":
        raise ValueError("Cannot convert object %r to type commit" % obj)
    # END verify type
    return obj


def rev_parse(repo: "Repo", rev: str) -> Union["Commit", "Tag", "Tree", "Blob"]:
    """
    :return: Object at the given revision, either Commit, Tag, Tree or Blob
    :param rev: git-rev-parse compatible revision specification as string, please see
        http://www.kernel.org/pub/software/scm/git/docs/git-rev-parse.html
        for details
    :raise BadObject: if the given revision could not be found
    :raise ValueError: If rev couldn't be parsed
    :raise IndexError: If invalid reflog index is specified"""

    # colon search mode ?
    if rev.startswith(":/"):
        # colon search mode
        raise NotImplementedError("commit by message search ( regex )")
    # END handle search

    obj: Union[Commit_ish, "Reference", None] = None
    ref = None
    output_type = "commit"
    start = 0
    parsed_to = 0
    lr = len(rev)
    while start < lr:
        if rev[start] not in "^~:@":
            start += 1
            continue
        # END handle start

        token = rev[start]

        if obj is None:
            # token is a rev name
            if start == 0:
                ref = repo.head.ref
            else:
                if token == "@":
                    ref = cast("Reference", name_to_object(repo, rev[:start], return_ref=True))
                else:
                    obj = cast(Commit_ish, name_to_object(repo, rev[:start]))
                # END handle token
            # END handle refname
        else:
            assert obj is not None

            if ref is not None:
                obj = cast("Commit", ref.commit)
            # END handle ref
        # END initialize obj on first token

        start += 1

        # try to parse {type}
        if start < lr and rev[start] == "{":
            end = rev.find("}", start)
            if end == -1:
                raise ValueError("Missing closing brace to define type in %s" % rev)
            output_type = rev[start + 1 : end]  # exclude brace

            # handle type
            if output_type == "commit":
                pass  # default
            elif output_type == "tree":
                try:
                    obj = cast(Commit_ish, obj)
                    obj = to_commit(obj).tree
                except (AttributeError, ValueError):
                    pass  # error raised later
                # END exception handling
            elif output_type in ("", "blob"):
                obj = cast("TagObject", obj)
                if obj and obj.type == "tag":
                    obj = deref_tag(obj)
                else:
                    # cannot do anything for non-tags
                    pass
                # END handle tag
            elif token == "@":
                # try single int
                assert ref is not None, "Require Reference to access reflog"
                revlog_index = None
                try:
                    # transform reversed index into the format of our revlog
                    revlog_index = -(int(output_type) + 1)
                except ValueError as e:
                    # TODO: Try to parse the other date options, using parse_date
                    # maybe
                    raise NotImplementedError("Support for additional @{...} modes not implemented") from e
                # END handle revlog index

                try:
                    entry = ref.log_entry(revlog_index)
                except IndexError as e:
                    raise IndexError("Invalid revlog index: %i" % revlog_index) from e
                # END handle index out of bound

                obj = Object.new_from_sha(repo, hex_to_bin(entry.newhexsha))

                # make it pass the following checks
                output_type = ""
            else:
                raise ValueError("Invalid output type: %s ( in %s )" % (output_type, rev))
            # END handle output type

            # empty output types don't require any specific type, its just about dereferencing tags
            if output_type and obj and obj.type != output_type:
                raise ValueError("Could not accommodate requested object type %r, got %s" % (output_type, obj.type))
            # END verify output type

            start = end + 1  # skip brace
            parsed_to = start
            continue
        # END parse type

        # try to parse a number
        num = 0
        if token != ":":
            found_digit = False
            while start < lr:
                if rev[start] in digits:
                    num = num * 10 + int(rev[start])
                    start += 1
                    found_digit = True
                else:
                    break
                # END handle number
            # END number parse loop

            # no explicit number given, 1 is the default
            # It could be 0 though
            if not found_digit:
                num = 1
            # END set default num
        # END number parsing only if non-blob mode

        parsed_to = start
        # handle hierarchy walk
        try:
            obj = cast(Commit_ish, obj)
            if token == "~":
                obj = to_commit(obj)
                for _ in range(num):
                    obj = obj.parents[0]
                # END for each history item to walk
            elif token == "^":
                obj = to_commit(obj)
                # must be n'th parent
                if num:
                    obj = obj.parents[num - 1]
            elif token == ":":
                if obj.type != "tree":
                    obj = obj.tree
                # END get tree type
                obj = obj[rev[start:]]
                parsed_to = lr
            else:
                raise ValueError("Invalid token: %r" % token)
            # END end handle tag
        except (IndexError, AttributeError) as e:
            raise BadName(
                f"Invalid revision spec '{rev}' - not enough " f"parent commits to reach '{token}{int(num)}'"
            ) from e
        # END exception handling
    # END parse loop

    # still no obj ? Its probably a simple name
    if obj is None:
        obj = cast(Commit_ish, name_to_object(repo, rev))
        parsed_to = lr
    # END handle simple name

    if obj is None:
        raise ValueError("Revision specifier could not be parsed: %s" % rev)

    if parsed_to != lr:
        raise ValueError("Didn't consume complete rev spec %s, consumed part: %s" % (rev, rev[:parsed_to]))

    return obj
