# object_store.py -- Object store for git objects
# Copyright (C) 2008-2013 Jelmer Vernooij <jelmer@jelmer.uk>
#                         and others
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


"""Git object store interfaces and implementation."""

import os
import stat
import sys
import warnings
from contextlib import suppress
from io import BytesIO
from typing import (Callable, Dict, Iterable, Iterator, List, Optional,
                    Sequence, Set, Tuple, cast)

try:
    from typing import Protocol
except ImportError:  # python << 3.8
    from typing_extensions import Protocol  # type: ignore

from .errors import NotTreeError
from .file import GitFile
from .objects import (S_ISGITLINK, ZERO_SHA, Blob, Commit, ObjectID, ShaFile,
                      Tag, Tree, TreeEntry, hex_to_filename, hex_to_sha,
                      object_class, sha_to_hex, valid_hexsha)
from .pack import (PACK_SPOOL_FILE_MAX_SIZE, ObjectContainer, Pack, PackData,
                   PackedObjectContainer, PackFileDisappeared, PackHint,
                   PackIndexer, PackInflater, PackStreamCopier, UnpackedObject,
                   extend_pack, full_unpacked_object,
                   generate_unpacked_objects, iter_sha1, load_pack_index_file,
                   pack_objects_to_data, write_pack_data, write_pack_index)
from .protocol import DEPTH_INFINITE
from .refs import PEELED_TAG_SUFFIX, Ref

INFODIR = "info"
PACKDIR = "pack"

# use permissions consistent with Git; just readable by everyone
# TODO: should packs also be non-writable on Windows? if so, that
# would requite some rather significant adjustments to the test suite
PACK_MODE = 0o444 if sys.platform != "win32" else 0o644


class PackContainer(Protocol):

    def add_pack(
        self
    ) -> Tuple[BytesIO, Callable[[], None], Callable[[], None]]:
        """Add a new pack."""


class BaseObjectStore:
    """Object store interface."""

    def determine_wants_all(
        self,
        refs: Dict[Ref, ObjectID],
        depth: Optional[int] = None
    ) -> List[ObjectID]:
        def _want_deepen(sha):
            if not depth:
                return False
            if depth == DEPTH_INFINITE:
                return True
            return depth > self._get_depth(sha)

        return [
            sha
            for (ref, sha) in refs.items()
            if (sha not in self or _want_deepen(sha))
            and not ref.endswith(PEELED_TAG_SUFFIX)
            and not sha == ZERO_SHA
        ]

    def contains_loose(self, sha):
        """Check if a particular object is present by SHA1 and is loose."""
        raise NotImplementedError(self.contains_loose)

    def __contains__(self, sha1: bytes) -> bool:
        """Check if a particular object is present by SHA1.

        This method makes no distinction between loose and packed objects.
        """
        return self.contains_loose(sha1)

    @property
    def packs(self):
        """Iterable of pack objects."""
        raise NotImplementedError

    def get_raw(self, name):
        """Obtain the raw text for an object.

        Args:
          name: sha for the object.
        Returns: tuple with numeric type and object contents.
        """
        raise NotImplementedError(self.get_raw)

    def __getitem__(self, sha1: ObjectID) -> ShaFile:
        """Obtain an object by SHA1."""
        type_num, uncomp = self.get_raw(sha1)
        return ShaFile.from_raw_string(type_num, uncomp, sha=sha1)

    def __iter__(self):
        """Iterate over the SHAs that are present in this store."""
        raise NotImplementedError(self.__iter__)

    def add_object(self, obj):
        """Add a single object to this object store."""
        raise NotImplementedError(self.add_object)

    def add_objects(self, objects, progress=None):
        """Add a set of objects to this object store.

        Args:
          objects: Iterable over a list of (object, path) tuples
        """
        raise NotImplementedError(self.add_objects)

    def tree_changes(
        self,
        source,
        target,
        want_unchanged=False,
        include_trees=False,
        change_type_same=False,
        rename_detector=None,
    ):
        """Find the differences between the contents of two trees

        Args:
          source: SHA1 of the source tree
          target: SHA1 of the target tree
          want_unchanged: Whether unchanged files should be reported
          include_trees: Whether to include trees
          change_type_same: Whether to report files changing
            type in the same entry.
        Returns: Iterator over tuples with
            (oldpath, newpath), (oldmode, newmode), (oldsha, newsha)
        """

        from .diff_tree import tree_changes
        for change in tree_changes(
            self,
            source,
            target,
            want_unchanged=want_unchanged,
            include_trees=include_trees,
            change_type_same=change_type_same,
            rename_detector=rename_detector,
        ):
            yield (
                (change.old.path, change.new.path),
                (change.old.mode, change.new.mode),
                (change.old.sha, change.new.sha),
            )

    def iter_tree_contents(self, tree_id, include_trees=False):
        """Iterate the contents of a tree and all subtrees.

        Iteration is depth-first pre-order, as in e.g. os.walk.

        Args:
          tree_id: SHA1 of the tree.
          include_trees: If True, include tree objects in the iteration.
        Returns: Iterator over TreeEntry namedtuples for all the objects in a
            tree.
        """
        warnings.warn(
            "Please use dulwich.object_store.iter_tree_contents",
            DeprecationWarning, stacklevel=2)
        return iter_tree_contents(self, tree_id, include_trees=include_trees)

    def iterobjects_subset(self, shas: Iterable[bytes], *, allow_missing: bool = False) -> Iterator[ShaFile]:
        for sha in shas:
            try:
                yield self[sha]
            except KeyError:
                if not allow_missing:
                    raise

    def find_missing_objects(
        self,
        haves,
        wants,
        shallow=None,
        progress=None,
        get_tagged=None,
        get_parents=lambda commit: commit.parents,
    ):
        """Find the missing objects required for a set of revisions.

        Args:
          haves: Iterable over SHAs already in common.
          wants: Iterable over SHAs of objects to fetch.
          shallow: Set of shallow commit SHA1s to skip
          progress: Simple progress function that will be called with
            updated progress strings.
          get_tagged: Function that returns a dict of pointed-to sha ->
            tag sha for including tags.
          get_parents: Optional function for getting the parents of a
            commit.
        Returns: Iterator over (sha, path) pairs.
        """
        warnings.warn(
            'Please use MissingObjectFinder(store)', DeprecationWarning)
        finder = MissingObjectFinder(
            self,
            haves=haves,
            wants=wants,
            shallow=shallow,
            progress=progress,
            get_tagged=get_tagged,
            get_parents=get_parents,
        )
        return iter(finder)

    def find_common_revisions(self, graphwalker):
        """Find which revisions this store has in common using graphwalker.

        Args:
          graphwalker: A graphwalker object.
        Returns: List of SHAs that are in common
        """
        haves = []
        sha = next(graphwalker)
        while sha:
            if sha in self:
                haves.append(sha)
                graphwalker.ack(sha)
            sha = next(graphwalker)
        return haves

    def generate_pack_data(
        self, have, want, shallow=None, progress=None,
        ofs_delta=True
    ) -> Tuple[int, Iterator[UnpackedObject]]:
        """Generate pack data objects for a set of wants/haves.

        Args:
          have: List of SHA1s of objects that should not be sent
          want: List of SHA1s of objects that should be sent
          shallow: Set of shallow commit SHA1s to skip
          ofs_delta: Whether OFS deltas can be included
          progress: Optional progress reporting method
        """
        # Note that the pack-specific implementation below is more efficient,
        # as it reuses deltas
        missing_objects = MissingObjectFinder(
            self, haves=have, wants=want, shallow=shallow, progress=progress)
        object_ids = list(missing_objects)
        return pack_objects_to_data(
            [(self[oid], path) for oid, path in object_ids], ofs_delta=ofs_delta,
            progress=progress)

    def peel_sha(self, sha):
        """Peel all tags from a SHA.

        Args:
          sha: The object SHA to peel.
        Returns: The fully-peeled SHA1 of a tag object, after peeling all
            intermediate tags; if the original ref does not point to a tag,
            this will equal the original SHA1.
        """
        warnings.warn(
            "Please use dulwich.object_store.peel_sha()",
            DeprecationWarning, stacklevel=2)
        return peel_sha(self, sha)[1]

    def _get_depth(
        self, head, get_parents=lambda commit: commit.parents, max_depth=None,
    ):
        """Return the current available depth for the given head.
        For commits with multiple parents, the largest possible depth will be
        returned.

        Args:
            head: commit to start from
            get_parents: optional function for getting the parents of a commit
            max_depth: maximum depth to search
        """
        if head not in self:
            return 0
        current_depth = 1
        queue = [(head, current_depth)]
        while queue and (max_depth is None or current_depth < max_depth):
            e, depth = queue.pop(0)
            current_depth = max(current_depth, depth)
            cmt = self[e]
            if isinstance(cmt, Tag):
                _cls, sha = cmt.object
                cmt = self[sha]
            queue.extend(
                (parent, depth + 1)
                for parent in get_parents(cmt)
                if parent in self
            )
        return current_depth

    def close(self):
        """Close any files opened by this object store."""
        # Default implementation is a NO-OP


