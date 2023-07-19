# Contains standalone functions to accompany the index implementation and make it
# more versatile
# NOTE: Autodoc hates it if this is a docstring

from io import BytesIO
from pathlib import Path
import os
from stat import (
    S_IFDIR,
    S_IFLNK,
    S_ISLNK,
    S_ISDIR,
    S_IFMT,
    S_IFREG,
    S_IXUSR,
)
import subprocess

from git.cmd import PROC_CREATIONFLAGS, handle_process_output
from git.compat import (
    defenc,
    force_text,
    force_bytes,
    is_posix,
    is_win,
    safe_decode,
)
from git.exc import UnmergedEntriesError, HookExecutionError
from git.objects.fun import (
    tree_to_stream,
    traverse_tree_recursive,
    traverse_trees_recursive,
)
from git.util import IndexFileSHA1Writer, finalize_process
from gitdb.base import IStream
from gitdb.typ import str_tree_type

import os.path as osp

from .typ import BaseIndexEntry, IndexEntry, CE_NAMEMASK, CE_STAGESHIFT
from .util import pack, unpack

# typing -----------------------------------------------------------------------------

from typing import Dict, IO, List, Sequence, TYPE_CHECKING, Tuple, Type, Union, cast

from git.types import PathLike

if TYPE_CHECKING:
    from .base import IndexFile
    from git.db import GitCmdObjectDB
    from git.objects.tree import TreeCacheTup

    # from git.objects.fun import EntryTupOrNone

# ------------------------------------------------------------------------------------


S_IFGITLINK = S_IFLNK | S_IFDIR  # a submodule
CE_NAMEMASK_INV = ~CE_NAMEMASK

__all__ = (
    "write_cache",
    "read_cache",
    "write_tree_from_cache",
    "entry_key",
    "stat_mode_to_index_mode",
    "S_IFGITLINK",
    "run_commit_hook",
    "hook_path",
)


def hook_path(name: str, git_dir: PathLike) -> str:
    """:return: path to the given named hook in the given git repository directory"""
    return osp.join(git_dir, "hooks", name)


def _has_file_extension(path):
    return osp.splitext(path)[1]


def run_commit_hook(name: str, index: "IndexFile", *args: str) -> None:
    """Run the commit hook of the given name. Silently ignores hooks that do not exist.

    :param name: name of hook, like 'pre-commit'
    :param index: IndexFile instance
    :param args: arguments passed to hook file
    :raises HookExecutionError:"""
    hp = hook_path(name, index.repo.git_dir)
    if not os.access(hp, os.X_OK):
        return None

    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = safe_decode(str(index.path))
    env["GIT_EDITOR"] = ":"
    cmd = [hp]
    try:
        if is_win and not _has_file_extension(hp):
            # Windows only uses extensions to determine how to open files
            # (doesn't understand shebangs). Try using bash to run the hook.
            relative_hp = Path(hp).relative_to(index.repo.working_dir).as_posix()
            cmd = ["bash.exe", relative_hp]

        cmd = subprocess.Popen(
            cmd + list(args),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=index.repo.working_dir,
            close_fds=is_posix,
            creationflags=PROC_CREATIONFLAGS,
        )
    except Exception as ex:
        raise HookExecutionError(hp, ex) from ex
    else:
        stdout_list: List[str] = []
        stderr_list: List[str] = []
        handle_process_output(cmd, stdout_list.append, stderr_list.append, finalize_process)
        stdout = "".join(stdout_list)
        stderr = "".join(stderr_list)
        if cmd.returncode != 0:
            stdout = force_text(stdout, defenc)
            stderr = force_text(stderr, defenc)
            raise HookExecutionError(hp, cmd.returncode, stderr, stdout)
    # end handle return code


