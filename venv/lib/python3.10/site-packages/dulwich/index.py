# index.py -- File parser/writer for the git index file
# Copyright (C) 2008-2013 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Parser for the git index file format."""

import collections
import os
import stat
import struct
import sys
from typing import (Any, BinaryIO, Callable, Dict, Iterable, Iterator, List,
                    Optional, Tuple, Union)

from .file import GitFile
from .object_store import iter_tree_contents
from .objects import (S_IFGITLINK, S_ISGITLINK, Blob, ObjectID, Tree,
                      hex_to_sha, sha_to_hex)
from .pack import ObjectContainer, SHA1Reader, SHA1Writer

# TODO(jelmer): Switch to dataclass?
IndexEntry = collections.namedtuple(
    "IndexEntry",
    [
        "ctime",
        "mtime",
        "dev",
        "ino",
        "mode",
        "uid",
        "gid",
        "size",
        "sha",
        "flags",
        "extended_flags",
    ],
)


# 2-bit stage (during merge)
FLAG_STAGEMASK = 0x3000

# assume-valid
FLAG_VALID = 0x8000

# extended flag (must be zero in version 2)
FLAG_EXTENDED = 0x4000


# used by sparse checkout
EXTENDED_FLAG_SKIP_WORKTREE = 0x4000

# used by "git add -N"
EXTENDED_FLAG_INTEND_TO_ADD = 0x2000


DEFAULT_VERSION = 2


def pathsplit(path: bytes) -> Tuple[bytes, bytes]:
    """Split a /-delimited path into a directory part and a basename.

    Args:
      path: The path to split.
    Returns:
      Tuple with directory name and basename
    """
    try:
        (dirname, basename) = path.rsplit(b"/", 1)
    except ValueError:
        return (b"", path)
    else:
        return (dirname, basename)


def pathjoin(*args):
    """Join a /-delimited path."""
    return b"/".join([p for p in args if p])


def read_cache_time(f):
    """Read a cache time.

    Args:
      f: File-like object to read from
    Returns:
      Tuple with seconds and nanoseconds
    """
    return struct.unpack(">LL", f.read(8))


def write_cache_time(f, t):
    """Write a cache time.

    Args:
      f: File-like object to write to
      t: Time to write (as int, float or tuple with secs and nsecs)
    """
    if isinstance(t, int):
        t = (t, 0)
    elif isinstance(t, float):
        (secs, nsecs) = divmod(t, 1.0)
        t = (int(secs), int(nsecs * 1000000000))
    elif not isinstance(t, tuple):
        raise TypeError(t)
    f.write(struct.pack(">LL", *t))


def read_cache_entry(f, version: int) -> Tuple[str, IndexEntry]:
    """Read an entry from a cache file.

    Args:
      f: File-like object to read from
    Returns:
      tuple with: name, IndexEntry
    """
    beginoffset = f.tell()
    ctime = read_cache_time(f)
    mtime = read_cache_time(f)
    (
        dev,
        ino,
        mode,
        uid,
        gid,
        size,
        sha,
        flags,
    ) = struct.unpack(">LLLLLL20sH", f.read(20 + 4 * 6 + 2))
    if flags & FLAG_EXTENDED:
        if version < 3:
            raise AssertionError(
                'extended flag set in index with version < 3')
        (extended_flags, ) = struct.unpack(">H", f.read(2))
    else:
        extended_flags = 0
    name = f.read(flags & 0x0FFF)
    # Padding:
    if version < 4:
        real_size = (f.tell() - beginoffset + 8) & ~7
        f.read((beginoffset + real_size) - f.tell())
    return (
        name,
        IndexEntry(
            ctime,
            mtime,
            dev,
            ino,
            mode,
            uid,
            gid,
            size,
            sha_to_hex(sha),
            flags & ~0x0FFF,
            extended_flags,
        ))