class PackBasedObjectStore(BaseObjectStore):
    def __init__(self, pack_compression_level=-1):
        self._pack_cache = {}
        self.pack_compression_level = pack_compression_level

    def add_pack(
        self
    ) -> Tuple[BytesIO, Callable[[], None], Callable[[], None]]:
        """Add a new pack to this object store."""
        raise NotImplementedError(self.add_pack)

    def add_pack_data(self, count: int, unpacked_objects: Iterator[UnpackedObject], progress=None) -> None:
        """Add pack data to this object store.

        Args:
          count: Number of items to add
          pack_data: Iterator over pack data tuples
        """
        if count == 0:
            # Don't bother writing an empty pack file
            return
        f, commit, abort = self.add_pack()
        try:
            write_pack_data(
                f.write,
                unpacked_objects,
                num_records=count,
                progress=progress,
                compression_level=self.pack_compression_level,
            )
        except BaseException:
            abort()
            raise
        else:
            return commit()

    @property
    def alternates(self):
        return []

    def contains_packed(self, sha):
        """Check if a particular object is present by SHA1 and is packed.

        This does not check alternates.
        """
        for pack in self.packs:
            try:
                if sha in pack:
                    return True
            except PackFileDisappeared:
                pass
        return False

    def __contains__(self, sha):
        """Check if a particular object is present by SHA1.

        This method makes no distinction between loose and packed objects.
        """
        if self.contains_packed(sha) or self.contains_loose(sha):
            return True
        for alternate in self.alternates:
            if sha in alternate:
                return True
        return False

    def _add_cached_pack(self, base_name, pack):
        """Add a newly appeared pack to the cache by path."""
        prev_pack = self._pack_cache.get(base_name)
        if prev_pack is not pack:
            self._pack_cache[base_name] = pack
            if prev_pack:
                prev_pack.close()

    def generate_pack_data(
        self, have, want, shallow=None, progress=None,
        ofs_delta=True
    ) -> Tuple[int, Iterator[UnpackedObject]]:
        """Generate pack data objects for a set of wants/haves.

        Args:
          have: List of SHA1s of objects that should not be sent
          want: List of SHA1s of objects that should be sent
          shallow: Set of shallow commit SHA1s to skip
          ofs_delta: Whether OFS deltas can be included
          progress: Optional progress reporting method
        """
        missing_objects = MissingObjectFinder(
            self, haves=have, wants=want, shallow=shallow, progress=progress)
        remote_has = missing_objects.get_remote_has()
        object_ids = list(missing_objects)
        return len(object_ids), generate_unpacked_objects(
            cast(PackedObjectContainer, self),
            object_ids,
            progress=progress,
            ofs_delta=ofs_delta,
            other_haves=remote_has)

    def _clear_cached_packs(self):
        pack_cache = self._pack_cache
        self._pack_cache = {}
        while pack_cache:
            (name, pack) = pack_cache.popitem()
            pack.close()

    def _iter_cached_packs(self):
        return self._pack_cache.values()

    def _update_pack_cache(self):
        raise NotImplementedError(self._update_pack_cache)

    def close(self):
        self._clear_cached_packs()

    @property
    def packs(self):
        """List with pack objects."""
        return list(self._iter_cached_packs()) + list(self._update_pack_cache())

    def _iter_alternate_objects(self):
        """Iterate over the SHAs of all the objects in alternate stores."""
        for alternate in self.alternates:
            yield from alternate

    def _iter_loose_objects(self):
        """Iterate over the SHAs of all loose objects."""
        raise NotImplementedError(self._iter_loose_objects)

    def _get_loose_object(self, sha):
        raise NotImplementedError(self._get_loose_object)

    def _remove_loose_object(self, sha):
        raise NotImplementedError(self._remove_loose_object)

    def _remove_pack(self, name):
        raise NotImplementedError(self._remove_pack)

    def pack_loose_objects(self):
        """Pack loose objects.

        Returns: Number of objects packed
        """
        objects = set()
        for sha in self._iter_loose_objects():
            objects.add((self._get_loose_object(sha), None))
        self.add_objects(list(objects))
        for obj, path in objects:
            self._remove_loose_object(obj.id)
        return len(objects)

    def repack(self):
        """Repack the packs in this repository.

        Note that this implementation is fairly naive and currently keeps all
        objects in memory while it repacks.
        """
        loose_objects = set()
        for sha in self._iter_loose_objects():
            loose_objects.add(self._get_loose_object(sha))
        objects = {(obj, None) for obj in loose_objects}
        old_packs = {p.name(): p for p in self.packs}
        for name, pack in old_packs.items():
            objects.update((obj, None) for obj in pack.iterobjects())

        # The name of the consolidated pack might match the name of a
        # pre-existing pack. Take care not to remove the newly created
        # consolidated pack.

        consolidated = self.add_objects(objects)
        old_packs.pop(consolidated.name(), None)

        for obj in loose_objects:
            self._remove_loose_object(obj.id)
        for name, pack in old_packs.items():
            self._remove_pack(pack)
        self._update_pack_cache()
        return len(objects)

    def __iter__(self):
        """Iterate over the SHAs that are present in this store."""
        self._update_pack_cache()
        for pack in self._iter_cached_packs():
            try:
                yield from pack
            except PackFileDisappeared:
                pass
        yield from self._iter_loose_objects()
        yield from self._iter_alternate_objects()

    def contains_loose(self, sha):
        """Check if a particular object is present by SHA1 and is loose.

        This does not check alternates.
        """
        return self._get_loose_object(sha) is not None

    def get_raw(self, name):
        """Obtain the raw fulltext for an object.

        Args:
          name: sha for the object.
        Returns: tuple with numeric type and object contents.
        """
        if name == ZERO_SHA:
            raise KeyError(name)
        if len(name) == 40:
            sha = hex_to_sha(name)
            hexsha = name
        elif len(name) == 20:
            sha = name
            hexsha = None
        else:
            raise AssertionError("Invalid object name {!r}".format(name))
        for pack in self._iter_cached_packs():
            try:
                return pack.get_raw(sha)
            except (KeyError, PackFileDisappeared):
                pass
        if hexsha is None:
            hexsha = sha_to_hex(name)
        ret = self._get_loose_object(hexsha)
        if ret is not None:
            return ret.type_num, ret.as_raw_string()
        # Maybe something else has added a pack with the object
        # in the mean time?
        for pack in self._update_pack_cache():
            try:
                return pack.get_raw(sha)
            except KeyError:
                pass
        for alternate in self.alternates:
            try:
                return alternate.get_raw(hexsha)
            except KeyError:
                pass
        raise KeyError(hexsha)

    def iter_unpacked_subset(self, shas, *, include_comp=False, allow_missing: bool = False, convert_ofs_delta: bool = True) -> Iterator[ShaFile]:
        todo: Set[bytes] = set(shas)
        for p in self._iter_cached_packs():
            for unpacked in p.iter_unpacked_subset(todo, include_comp=include_comp, allow_missing=True, convert_ofs_delta=convert_ofs_delta):
                yield unpacked
                hexsha = sha_to_hex(unpacked.sha())
                todo.remove(hexsha)
        # Maybe something else has added a pack with the object
        # in the mean time?
        for p in self._update_pack_cache():
            for unpacked in p.iter_unpacked_subset(todo, include_comp=include_comp, allow_missing=True, convert_ofs_delta=convert_ofs_delta):
                yield unpacked
                hexsha = sha_to_hex(unpacked.sha())
                todo.remove(hexsha)
        for alternate in self.alternates:
            for unpacked in alternate.iter_unpacked_subset(todo, include_comp=include_comp, allow_missing=True, convert_ofs_delta=convert_ofs_delta):
                yield unpacked
                hexsha = sha_to_hex(unpacked.sha())
                todo.remove(hexsha)

    def iterobjects_subset(self, shas: Iterable[bytes], *, allow_missing: bool = False) -> Iterator[ShaFile]:
        todo: Set[bytes] = set(shas)
        for p in self._iter_cached_packs():
            for o in p.iterobjects_subset(todo, allow_missing=True):
                yield o
                todo.remove(o.id)
        # Maybe something else has added a pack with the object
        # in the mean time?
        for p in self._update_pack_cache():
            for o in p.iterobjects_subset(todo, allow_missing=True):
                yield o
                todo.remove(o.id)
        for alternate in self.alternates:
            for o in alternate.iterobjects_subset(todo, allow_missing=True):
                yield o
                todo.remove(o.id)
        for oid in todo:
            o = self._get_loose_object(oid)
            if o is not None:
                yield o
            elif not allow_missing:
                raise KeyError(oid)

    def get_unpacked_object(self, sha1: bytes, *, include_comp: bool = False) -> UnpackedObject:
        """Obtain the unpacked object.

        Args:
          sha1: sha for the object.
        """
        if sha1 == ZERO_SHA:
            raise KeyError(sha1)
        if len(sha1) == 40:
            sha = hex_to_sha(sha1)
            hexsha = sha1
        elif len(sha1) == 20:
            sha = sha1
            hexsha = None
        else:
            raise AssertionError("Invalid object sha1 {!r}".format(sha1))
        for pack in self._iter_cached_packs():
            try:
                return pack.get_unpacked_object(sha, include_comp=include_comp)
            except (KeyError, PackFileDisappeared):
                pass
        if hexsha is None:
            hexsha = sha_to_hex(sha1)
        # Maybe something else has added a pack with the object
        # in the mean time?
        for pack in self._update_pack_cache():
            try:
                return pack.get_unpacked_object(sha, include_comp=include_comp)
            except KeyError:
                pass
        for alternate in self.alternates:
            try:
                return alternate.get_unpacked_object(hexsha, include_comp=include_comp)
            except KeyError:
                pass
        raise KeyError(hexsha)

    def add_objects(
            self, objects: Sequence[Tuple[ShaFile, Optional[str]]],
            progress: Optional[Callable[[str], None]] = None) -> None:
        """Add a set of objects to this object store.

        Args:
          objects: Iterable over (object, path) tuples, should support
            __len__.
        Returns: Pack object of the objects written.
        """
        count = len(objects)
        record_iter = (full_unpacked_object(o) for (o, p) in objects)
        return self.add_pack_data(count, record_iter, progress=progress)