def stat_mode_to_index_mode(mode: int) -> int:
    """Convert the given mode from a stat call to the corresponding index mode
    and return it"""
    if S_ISLNK(mode):  # symlinks
        return S_IFLNK
    if S_ISDIR(mode) or S_IFMT(mode) == S_IFGITLINK:  # submodules
        return S_IFGITLINK
    return S_IFREG | (mode & S_IXUSR and 0o755 or 0o644)  # blobs with or without executable bit


def write_cache(
    entries: Sequence[Union[BaseIndexEntry, "IndexEntry"]],
    stream: IO[bytes],
    extension_data: Union[None, bytes] = None,
    ShaStreamCls: Type[IndexFileSHA1Writer] = IndexFileSHA1Writer,
) -> None:
    """Write the cache represented by entries to a stream

    :param entries: **sorted** list of entries
    :param stream: stream to wrap into the AdapterStreamCls - it is used for
        final output.

    :param ShaStreamCls: Type to use when writing to the stream. It produces a sha
        while writing to it, before the data is passed on to the wrapped stream

    :param extension_data: any kind of data to write as a trailer, it must begin
        a 4 byte identifier, followed by its size ( 4 bytes )"""
    # wrap the stream into a compatible writer
    stream_sha = ShaStreamCls(stream)

    tell = stream_sha.tell
    write = stream_sha.write

    # header
    version = 2
    write(b"DIRC")
    write(pack(">LL", version, len(entries)))

    # body
    for entry in entries:
        beginoffset = tell()
        write(entry.ctime_bytes)  # ctime
        write(entry.mtime_bytes)  # mtime
        path_str = str(entry.path)
        path: bytes = force_bytes(path_str, encoding=defenc)
        plen = len(path) & CE_NAMEMASK  # path length
        assert plen == len(path), "Path %s too long to fit into index" % entry.path
        flags = plen | (entry.flags & CE_NAMEMASK_INV)  # clear possible previous values
        write(
            pack(
                ">LLLLLL20sH",
                entry.dev,
                entry.inode,
                entry.mode,
                entry.uid,
                entry.gid,
                entry.size,
                entry.binsha,
                flags,
            )
        )
        write(path)
        real_size = (tell() - beginoffset + 8) & ~7
        write(b"\0" * ((beginoffset + real_size) - tell()))
    # END for each entry

    # write previously cached extensions data
    if extension_data is not None:
        stream_sha.write(extension_data)

    # write the sha over the content
    stream_sha.write_sha()


def read_header(stream: IO[bytes]) -> Tuple[int, int]:
    """Return tuple(version_long, num_entries) from the given stream"""
    type_id = stream.read(4)
    if type_id != b"DIRC":
        raise AssertionError("Invalid index file header: %r" % type_id)
    unpacked = cast(Tuple[int, int], unpack(">LL", stream.read(4 * 2)))
    version, num_entries = unpacked

    # TODO: handle version 3: extended data, see read-cache.c
    assert version in (1, 2)
    return version, num_entries


def entry_key(*entry: Union[BaseIndexEntry, PathLike, int]) -> Tuple[PathLike, int]:
    """:return: Key suitable to be used for the index.entries dictionary
    :param entry: One instance of type BaseIndexEntry or the path and the stage"""

    # def is_entry_key_tup(entry_key: Tuple) -> TypeGuard[Tuple[PathLike, int]]:
    #     return isinstance(entry_key, tuple) and len(entry_key) == 2

    if len(entry) == 1:
        entry_first = entry[0]
        assert isinstance(entry_first, BaseIndexEntry)
        return (entry_first.path, entry_first.stage)
    else:
        # assert is_entry_key_tup(entry)
        entry = cast(Tuple[PathLike, int], entry)
        return entry
    # END handle entry