def write_cache_entry(f, name: bytes, entry: IndexEntry, version: int) -> None:
    """Write an index entry to a file.

    Args:
      f: File object
      entry: IndexEntry to write, tuple with:
    """
    beginoffset = f.tell()
    write_cache_time(f, entry.ctime)
    write_cache_time(f, entry.mtime)
    flags = len(name) | (entry.flags & ~0x0FFF)
    if entry.extended_flags:
        flags |= FLAG_EXTENDED
    if flags & FLAG_EXTENDED and version is not None and version < 3:
        raise AssertionError('unable to use extended flags in version < 3')
    f.write(
        struct.pack(
            b">LLLLLL20sH",
            entry.dev & 0xFFFFFFFF,
            entry.ino & 0xFFFFFFFF,
            entry.mode,
            entry.uid,
            entry.gid,
            entry.size,
            hex_to_sha(entry.sha),
            flags,
        )
    )
    if flags & FLAG_EXTENDED:
        f.write(struct.pack(b">H", entry.extended_flags))
    f.write(name)
    if version < 4:
        real_size = (f.tell() - beginoffset + 8) & ~7
        f.write(b"\0" * ((beginoffset + real_size) - f.tell()))


class UnsupportedIndexFormat(Exception):
    """An unsupported index format was encountered."""

    def __init__(self, version):
        self.index_format_version = version


def read_index(f: BinaryIO):
    """Read an index file, yielding the individual entries."""
    header = f.read(4)
    if header != b"DIRC":
        raise AssertionError("Invalid index file header: %r" % header)
    (version, num_entries) = struct.unpack(b">LL", f.read(4 * 2))
    if version not in (1, 2, 3):
        raise UnsupportedIndexFormat(version)
    for i in range(num_entries):
        yield read_cache_entry(f, version)


def read_index_dict(f) -> Dict[bytes, IndexEntry]:
    """Read an index file and return it as a dictionary.

    Args:
      f: File object to read from
    """
    ret = {}
    for name, entry in read_index(f):
        ret[name] = entry
    return ret


def write_index(f: BinaryIO, entries: List[Tuple[bytes, IndexEntry]], version: Optional[int] = None):
    """Write an index file.

    Args:
      f: File-like object to write to
      version: Version number to write
      entries: Iterable over the entries to write
    """
    if version is None:
        version = DEFAULT_VERSION
    f.write(b"DIRC")
    f.write(struct.pack(b">LL", version, len(entries)))
    for name, entry in entries:
        write_cache_entry(f, name, entry, version)


def write_index_dict(
    f: BinaryIO,
    entries: Dict[bytes, IndexEntry],
    version: Optional[int] = None,
) -> None:
    """Write an index file based on the contents of a dictionary."""
    entries_list = []
    for name in sorted(entries):
        entries_list.append((name, entries[name]))
    write_index(f, entries_list, version=version)


def cleanup_mode(mode: int) -> int:
    """Cleanup a mode value.

    This will return a mode that can be stored in a tree object.

    Args:
      mode: Mode to clean up.
    Returns:
      mode
    """
    if stat.S_ISLNK(mode):
        return stat.S_IFLNK
    elif stat.S_ISDIR(mode):
        return stat.S_IFDIR
    elif S_ISGITLINK(mode):
        return S_IFGITLINK
    ret = stat.S_IFREG | 0o644
    if mode & 0o100:
        ret |= 0o111
    return ret