class DiskObjectStore(PackBasedObjectStore):
    """Git-style object store that exists on disk."""

    def __init__(self, path, loose_compression_level=-1, pack_compression_level=-1):
        """Open an object store.

        Args:
          path: Path of the object store.
          loose_compression_level: zlib compression level for loose objects
          pack_compression_level: zlib compression level for pack objects
        """
        super().__init__(
            pack_compression_level=pack_compression_level
        )
        self.path = path
        self.pack_dir = os.path.join(self.path, PACKDIR)
        self._alternates = None
        self.loose_compression_level = loose_compression_level
        self.pack_compression_level = pack_compression_level

    def __repr__(self):
        return "<{}({!r})>".format(self.__class__.__name__, self.path)

    @classmethod
    def from_config(cls, path, config):
        try:
            default_compression_level = int(
                config.get((b"core",), b"compression").decode()
            )
        except KeyError:
            default_compression_level = -1
        try:
            loose_compression_level = int(
                config.get((b"core",), b"looseCompression").decode()
            )
        except KeyError:
            loose_compression_level = default_compression_level
        try:
            pack_compression_level = int(
                config.get((b"core",), "packCompression").decode()
            )
        except KeyError:
            pack_compression_level = default_compression_level
        return cls(path, loose_compression_level, pack_compression_level)

    @property
    def alternates(self):
        if self._alternates is not None:
            return self._alternates
        self._alternates = []
        for path in self._read_alternate_paths():
            self._alternates.append(DiskObjectStore(path))
        return self._alternates

    def _read_alternate_paths(self):
        try:
            f = GitFile(os.path.join(self.path, INFODIR, "alternates"), "rb")
        except FileNotFoundError:
            return
        with f:
            for line in f.readlines():
                line = line.rstrip(b"\n")
                if line.startswith(b"#"):
                    continue
                if os.path.isabs(line):
                    yield os.fsdecode(line)
                else:
                    yield os.fsdecode(os.path.join(os.fsencode(self.path), line))

    def add_alternate_path(self, path):
        """Add an alternate path to this object store."""
        try:
            os.mkdir(os.path.join(self.path, INFODIR))
        except FileExistsError:
            pass
        alternates_path = os.path.join(self.path, INFODIR, "alternates")
        with GitFile(alternates_path, "wb") as f:
            try:
                orig_f = open(alternates_path, "rb")
            except FileNotFoundError:
                pass
            else:
                with orig_f:
                    f.write(orig_f.read())
            f.write(os.fsencode(path) + b"\n")

        if not os.path.isabs(path):
            path = os.path.join(self.path, path)
        self.alternates.append(DiskObjectStore(path))

    def _update_pack_cache(self):
        """Read and iterate over new pack files and cache them."""
        try:
            pack_dir_contents = os.listdir(self.pack_dir)
        except FileNotFoundError:
            self.close()
            return []
        pack_files = set()
        for name in pack_dir_contents:
            if name.startswith("pack-") and name.endswith(".pack"):
                # verify that idx exists first (otherwise the pack was not yet
                # fully written)
                idx_name = os.path.splitext(name)[0] + ".idx"
                if idx_name in pack_dir_contents:
                    pack_name = name[: -len(".pack")]
                    pack_files.add(pack_name)

        # Open newly appeared pack files
        new_packs = []
        for f in pack_files:
            if f not in self._pack_cache:
                pack = Pack(os.path.join(self.pack_dir, f))
                new_packs.append(pack)
                self._pack_cache[f] = pack
        # Remove disappeared pack files
        for f in set(self._pack_cache) - pack_files:
            self._pack_cache.pop(f).close()
        return new_packs

    def _get_shafile_path(self, sha):
        # Check from object dir
        return hex_to_filename(self.path, sha)

    def _iter_loose_objects(self):
        for base in os.listdir(self.path):
            if len(base) != 2:
                continue
            for rest in os.listdir(os.path.join(self.path, base)):
                sha = os.fsencode(base + rest)
                if not valid_hexsha(sha):
                    continue
                yield sha

    def _get_loose_object(self, sha):
        path = self._get_shafile_path(sha)
        try:
            return ShaFile.from_path(path)
        except FileNotFoundError:
            return None

    def _remove_loose_object(self, sha):
        os.remove(self._get_shafile_path(sha))

    def _remove_pack(self, pack):
        try:
            del self._pack_cache[os.path.basename(pack._basename)]
        except KeyError:
            pass
        pack.close()
        os.remove(pack.data.path)
        os.remove(pack.index.path)

    def _get_pack_basepath(self, entries):
        suffix = iter_sha1(entry[0] for entry in entries)
        # TODO: Handle self.pack_dir being bytes
        suffix = suffix.decode("ascii")
        return os.path.join(self.pack_dir, "pack-" + suffix)

    def _complete_pack(self, f, path, num_objects, indexer, progress=None):
        """Move a specific file containing a pack into the pack directory.

        Note: The file should be on the same file system as the
            packs directory.

        Args:
          f: Open file object for the pack.
          path: Path to the pack file.
          indexer: A PackIndexer for indexing the pack.
        """
        entries = []
        for i, entry in enumerate(indexer):
            if progress is not None:
                progress(("generating index: %d/%d\r" % (i, num_objects)).encode('ascii'))
            entries.append(entry)

        pack_sha, extra_entries = extend_pack(
            f, indexer.ext_refs(), get_raw=self.get_raw, compression_level=self.pack_compression_level,
            progress=progress)
        f.flush()
        try:
            fileno = f.fileno()
        except AttributeError:
            pass
        else:
            os.fsync(fileno)
        f.close()

        entries.extend(extra_entries)

        # Move the pack in.
        entries.sort()
        pack_base_name = self._get_pack_basepath(entries)

        for pack in self.packs:
            if pack._basename == pack_base_name:
                return pack

        target_pack_path = pack_base_name + ".pack"
        target_index_path = pack_base_name + ".idx"
        if sys.platform == "win32":
            # Windows might have the target pack file lingering. Attempt
            # removal, silently passing if the target does not exist.
            with suppress(FileNotFoundError):
                os.remove(target_pack_path)
        os.rename(path, target_pack_path)

        # Write the index.
        with GitFile(target_index_path, "wb", mask=PACK_MODE) as index_file:
            write_pack_index(index_file, entries, pack_sha)

        # Add the pack to the store and return it.
        final_pack = Pack(pack_base_name)
        final_pack.check_length_and_checksum()
        self._add_cached_pack(pack_base_name, final_pack)
        return final_pack

    def add_thin_pack(self, read_all, read_some, progress=None):
        """Add a new thin pack to this object store.

        Thin packs are packs that contain deltas with parents that exist
        outside the pack. They should never be placed in the object store
        directly, and always indexed and completed as they are copied.

        Args:
          read_all: Read function that blocks until the number of
            requested bytes are read.
          read_some: Read function that returns at least one byte, but may
            not return the number of bytes requested.
        Returns: A Pack object pointing at the now-completed thin pack in the
            objects/pack directory.
        """
        import tempfile

        fd, path = tempfile.mkstemp(dir=self.path, prefix="tmp_pack_")
        with os.fdopen(fd, "w+b") as f:
            os.chmod(path, PACK_MODE)
            indexer = PackIndexer(f, resolve_ext_ref=self.get_raw)
            copier = PackStreamCopier(read_all, read_some, f, delta_iter=indexer)
            copier.verify(progress=progress)
            return self._complete_pack(f, path, len(copier), indexer, progress=progress)

    def add_pack(self):
        """Add a new pack to this object store.

        Returns: Fileobject to write to, a commit function to
            call when the pack is finished and an abort
            function.
        """
        import tempfile

        fd, path = tempfile.mkstemp(dir=self.pack_dir, suffix=".pack")
        f = os.fdopen(fd, "w+b")
        os.chmod(path, PACK_MODE)

        def commit():
            if f.tell() > 0:
                f.seek(0)
                with PackData(path, f) as pd:
                    indexer = PackIndexer.for_pack_data(pd, resolve_ext_ref=self.get_raw)
                    return self._complete_pack(f, path, len(pd), indexer)
            else:
                f.close()
                os.remove(path)
                return None

        def abort():
            f.close()
            os.remove(path)

        return f, commit, abort

    def add_object(self, obj):
        """Add a single object to this object store.

        Args:
          obj: Object to add
        """
        path = self._get_shafile_path(obj.id)
        dir = os.path.dirname(path)
        try:
            os.mkdir(dir)
        except FileExistsError:
            pass
        if os.path.exists(path):
            return  # Already there, no need to write again
        with GitFile(path, "wb", mask=PACK_MODE) as f:
            f.write(
                obj.as_legacy_object(compression_level=self.loose_compression_level)
            )

    @classmethod
    def init(cls, path):
        try:
            os.mkdir(path)
        except FileExistsError:
            pass
        os.mkdir(os.path.join(path, "info"))
        os.mkdir(os.path.join(path, PACKDIR))
        return cls(path)