def read_cache(
    stream: IO[bytes],
) -> Tuple[int, Dict[Tuple[PathLike, int], "IndexEntry"], bytes, bytes]:
    """Read a cache file from the given stream

    :return: tuple(version, entries_dict, extension_data, content_sha)

      * version is the integer version number
      * entries dict is a dictionary which maps IndexEntry instances to a path at a stage
      * extension_data is '' or 4 bytes of type + 4 bytes of size + size bytes
      * content_sha is a 20 byte sha on all cache file contents"""
    version, num_entries = read_header(stream)
    count = 0
    entries: Dict[Tuple[PathLike, int], "IndexEntry"] = {}

    read = stream.read
    tell = stream.tell
    while count < num_entries:
        beginoffset = tell()
        ctime = unpack(">8s", read(8))[0]
        mtime = unpack(">8s", read(8))[0]
        (dev, ino, mode, uid, gid, size, sha, flags) = unpack(">LLLLLL20sH", read(20 + 4 * 6 + 2))
        path_size = flags & CE_NAMEMASK
        path = read(path_size).decode(defenc)

        real_size = (tell() - beginoffset + 8) & ~7
        read((beginoffset + real_size) - tell())
        entry = IndexEntry((mode, sha, flags, path, ctime, mtime, dev, ino, uid, gid, size))
        # entry_key would be the method to use, but we safe the effort
        entries[(path, entry.stage)] = entry
        count += 1
    # END for each entry

    # the footer contains extension data and a sha on the content so far
    # Keep the extension footer,and verify we have a sha in the end
    # Extension data format is:
    # 4 bytes ID
    # 4 bytes length of chunk
    # repeated 0 - N times
    extension_data = stream.read(~0)
    assert (
        len(extension_data) > 19
    ), "Index Footer was not at least a sha on content as it was only %i bytes in size" % len(extension_data)

    content_sha = extension_data[-20:]

    # truncate the sha in the end as we will dynamically create it anyway
    extension_data = extension_data[:-20]

    return (version, entries, extension_data, content_sha)


def write_tree_from_cache(
    entries: List[IndexEntry], odb: "GitCmdObjectDB", sl: slice, si: int = 0
) -> Tuple[bytes, List["TreeCacheTup"]]:
    """Create a tree from the given sorted list of entries and put the respective
    trees into the given object database

    :param entries: **sorted** list of IndexEntries
    :param odb: object database to store the trees in
    :param si: start index at which we should start creating subtrees
    :param sl: slice indicating the range we should process on the entries list
    :return: tuple(binsha, list(tree_entry, ...)) a tuple of a sha and a list of
        tree entries being a tuple of hexsha, mode, name"""
    tree_items: List["TreeCacheTup"] = []

    ci = sl.start
    end = sl.stop
    while ci < end:
        entry = entries[ci]
        if entry.stage != 0:
            raise UnmergedEntriesError(entry)
        # END abort on unmerged
        ci += 1
        rbound = entry.path.find("/", si)
        if rbound == -1:
            # its not a tree
            tree_items.append((entry.binsha, entry.mode, entry.path[si:]))
        else:
            # find common base range
            base = entry.path[si:rbound]
            xi = ci
            while xi < end:
                oentry = entries[xi]
                orbound = oentry.path.find("/", si)
                if orbound == -1 or oentry.path[si:orbound] != base:
                    break
                # END abort on base mismatch
                xi += 1
            # END find common base

            # enter recursion
            # ci - 1 as we want to count our current item as well
            sha, _tree_entry_list = write_tree_from_cache(entries, odb, slice(ci - 1, xi), rbound + 1)
            tree_items.append((sha, S_IFDIR, base))

            # skip ahead
            ci = xi
        # END handle bounds
    # END for each entry

    # finally create the tree
    sio = BytesIO()
    tree_to_stream(tree_items, sio.write)  # writes to stream as bytes, but doesn't change tree_items
    sio.seek(0)

    istream = odb.store(IStream(str_tree_type, len(sio.getvalue()), sio))
    return (istream.binsha, tree_items)


def _tree_entry_to_baseindexentry(tree_entry: "TreeCacheTup", stage: int) -> BaseIndexEntry:
    return BaseIndexEntry((tree_entry[1], tree_entry[0], stage << CE_STAGESHIFT, tree_entry[2]))