class Index:
    """A Git Index file."""

    def __init__(self, filename: Union[bytes, str], read=True):
        """Create an index object associated with the given filename.

        Args:
          filename: Path to the index file
          read: Whether to initialize the index from the given file, should it exist.
        """
        self._filename = filename
        # TODO(jelmer): Store the version returned by read_index
        self._version = None
        self.clear()
        if read:
            self.read()

    @property
    def path(self):
        return self._filename

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self._filename)

    def write(self) -> None:
        """Write current contents of index to disk."""
        f = GitFile(self._filename, "wb")
        try:
            f = SHA1Writer(f)
            write_index_dict(f, self._byname, version=self._version)
        finally:
            f.close()

    def read(self):
        """Read current contents of index from disk."""
        if not os.path.exists(self._filename):
            return
        f = GitFile(self._filename, "rb")
        try:
            f = SHA1Reader(f)
            for name, entry in read_index(f):
                self[name] = entry
            # FIXME: Additional data?
            f.read(os.path.getsize(self._filename) - f.tell() - 20)
            f.check_sha()
        finally:
            f.close()

    def __len__(self) -> int:
        """Number of entries in this index file."""
        return len(self._byname)

    def __getitem__(self, name: bytes) -> IndexEntry:
        """Retrieve entry by relative path.

        Returns: tuple with (ctime, mtime, dev, ino, mode, uid, gid, size, sha,
            flags)
        """
        return self._byname[name]

    def __iter__(self) -> Iterator[bytes]:
        """Iterate over the paths in this index."""
        return iter(self._byname)

    def get_sha1(self, path: bytes) -> bytes:
        """Return the (git object) SHA1 for the object at a path."""
        return self[path].sha

    def get_mode(self, path: bytes) -> int:
        """Return the POSIX file mode for the object at a path."""
        return self[path].mode

    def iterobjects(self) -> Iterable[Tuple[bytes, bytes, int]]:
        """Iterate over path, sha, mode tuples for use with commit_tree."""
        for path in self:
            entry = self[path]
            yield path, entry.sha, cleanup_mode(entry.mode)

    def clear(self):
        """Remove all contents from this index."""
        self._byname = {}

    def __setitem__(self, name: bytes, x: IndexEntry):
        assert isinstance(name, bytes)
        assert len(x) == len(IndexEntry._fields)
        # Remove the old entry if any
        self._byname[name] = IndexEntry(*x)

    def __delitem__(self, name: bytes):
        assert isinstance(name, bytes)
        del self._byname[name]

    def iteritems(self) -> Iterator[Tuple[bytes, IndexEntry]]:
        return self._byname.items()

    def items(self) -> Iterator[Tuple[bytes, IndexEntry]]:
        return self._byname.items()

    def update(self, entries: Dict[bytes, IndexEntry]):
        for name, value in entries.items():
            self[name] = value

    def changes_from_tree(
            self, object_store, tree: ObjectID, want_unchanged: bool = False):
        """Find the differences between the contents of this index and a tree.

        Args:
          object_store: Object store to use for retrieving tree contents
          tree: SHA1 of the root tree
          want_unchanged: Whether unchanged files should be reported
        Returns: Iterator over tuples with (oldpath, newpath), (oldmode,
            newmode), (oldsha, newsha)
        """

        def lookup_entry(path):
            entry = self[path]
            return entry.sha, cleanup_mode(entry.mode)

        yield from changes_from_tree(
            self._byname.keys(),
            lookup_entry,
            object_store,
            tree,
            want_unchanged=want_unchanged,
        )

    def commit(self, object_store):
        """Create a new tree from an index.

        Args:
          object_store: Object store to save the tree in
        Returns:
          Root tree SHA
        """
        return commit_tree(object_store, self.iterobjects())


def commit_tree(
    object_store: ObjectContainer, blobs: Iterable[Tuple[bytes, bytes, int]]
) -> bytes:
    """Commit a new tree.

    Args:
      object_store: Object store to add trees to
      blobs: Iterable over blob path, sha, mode entries
    Returns:
      SHA1 of the created tree.
    """
    trees: Dict[bytes, Any] = {b"": {}}

    def add_tree(path):
        if path in trees:
            return trees[path]
        dirname, basename = pathsplit(path)
        t = add_tree(dirname)
        assert isinstance(basename, bytes)
        newtree = {}
        t[basename] = newtree
        trees[path] = newtree
        return newtree

    for path, sha, mode in blobs:
        tree_path, basename = pathsplit(path)
        tree = add_tree(tree_path)
        tree[basename] = (mode, sha)

    def build_tree(path):
        tree = Tree()
        for basename, entry in trees[path].items():
            if isinstance(entry, dict):
                mode = stat.S_IFDIR
                sha = build_tree(pathjoin(path, basename))
            else:
                (mode, sha) = entry
            tree.add(basename, mode, sha)
        object_store.add_object(tree)
        return tree.id

    return build_tree(b"")