class MemoryObjectStore(BaseObjectStore):
    """Object store that keeps all objects in memory."""

    def __init__(self):
        super().__init__()
        self._data = {}
        self.pack_compression_level = -1

    def _to_hexsha(self, sha):
        if len(sha) == 40:
            return sha
        elif len(sha) == 20:
            return sha_to_hex(sha)
        else:
            raise ValueError("Invalid sha {!r}".format(sha))

    def contains_loose(self, sha):
        """Check if a particular object is present by SHA1 and is loose."""
        return self._to_hexsha(sha) in self._data

    def contains_packed(self, sha):
        """Check if a particular object is present by SHA1 and is packed."""
        return False

    def __iter__(self):
        """Iterate over the SHAs that are present in this store."""
        return iter(self._data.keys())

    @property
    def packs(self):
        """List with pack objects."""
        return []

    def get_raw(self, name: ObjectID):
        """Obtain the raw text for an object.

        Args:
          name: sha for the object.
        Returns: tuple with numeric type and object contents.
        """
        obj = self[self._to_hexsha(name)]
        return obj.type_num, obj.as_raw_string()

    def __getitem__(self, name: ObjectID):
        return self._data[self._to_hexsha(name)].copy()

    def __delitem__(self, name: ObjectID):
        """Delete an object from this store, for testing only."""
        del self._data[self._to_hexsha(name)]

    def add_object(self, obj):
        """Add a single object to this object store."""
        self._data[obj.id] = obj.copy()

    def add_objects(self, objects, progress=None):
        """Add a set of objects to this object store.

        Args:
          objects: Iterable over a list of (object, path) tuples
        """
        for obj, path in objects:
            self.add_object(obj)

    def add_pack(self):
        """Add a new pack to this object store.

        Because this object store doesn't support packs, we extract and add the
        individual objects.

        Returns: Fileobject to write to and a commit function to
            call when the pack is finished.
        """
        from tempfile import SpooledTemporaryFile
        f = SpooledTemporaryFile(
            max_size=PACK_SPOOL_FILE_MAX_SIZE, prefix='incoming-')

        def commit():
            size = f.tell()
            if size > 0:
                f.seek(0)
                p = PackData.from_file(f, size)
                for obj in PackInflater.for_pack_data(p, self.get_raw):
                    self.add_object(obj)
                p.close()
            else:
                f.close()

        def abort():
            f.close()

        return f, commit, abort

    def add_pack_data(self, count: int, unpacked_objects: Iterator[UnpackedObject], progress=None) -> None:
        """Add pack data to this object store.

        Args:
          count: Number of items to add
          pack_data: Iterator over pack data tuples
        """
        for unpacked_object in unpacked_objects:
            self.add_object(unpacked_object.sha_file())

    def add_thin_pack(self, read_all, read_some, progress=None):
        """Add a new thin pack to this object store.

        Thin packs are packs that contain deltas with parents that exist
        outside the pack. Because this object store doesn't support packs, we
        extract and add the individual objects.

        Args:
          read_all: Read function that blocks until the number of
            requested bytes are read.
          read_some: Read function that returns at least one byte, but may
            not return the number of bytes requested.
        """

        f, commit, abort = self.add_pack()
        try:
            copier = PackStreamCopier(read_all, read_some, f)
            copier.verify()
        except BaseException:
            abort()
            raise
        else:
            commit()