def aggressive_tree_merge(odb: "GitCmdObjectDB", tree_shas: Sequence[bytes]) -> List[BaseIndexEntry]:
    """
    :return: list of BaseIndexEntries representing the aggressive merge of the given
        trees. All valid entries are on stage 0, whereas the conflicting ones are left
        on stage 1, 2 or 3, whereas stage 1 corresponds to the common ancestor tree,
        2 to our tree and 3 to 'their' tree.
    :param tree_shas: 1, 2 or 3 trees as identified by their binary 20 byte shas
        If 1 or two, the entries will effectively correspond to the last given tree
        If 3 are given, a 3 way merge is performed"""
    out: List[BaseIndexEntry] = []

    # one and two way is the same for us, as we don't have to handle an existing
    # index, instrea
    if len(tree_shas) in (1, 2):
        for entry in traverse_tree_recursive(odb, tree_shas[-1], ""):
            out.append(_tree_entry_to_baseindexentry(entry, 0))
        # END for each entry
        return out
    # END handle single tree

    if len(tree_shas) > 3:
        raise ValueError("Cannot handle %i trees at once" % len(tree_shas))

    # three trees
    for base, ours, theirs in traverse_trees_recursive(odb, tree_shas, ""):
        if base is not None:
            # base version exists
            if ours is not None:
                # ours exists
                if theirs is not None:
                    # it exists in all branches, if it was changed in both
                    # its a conflict, otherwise we take the changed version
                    # This should be the most common branch, so it comes first
                    if (base[0] != ours[0] and base[0] != theirs[0] and ours[0] != theirs[0]) or (
                        base[1] != ours[1] and base[1] != theirs[1] and ours[1] != theirs[1]
                    ):
                        # changed by both
                        out.append(_tree_entry_to_baseindexentry(base, 1))
                        out.append(_tree_entry_to_baseindexentry(ours, 2))
                        out.append(_tree_entry_to_baseindexentry(theirs, 3))
                    elif base[0] != ours[0] or base[1] != ours[1]:
                        # only we changed it
                        out.append(_tree_entry_to_baseindexentry(ours, 0))
                    else:
                        # either nobody changed it, or they did. In either
                        # case, use theirs
                        out.append(_tree_entry_to_baseindexentry(theirs, 0))
                    # END handle modification
                else:

                    if ours[0] != base[0] or ours[1] != base[1]:
                        # they deleted it, we changed it, conflict
                        out.append(_tree_entry_to_baseindexentry(base, 1))
                        out.append(_tree_entry_to_baseindexentry(ours, 2))
                    # else:
                    #   we didn't change it, ignore
                    #   pass
                    # END handle our change
                # END handle theirs
            else:
                if theirs is None:
                    # deleted in both, its fine - its out
                    pass
                else:
                    if theirs[0] != base[0] or theirs[1] != base[1]:
                        # deleted in ours, changed theirs, conflict
                        out.append(_tree_entry_to_baseindexentry(base, 1))
                        out.append(_tree_entry_to_baseindexentry(theirs, 3))
                    # END theirs changed
                    # else:
                    #   theirs didn't change
                    #   pass
                # END handle theirs
            # END handle ours
        else:
            # all three can't be None
            if ours is None:
                # added in their branch
                assert theirs is not None
                out.append(_tree_entry_to_baseindexentry(theirs, 0))
            elif theirs is None:
                # added in our branch
                out.append(_tree_entry_to_baseindexentry(ours, 0))
            else:
                # both have it, except for the base, see whether it changed
                if ours[0] != theirs[0] or ours[1] != theirs[1]:
                    out.append(_tree_entry_to_baseindexentry(ours, 2))
                    out.append(_tree_entry_to_baseindexentry(theirs, 3))
                else:
                    # it was added the same in both
                    out.append(_tree_entry_to_baseindexentry(ours, 0))
                # END handle two items
            # END handle heads
        # END handle base exists
    # END for each entries tuple

    return out