def commit_index(object_store: ObjectContainer, index: Index) -> bytes:
    """Create a new tree from an index.

    Args:
      object_store: Object store to save the tree in
      index: Index file
    Note: This function is deprecated, use index.commit() instead.
    Returns: Root tree sha.
    """
    return commit_tree(object_store, index.iterobjects())


def changes_from_tree(
    names: Iterable[bytes],
    lookup_entry: Callable[[bytes], Tuple[bytes, int]],
    object_store: ObjectContainer,
    tree: Optional[bytes],
    want_unchanged=False,
) -> Iterable[
    Tuple[
        Tuple[Optional[bytes], Optional[bytes]],
        Tuple[Optional[int], Optional[int]],
        Tuple[Optional[bytes], Optional[bytes]],
    ]
]:
    """Find the differences between the contents of a tree and
    a working copy.

    Args:
      names: Iterable of names in the working copy
      lookup_entry: Function to lookup an entry in the working copy
      object_store: Object store to use for retrieving tree contents
      tree: SHA1 of the root tree, or None for an empty tree
      want_unchanged: Whether unchanged files should be reported
    Returns: Iterator over tuples with (oldpath, newpath), (oldmode, newmode),
        (oldsha, newsha)
    """
    # TODO(jelmer): Support a include_trees option
    other_names = set(names)

    if tree is not None:
        for (name, mode, sha) in iter_tree_contents(object_store, tree):
            try:
                (other_sha, other_mode) = lookup_entry(name)
            except KeyError:
                # Was removed
                yield ((name, None), (mode, None), (sha, None))
            else:
                other_names.remove(name)
                if want_unchanged or other_sha != sha or other_mode != mode:
                    yield ((name, name), (mode, other_mode), (sha, other_sha))

    # Mention added files
    for name in other_names:
        try:
            (other_sha, other_mode) = lookup_entry(name)
        except KeyError:
            pass
        else:
            yield ((None, name), (None, other_mode), (None, other_sha))


def index_entry_from_stat(
    stat_val, hex_sha: bytes, flags: int, mode: Optional[int] = None,
    extended_flags: Optional[int] = None
):
    """Create a new index entry from a stat value.

    Args:
      stat_val: POSIX stat_result instance
      hex_sha: Hex sha of the object
      flags: Index flags
    """
    if mode is None:
        mode = cleanup_mode(stat_val.st_mode)

    return IndexEntry(
        stat_val.st_ctime,
        stat_val.st_mtime,
        stat_val.st_dev,
        stat_val.st_ino,
        mode,
        stat_val.st_uid,
        stat_val.st_gid,
        stat_val.st_size,
        hex_sha,
        flags,
        extended_flags
    )


if sys.platform == 'win32':
    # On Windows, creating symlinks either requires administrator privileges
    # or developer mode. Raise a more helpful error when we're unable to
    # create symlinks

    # https://github.com/jelmer/dulwich/issues/1005

    class WindowsSymlinkPermissionError(PermissionError):

        def __init__(self, errno, msg, filename):
            super(PermissionError, self).__init__(
                errno, "Unable to create symlink; "
                "do you have developer mode enabled? %s" % msg,
                filename)

    def symlink(src, dst, target_is_directory=False, *, dir_fd=None):
        try:
            return os.symlink(
                src, dst, target_is_directory=target_is_directory,
                dir_fd=dir_fd)
        except PermissionError as e:
            raise WindowsSymlinkPermissionError(
                e.errno, e.strerror, e.filename) from e
else:
    symlink = os.symlink