class ObjectIterator(Protocol):
    """Interface for iterating over objects."""

    def iterobjects(self) -> Iterator[ShaFile]:
        raise NotImplementedError(self.iterobjects)


def tree_lookup_path(lookup_obj, root_sha, path):
    """Look up an object in a Git tree.

    Args:
      lookup_obj: Callback for retrieving object by SHA1
      root_sha: SHA1 of the root tree
      path: Path to lookup
    Returns: A tuple of (mode, SHA) of the resulting path.
    """
    tree = lookup_obj(root_sha)
    if not isinstance(tree, Tree):
        raise NotTreeError(root_sha)
    return tree.lookup_path(lookup_obj, path)


def _collect_filetree_revs(obj_store: ObjectContainer, tree_sha: ObjectID, kset: Set[ObjectID]) -> None:
    """Collect SHA1s of files and directories for specified tree.

    Args:
      obj_store: Object store to get objects by SHA from
      tree_sha: tree reference to walk
      kset: set to fill with references to files and directories
    """
    filetree = obj_store[tree_sha]
    assert isinstance(filetree, Tree)
    for name, mode, sha in filetree.iteritems():
        if not S_ISGITLINK(mode) and sha not in kset:
            kset.add(sha)
            if stat.S_ISDIR(mode):
                _collect_filetree_revs(obj_store, sha, kset)


def _split_commits_and_tags(obj_store: ObjectContainer, lst, *, ignore_unknown=False) -> Tuple[Set[bytes], Set[bytes], Set[bytes]]:
    """Split object id list into three lists with commit, tag, and other SHAs.

    Commits referenced by tags are included into commits
    list as well. Only SHA1s known in this repository will get
    through, and unless ignore_unknown argument is True, KeyError
    is thrown for SHA1 missing in the repository

    Args:
      obj_store: Object store to get objects by SHA1 from
      lst: Collection of commit and tag SHAs
      ignore_unknown: True to skip SHA1 missing in the repository
        silently.
    Returns: A tuple of (commits, tags, others) SHA1s
    """
    commits: Set[bytes] = set()
    tags: Set[bytes] = set()
    others: Set[bytes] = set()
    for e in lst:
        try:
            o = obj_store[e]
        except KeyError:
            if not ignore_unknown:
                raise
        else:
            if isinstance(o, Commit):
                commits.add(e)
            elif isinstance(o, Tag):
                tags.add(e)
                tagged = o.object[1]
                c, t, os = _split_commits_and_tags(
                    obj_store, [tagged], ignore_unknown=ignore_unknown
                )
                commits |= c
                tags |= t
                others |= os
            else:
                others.add(e)
    return (commits, tags, others)


class MissingObjectFinder:
    """Find the objects missing from another object store.

    Args:
      object_store: Object store containing at least all objects to be
        sent
      haves: SHA1s of commits not to send (already present in target)
      wants: SHA1s of commits to send
      progress: Optional function to report progress to.
      get_tagged: Function that returns a dict of pointed-to sha -> tag
        sha for including tags.
      get_parents: Optional function for getting the parents of a commit.
      tagged: dict of pointed-to sha -> tag sha for including tags
    """

    def __init__(
        self,
        object_store,
        haves,
        wants,
        *,
        shallow=None,
        progress=None,
        get_tagged=None,
        get_parents=lambda commit: commit.parents,
    ):
        self.object_store = object_store
        if shallow is None:
            shallow = set()
        self._get_parents = get_parents
        # process Commits and Tags differently
        # Note, while haves may list commits/tags not available locally,
        # and such SHAs would get filtered out by _split_commits_and_tags,
        # wants shall list only known SHAs, and otherwise
        # _split_commits_and_tags fails with KeyError
        have_commits, have_tags, have_others = _split_commits_and_tags(
            object_store, haves, ignore_unknown=True
        )
        want_commits, want_tags, want_others = _split_commits_and_tags(
            object_store, wants, ignore_unknown=False
        )
        # all_ancestors is a set of commits that shall not be sent
        # (complete repository up to 'haves')
        all_ancestors = _collect_ancestors(
            object_store,
            have_commits, shallow=shallow, get_parents=self._get_parents
        )[0]
        # all_missing - complete set of commits between haves and wants
        # common - commits from all_ancestors we hit into while
        # traversing parent hierarchy of wants
        missing_commits, common_commits = _collect_ancestors(
            object_store,
            want_commits,
            all_ancestors,
            shallow=shallow,
            get_parents=self._get_parents,
        )
        self.remote_has: Set[bytes] = set()
        # Now, fill sha_done with commits and revisions of
        # files and directories known to be both locally
        # and on target. Thus these commits and files
        # won't get selected for fetch
        for h in common_commits:
            self.remote_has.add(h)
            cmt = object_store[h]
            _collect_filetree_revs(object_store, cmt.tree, self.remote_has)
        # record tags we have as visited, too
        for t in have_tags:
            self.remote_has.add(t)
        self.sha_done = set(self.remote_has)

        # in fact, what we 'want' is commits, tags, and others
        # we've found missing
        self.objects_to_send = {
            (w, None, Commit.type_num, False)
            for w in missing_commits}
        missing_tags = want_tags.difference(have_tags)
        self.objects_to_send.update(
            {(w, None, Tag.type_num, False)
             for w in missing_tags})
        missing_others = want_others.difference(have_others)
        self.objects_to_send.update(
            {(w, None, None, False)
             for w in missing_others})

        if progress is None:
            self.progress = lambda x: None
        else:
            self.progress = progress
        self._tagged = get_tagged and get_tagged() or {}

    def get_remote_has(self):
        return self.remote_has

    def add_todo(self, entries: Iterable[Tuple[ObjectID, Optional[bytes], Optional[int], bool]]):
        self.objects_to_send.update([e for e in entries if not e[0] in self.sha_done])

    def __next__(self) -> Tuple[bytes, PackHint]:
        while True:
            if not self.objects_to_send:
                self.progress(("counting objects: %d, done.\n" % len(self.sha_done)).encode("ascii"))
                raise StopIteration
            (sha, name, type_num, leaf) = self.objects_to_send.pop()
            if sha not in self.sha_done:
                break
        if not leaf:
            o = self.object_store[sha]
            if isinstance(o, Commit):
                self.add_todo([(o.tree, b"", Tree.type_num, False)])
            elif isinstance(o, Tree):
                self.add_todo(
                    [
                        (s, n, (Blob.type_num if stat.S_ISREG(m) else Tree.type_num),
                         not stat.S_ISDIR(m))
                        for n, m, s in o.iteritems()
                        if not S_ISGITLINK(m)
                    ]
                )
            elif isinstance(o, Tag):
                self.add_todo([(o.object[1], None, o.object[0].type_num, False)])
        if sha in self._tagged:
            self.add_todo([(self._tagged[sha], None, None, True)])
        self.sha_done.add(sha)
        if len(self.sha_done) % 1000 == 0:
            self.progress(("counting objects: %d\r" % len(self.sha_done)).encode("ascii"))
        return (sha, (type_num, name))

    def __iter__(self):
        return self