def build_file_from_blob(
        blob: Blob, mode: int, target_path: bytes, *, honor_filemode=True,
        tree_encoding="utf-8", symlink_fn=None
):
    """Build a file or symlink on disk based on a Git object.

    Args:
      blob: The git object
      mode: File mode
      target_path: Path to write to
      honor_filemode: An optional flag to honor core.filemode setting in
        config file, default is core.filemode=True, change executable bit
      symlink: Function to use for creating symlinks
    Returns: stat object for the file
    """
    try:
        oldstat = os.lstat(target_path)
    except FileNotFoundError:
        oldstat = None
    contents = blob.as_raw_string()
    if stat.S_ISLNK(mode):
        if oldstat:
            os.unlink(target_path)
        if sys.platform == "win32":
            # os.readlink on Python3 on Windows requires a unicode string.
            contents = contents.decode(tree_encoding)  # type: ignore
            target_path = target_path.decode(tree_encoding)  # type: ignore
        (symlink_fn or symlink)(contents, target_path)
    else:
        if oldstat is not None and oldstat.st_size == len(contents):
            with open(target_path, "rb") as f:
                if f.read() == contents:
                    return oldstat

        with open(target_path, "wb") as f:
            # Write out file
            f.write(contents)

        if honor_filemode:
            os.chmod(target_path, mode)

    return os.lstat(target_path)


INVALID_DOTNAMES = (b".git", b".", b"..", b"")


def validate_path_element_default(element: bytes) -> bool:
    return element.lower() not in INVALID_DOTNAMES


def validate_path_element_ntfs(element: bytes) -> bool:
    stripped = element.rstrip(b". ").lower()
    if stripped in INVALID_DOTNAMES:
        return False
    if stripped == b"git~1":
        return False
    return True


def validate_path(path: bytes,
                  element_validator=validate_path_element_default) -> bool:
    """Default path validator that just checks for .git/."""
    parts = path.split(b"/")
    for p in parts:
        if not element_validator(p):
            return False
    else:
        return True


def build_index_from_tree(
    root_path: Union[str, bytes],
    index_path: Union[str, bytes],
    object_store: ObjectContainer,
    tree_id: bytes,
    honor_filemode: bool = True,
    validate_path_element=validate_path_element_default,
    symlink_fn=None
):
    """Generate and materialize index from a tree

    Args:
      tree_id: Tree to materialize
      root_path: Target dir for materialized index files
      index_path: Target path for generated index
      object_store: Non-empty object store holding tree contents
      honor_filemode: An optional flag to honor core.filemode setting in
        config file, default is core.filemode=True, change executable bit
      validate_path_element: Function to validate path elements to check
        out; default just refuses .git and .. directories.

    Note: existing index is wiped and contents are not merged
        in a working dir. Suitable only for fresh clones.
    """
    index = Index(index_path, read=False)
    if not isinstance(root_path, bytes):
        root_path = os.fsencode(root_path)

    for entry in iter_tree_contents(object_store, tree_id):
        if not validate_path(entry.path, validate_path_element):
            continue
        full_path = _tree_to_fs_path(root_path, entry.path)

        if not os.path.exists(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path))

        # TODO(jelmer): Merge new index into working tree
        if S_ISGITLINK(entry.mode):
            if not os.path.isdir(full_path):
                os.mkdir(full_path)
            st = os.lstat(full_path)
            # TODO(jelmer): record and return submodule paths
        else:
            obj = object_store[entry.sha]
            assert isinstance(obj, Blob)
            st = build_file_from_blob(
                obj, entry.mode, full_path,
                honor_filemode=honor_filemode,
                symlink_fn=symlink_fn,
            )

        # Add file to index
        if not honor_filemode or S_ISGITLINK(entry.mode):
            # we can not use tuple slicing to build a new tuple,
            # because on windows that will convert the times to
            # longs, which causes errors further along
            st_tuple = (
                entry.mode,
                st.st_ino,
                st.st_dev,
                st.st_nlink,
                st.st_uid,
                st.st_gid,
                st.st_size,
                st.st_atime,
                st.st_mtime,
                st.st_ctime,
            )
            st = st.__class__(st_tuple)
        index[entry.path] = index_entry_from_stat(st, entry.sha, 0)

    index.write()