class ObjectStoreGraphWalker:
    """Graph walker that finds what commits are missing from an object store.

    Attributes:
      heads: Revisions without descendants in the local repo
      get_parents: Function to retrieve parents in the local repo
    """

    def __init__(self, local_heads, get_parents, shallow=None):
        """Create a new instance.

        Args:
          local_heads: Heads to start search with
          get_parents: Function for finding the parents of a SHA1.
        """
        self.heads = set(local_heads)
        self.get_parents = get_parents
        self.parents = {}
        if shallow is None:
            shallow = set()
        self.shallow = shallow

    def nak(self):
        """Nothing in common was found."""

    def ack(self, sha):
        """Ack that a revision and its ancestors are present in the source."""
        if len(sha) != 40:
            raise ValueError("unexpected sha %r received" % sha)
        ancestors = {sha}

        # stop if we run out of heads to remove
        while self.heads:
            for a in ancestors:
                if a in self.heads:
                    self.heads.remove(a)

            # collect all ancestors
            new_ancestors = set()
            for a in ancestors:
                ps = self.parents.get(a)
                if ps is not None:
                    new_ancestors.update(ps)
                self.parents[a] = None

            # no more ancestors; stop
            if not new_ancestors:
                break

            ancestors = new_ancestors

    def next(self):
        """Iterate over ancestors of heads in the target."""
        if self.heads:
            ret = self.heads.pop()
            try:
                ps = self.get_parents(ret)
            except KeyError:
                return None
            self.parents[ret] = ps
            self.heads.update([p for p in ps if p not in self.parents])
            return ret
        return None

    __next__ = next


def commit_tree_changes(object_store, tree, changes):
    """Commit a specified set of changes to a tree structure.

    This will apply a set of changes on top of an existing tree, storing new
    objects in object_store.

    changes are a list of tuples with (path, mode, object_sha).
    Paths can be both blobs and trees. See the mode and
    object sha to None deletes the path.

    This method works especially well if there are only a small
    number of changes to a big tree. For a large number of changes
    to a large tree, use e.g. commit_tree.

    Args:
      object_store: Object store to store new objects in
        and retrieve old ones from.
      tree: Original tree root
      changes: changes to apply
    Returns: New tree root object
    """
    # TODO(jelmer): Save up the objects and add them using .add_objects
    # rather than with individual calls to .add_object.
    nested_changes = {}
    for (path, new_mode, new_sha) in changes:
        try:
            (dirname, subpath) = path.split(b"/", 1)
        except ValueError:
            if new_sha is None:
                del tree[path]
            else:
                tree[path] = (new_mode, new_sha)
        else:
            nested_changes.setdefault(dirname, []).append((subpath, new_mode, new_sha))
    for name, subchanges in nested_changes.items():
        try:
            orig_subtree = object_store[tree[name][1]]
        except KeyError:
            orig_subtree = Tree()
        subtree = commit_tree_changes(object_store, orig_subtree, subchanges)
        if len(subtree) == 0:
            del tree[name]
        else:
            tree[name] = (stat.S_IFDIR, subtree.id)
    object_store.add_object(tree)
    return tree


class OverlayObjectStore(BaseObjectStore):
    """Object store that can overlay multiple object stores."""

    def __init__(self, bases, add_store=None):
        self.bases = bases
        self.add_store = add_store

    def add_object(self, object):
        if self.add_store is None:
            raise NotImplementedError(self.add_object)
        return self.add_store.add_object(object)

    def add_objects(self, objects, progress=None):
        if self.add_store is None:
            raise NotImplementedError(self.add_object)
        return self.add_store.add_objects(objects, progress)

    @property
    def packs(self):
        ret = []
        for b in self.bases:
            ret.extend(b.packs)
        return ret

    def __iter__(self):
        done = set()
        for b in self.bases:
            for o_id in b:
                if o_id not in done:
                    yield o_id
                    done.add(o_id)

    def iterobjects_subset(self, shas: Iterable[bytes], *, allow_missing: bool = False) -> Iterator[ShaFile]:
        todo = set(shas)
        for b in self.bases:
            for o in b.iterobjects_subset(todo, allow_missing=True):
                yield o
                todo.remove(o.id)
        if todo and not allow_missing:
            raise KeyError(o.id)

    def iter_unpacked_subset(self, shas: Iterable[bytes], *, include_comp=False, allow_missing: bool = False, convert_ofs_delta=True) -> Iterator[ShaFile]:
        todo = set(shas)
        for b in self.bases:
            for o in b.iter_unpacked_subset(todo, include_comp=include_comp, allow_missing=True, convert_ofs_delta=convert_ofs_delta):
                yield o
                todo.remove(o.id)
        if todo and not allow_missing:
            raise KeyError(o.id)

    def get_raw(self, sha_id):
        for b in self.bases:
            try:
                return b.get_raw(sha_id)
            except KeyError:
                pass
        raise KeyError(sha_id)

    def contains_packed(self, sha):
        for b in self.bases:
            if b.contains_packed(sha):
                return True
        return False

    def contains_loose(self, sha):
        for b in self.bases:
            if b.contains_loose(sha):
                return True
        return False


def read_packs_file(f):
    """Yield the packs listed in a packs file."""
    for line in f.read().splitlines():
        if not line:
            continue
        (kind, name) = line.split(b" ", 1)
        if kind != b"P":
            continue
        yield os.fsdecode(name)


class BucketBasedObjectStore(PackBasedObjectStore):
    """Object store implementation that uses a bucket store like S3 as backend.
    """

    def _iter_loose_objects(self):
        """Iterate over the SHAs of all loose objects."""
        return iter([])

    def _get_loose_object(self, sha):
        return None

    def _remove_loose_object(self, sha):
        # Doesn't exist..
        pass

    def _remove_pack(self, name):
        raise NotImplementedError(self._remove_pack)

    def _iter_pack_names(self):
        raise NotImplementedError(self._iter_pack_names)

    def _get_pack(self, name):
        raise NotImplementedError(self._get_pack)

    def _update_pack_cache(self):
        pack_files = set(self._iter_pack_names())

        # Open newly appeared pack files
        new_packs = []
        for f in pack_files:
            if f not in self._pack_cache:
                pack = self._get_pack(f)
                new_packs.append(pack)
                self._pack_cache[f] = pack
        # Remove disappeared pack files
        for f in set(self._pack_cache) - pack_files:
            self._pack_cache.pop(f).close()
        return new_packs

    def _upload_pack(self, basename, pack_file, index_file):
        raise NotImplementedError

    def add_pack(self):
        """Add a new pack to this object store.

        Returns: Fileobject to write to, a commit function to
            call when the pack is finished and an abort
            function.
        """
        import tempfile

        pf = tempfile.SpooledTemporaryFile(
            max_size=PACK_SPOOL_FILE_MAX_SIZE, prefix='incoming-')

        def commit():
            if pf.tell() == 0:
                pf.close()
                return None

            pf.seek(0)
            p = PackData(pf.name, pf)
            entries = p.sorted_entries()
            basename = iter_sha1(entry[0] for entry in entries).decode('ascii')
            idxf = tempfile.SpooledTemporaryFile(
                max_size=PACK_SPOOL_FILE_MAX_SIZE, prefix='incoming-')
            checksum = p.get_stored_checksum()
            write_pack_index(idxf, entries, checksum)
            idxf.seek(0)
            idx = load_pack_index_file(basename + '.idx', idxf)
            for pack in self.packs:
                if pack.get_stored_checksum() == p.get_stored_checksum():
                    p.close()
                    idx.close()
                    return pack
            pf.seek(0)
            idxf.seek(0)
            self._upload_pack(basename, pf, idxf)
            final_pack = Pack.from_objects(p, idx)
            self._add_cached_pack(basename, final_pack)
            return final_pack

        return pf, commit, pf.close


def _collect_ancestors(
    store: ObjectContainer,
    heads,
    common=frozenset(),
    shallow=frozenset(),
    get_parents=lambda commit: commit.parents,
):
    """Collect all ancestors of heads up to (excluding) those in common.

    Args:
      heads: commits to start from
      common: commits to end at, or empty set to walk repository
        completely
      get_parents: Optional function for getting the parents of a
        commit.
    Returns: a tuple (A, B) where A - all commits reachable
        from heads but not present in common, B - common (shared) elements
        that are directly reachable from heads
    """
    bases = set()
    commits = set()
    queue = []
    queue.extend(heads)
    while queue:
        e = queue.pop(0)
        if e in common:
            bases.add(e)
        elif e not in commits:
            commits.add(e)
            if e in shallow:
                continue
            cmt = store[e]
            queue.extend(get_parents(cmt))
    return (commits, bases)


def iter_tree_contents(
        store: ObjectContainer, tree_id: Optional[ObjectID], *, include_trees: bool = False):
    """Iterate the contents of a tree and all subtrees.

    Iteration is depth-first pre-order, as in e.g. os.walk.

    Args:
      tree_id: SHA1 of the tree.
      include_trees: If True, include tree objects in the iteration.
    Returns: Iterator over TreeEntry namedtuples for all the objects in a
        tree.
    """
    if tree_id is None:
        return
    # This could be fairly easily generalized to >2 trees if we find a use
    # case.
    todo = [TreeEntry(b"", stat.S_IFDIR, tree_id)]
    while todo:
        entry = todo.pop()
        if stat.S_ISDIR(entry.mode):
            extra = []
            tree = store[entry.sha]
            assert isinstance(tree, Tree)
            for subentry in tree.iteritems(name_order=True):
                extra.append(subentry.in_path(entry.path))
            todo.extend(reversed(extra))
        if not stat.S_ISDIR(entry.mode) or include_trees:
            yield entry


def peel_sha(store: ObjectContainer, sha: bytes) -> Tuple[ShaFile, ShaFile]:
    """Peel all tags from a SHA.

    Args:
      sha: The object SHA to peel.
    Returns: The fully-peeled SHA1 of a tag object, after peeling all
        intermediate tags; if the original ref does not point to a tag,
        this will equal the original SHA1.
    """
    unpeeled = obj = store[sha]
    obj_class = object_class(obj.type_name)
    while obj_class is Tag:
        assert isinstance(obj, Tag)
        obj_class, sha = obj.object
        obj = store[sha]
    return unpeeled, obj