def blob_from_path_and_mode(fs_path: bytes, mode: int,
                            tree_encoding="utf-8"):
    """Create a blob from a path and a stat object.

    Args:
      fs_path: Full file system path to file
      mode: File mode
    Returns: A `Blob` object
    """
    assert isinstance(fs_path, bytes)
    blob = Blob()
    if stat.S_ISLNK(mode):
        if sys.platform == "win32":
            # os.readlink on Python3 on Windows requires a unicode string.
            blob.data = os.readlink(os.fsdecode(fs_path)).encode(tree_encoding)
        else:
            blob.data = os.readlink(fs_path)
    else:
        with open(fs_path, "rb") as f:
            blob.data = f.read()
    return blob


def blob_from_path_and_stat(fs_path: bytes, st, tree_encoding="utf-8"):
    """Create a blob from a path and a stat object.

    Args:
      fs_path: Full file system path to file
      st: A stat object
    Returns: A `Blob` object
    """
    return blob_from_path_and_mode(fs_path, st.st_mode, tree_encoding)


def read_submodule_head(path: Union[str, bytes]) -> Optional[bytes]:
    """Read the head commit of a submodule.

    Args:
      path: path to the submodule
    Returns: HEAD sha, None if not a valid head/repository
    """
    from .errors import NotGitRepository
    from .repo import Repo

    # Repo currently expects a "str", so decode if necessary.
    # TODO(jelmer): Perhaps move this into Repo() ?
    if not isinstance(path, str):
        path = os.fsdecode(path)
    try:
        repo = Repo(path)
    except NotGitRepository:
        return None
    try:
        return repo.head()
    except KeyError:
        return None


def _has_directory_changed(tree_path: bytes, entry):
    """Check if a directory has changed after getting an error.

    When handling an error trying to create a blob from a path, call this
    function. It will check if the path is a directory. If it's a directory
    and a submodule, check the submodule head to see if it's has changed. If
    not, consider the file as changed as Git tracked a file and not a
    directory.

    Return true if the given path should be considered as changed and False
    otherwise or if the path is not a directory.
    """
    # This is actually a directory
    if os.path.exists(os.path.join(tree_path, b".git")):
        # Submodule
        head = read_submodule_head(tree_path)
        if entry.sha != head:
            return True
    else:
        # The file was changed to a directory, so consider it removed.
        return True

    return False


def get_unstaged_changes(
        index: Index, root_path: Union[str, bytes],
        filter_blob_callback=None):
    """Walk through an index and check for differences against working tree.

    Args:
      index: index to check
      root_path: path in which to find files
    Returns: iterator over paths with unstaged changes
    """
    # For each entry in the index check the sha1 & ensure not staged
    if not isinstance(root_path, bytes):
        root_path = os.fsencode(root_path)

    for tree_path, entry in index.iteritems():
        full_path = _tree_to_fs_path(root_path, tree_path)
        try:
            st = os.lstat(full_path)
            if stat.S_ISDIR(st.st_mode):
                if _has_directory_changed(tree_path, entry):
                    yield tree_path
                continue

            if not stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                continue

            blob = blob_from_path_and_stat(full_path, st)

            if filter_blob_callback is not None:
                blob = filter_blob_callback(blob, tree_path)
        except FileNotFoundError:
            # The file was removed, so we assume that counts as
            # different from whatever file used to exist.
            yield tree_path
        else:
            if blob.id != entry.sha:
                yield tree_path


os_sep_bytes = os.sep.encode("ascii")


def _tree_to_fs_path(root_path: bytes, tree_path: bytes):
    """Convert a git tree path to a file system path.

    Args:
      root_path: Root filesystem path
      tree_path: Git tree path as bytes

    Returns: File system path.
    """
    assert isinstance(tree_path, bytes)
    if os_sep_bytes != b"/":
        sep_corrected_path = tree_path.replace(b"/", os_sep_bytes)
    else:
        sep_corrected_path = tree_path
    return os.path.join(root_path, sep_corrected_path)


def _fs_to_tree_path(fs_path: Union[str, bytes]) -> bytes:
    """Convert a file system path to a git tree path.

    Args:
      fs_path: File system path.

    Returns:  Git tree path as bytes
    """
    if not isinstance(fs_path, bytes):
        fs_path_bytes = os.fsencode(fs_path)
    else:
        fs_path_bytes = fs_path
    if os_sep_bytes != b"/":
        tree_path = fs_path_bytes.replace(os_sep_bytes, b"/")
    else:
        tree_path = fs_path_bytes
    return tree_path


def index_entry_from_directory(st, path: bytes) -> Optional[IndexEntry]:
    if os.path.exists(os.path.join(path, b".git")):
        head = read_submodule_head(path)
        if head is None:
            return None
        return index_entry_from_stat(st, head, 0, mode=S_IFGITLINK)
    return None


def index_entry_from_path(
        path: bytes, object_store: Optional[ObjectContainer] = None
) -> Optional[IndexEntry]:
    """Create an index from a filesystem path.

    This returns an index value for files, symlinks
    and tree references. for directories and
    non-existent files it returns None

    Args:
      path: Path to create an index entry for
      object_store: Optional object store to
        save new blobs in
    Returns: An index entry; None for directories
    """
    assert isinstance(path, bytes)
    st = os.lstat(path)
    if stat.S_ISDIR(st.st_mode):
        return index_entry_from_directory(st, path)

    if stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
        blob = blob_from_path_and_stat(path, st)
        if object_store is not None:
            object_store.add_object(blob)
        return index_entry_from_stat(st, blob.id, 0)

    return None


def iter_fresh_entries(
    paths: Iterable[bytes], root_path: bytes,
    object_store: Optional[ObjectContainer] = None
) -> Iterator[Tuple[bytes, Optional[IndexEntry]]]:
    """Iterate over current versions of index entries on disk.

    Args:
      paths: Paths to iterate over
      root_path: Root path to access from
      object_store: Optional store to save new blobs in
    Returns: Iterator over path, index_entry
    """
    for path in paths:
        p = _tree_to_fs_path(root_path, path)
        try:
            entry = index_entry_from_path(p, object_store=object_store)
        except (FileNotFoundError, IsADirectoryError):
            entry = None
        yield path, entry


def iter_fresh_objects(
        paths: Iterable[bytes], root_path: bytes, include_deleted=False,
        object_store=None) -> Iterator[
            Tuple[bytes, Optional[bytes], Optional[int]]]:
    """Iterate over versions of objects on disk referenced by index.

    Args:
      root_path: Root path to access from
      include_deleted: Include deleted entries with sha and
        mode set to None
      object_store: Optional object store to report new items to
    Returns: Iterator over path, sha, mode
    """
    for path, entry in iter_fresh_entries(
            paths, root_path, object_store=object_store):
        if entry is None:
            if include_deleted:
                yield path, None, None
        else:
            entry = IndexEntry(*entry)
            yield path, entry.sha, cleanup_mode(entry.mode)


def refresh_index(index: Index, root_path: bytes):
    """Refresh the contents of an index.

    This is the equivalent to running 'git commit -a'.

    Args:
      index: Index to update
      root_path: Root filesystem path
    """
    for path, entry in iter_fresh_entries(index, root_path):
        if entry:
            index[path] = entry


class locked_index:
    """Lock the index while making modifications.

    Works as a context manager.
    """
    def __init__(self, path: Union[bytes, str]):
        self._path = path

    def __enter__(self):
        self._file = GitFile(self._path, "wb")
        self._index = Index(self._path)
        return self._index

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self._file.abort()
            return
        try:
            f = SHA1Writer(self._file)
            write_index_dict(f, self._index._byname)
        except BaseException:
            self._file.abort()
        else:
            f.close()
