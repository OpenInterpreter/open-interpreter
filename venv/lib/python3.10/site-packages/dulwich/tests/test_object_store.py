# test_object_store.py -- tests for object_store.py
# Copyright (C) 2008 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for the object store interface."""


import os
import shutil
import stat
import sys
import tempfile
from contextlib import closing
from io import BytesIO
from unittest import skipUnless

from dulwich.tests import TestCase

from ..errors import NotTreeError
from ..index import commit_tree
from ..object_store import (DiskObjectStore, MemoryObjectStore,
                            ObjectStoreGraphWalker, OverlayObjectStore,
                            commit_tree_changes, iter_tree_contents, peel_sha,
                            read_packs_file, tree_lookup_path)
from ..objects import (S_IFGITLINK, Blob, EmptyFileException,
                       SubmoduleEncountered, Tree, TreeEntry, sha_to_hex)
from ..pack import REF_DELTA, write_pack_objects
from ..protocol import DEPTH_INFINITE
from .utils import build_pack, make_object, make_tag

try:
    from unittest.mock import patch
except ImportError:
    patch = None  # type: ignore


testobject = make_object(Blob, data=b"yummy data")


class ObjectStoreTests:
    def test_determine_wants_all(self):
        self.assertEqual(
            [b"1" * 40],
            self.store.determine_wants_all({b"refs/heads/foo": b"1" * 40}),
        )

    def test_determine_wants_all_zero(self):
        self.assertEqual(
            [], self.store.determine_wants_all({b"refs/heads/foo": b"0" * 40})
        )

    @skipUnless(patch, "Required mock.patch")
    def test_determine_wants_all_depth(self):
        self.store.add_object(testobject)
        refs = {b"refs/heads/foo": testobject.id}
        with patch.object(self.store, "_get_depth", return_value=1) as m:
            self.assertEqual(
                [], self.store.determine_wants_all(refs, depth=0)
            )
            self.assertEqual(
                [testobject.id],
                self.store.determine_wants_all(refs, depth=DEPTH_INFINITE),
            )
            m.assert_not_called()

            self.assertEqual(
                [], self.store.determine_wants_all(refs, depth=1)
            )
            m.assert_called_with(testobject.id)
            self.assertEqual(
                [testobject.id], self.store.determine_wants_all(refs, depth=2)
            )

    def test_get_depth(self):
        self.assertEqual(
            0, self.store._get_depth(testobject.id)
        )

        self.store.add_object(testobject)
        self.assertEqual(
            1, self.store._get_depth(testobject.id, get_parents=lambda x: [])
        )

        parent = make_object(Blob, data=b"parent data")
        self.store.add_object(parent)
        self.assertEqual(
            2,
            self.store._get_depth(
                testobject.id,
                get_parents=lambda x: [parent.id] if x == testobject else [],
            ),
        )

    def test_iter(self):
        self.assertEqual([], list(self.store))

    def test_get_nonexistant(self):
        self.assertRaises(KeyError, lambda: self.store[b"a" * 40])

    def test_contains_nonexistant(self):
        self.assertNotIn(b"a" * 40, self.store)

    def test_add_objects_empty(self):
        self.store.add_objects([])

    def test_add_commit(self):
        # TODO: Argh, no way to construct Git commit objects without
        # access to a serialized form.
        self.store.add_objects([])

    def test_store_resilience(self):
        """Test if updating an existing stored object doesn't erase the
        object from the store.
        """
        test_object = make_object(Blob, data=b"data")

        self.store.add_object(test_object)
        test_object_id = test_object.id
        test_object.data = test_object.data + b"update"
        stored_test_object = self.store[test_object_id]

        self.assertNotEqual(test_object.id, stored_test_object.id)
        self.assertEqual(stored_test_object.id, test_object_id)

    def test_add_object(self):
        self.store.add_object(testobject)
        self.assertEqual({testobject.id}, set(self.store))
        self.assertIn(testobject.id, self.store)
        r = self.store[testobject.id]
        self.assertEqual(r, testobject)

    def test_add_objects(self):
        data = [(testobject, "mypath")]
        self.store.add_objects(data)
        self.assertEqual({testobject.id}, set(self.store))
        self.assertIn(testobject.id, self.store)
        r = self.store[testobject.id]
        self.assertEqual(r, testobject)

    def test_tree_changes(self):
        blob_a1 = make_object(Blob, data=b"a1")
        blob_a2 = make_object(Blob, data=b"a2")
        blob_b = make_object(Blob, data=b"b")
        for blob in [blob_a1, blob_a2, blob_b]:
            self.store.add_object(blob)

        blobs_1 = [(b"a", blob_a1.id, 0o100644), (b"b", blob_b.id, 0o100644)]
        tree1_id = commit_tree(self.store, blobs_1)
        blobs_2 = [(b"a", blob_a2.id, 0o100644), (b"b", blob_b.id, 0o100644)]
        tree2_id = commit_tree(self.store, blobs_2)
        change_a = (
            (b"a", b"a"),
            (0o100644, 0o100644),
            (blob_a1.id, blob_a2.id),
        )
        self.assertEqual([change_a], list(self.store.tree_changes(tree1_id, tree2_id)))
        self.assertEqual(
            [
                change_a,
                ((b"b", b"b"), (0o100644, 0o100644), (blob_b.id, blob_b.id)),
            ],
            list(self.store.tree_changes(tree1_id, tree2_id, want_unchanged=True)),
        )

    def test_iter_tree_contents(self):
        blob_a = make_object(Blob, data=b"a")
        blob_b = make_object(Blob, data=b"b")
        blob_c = make_object(Blob, data=b"c")
        for blob in [blob_a, blob_b, blob_c]:
            self.store.add_object(blob)

        blobs = [
            (b"a", blob_a.id, 0o100644),
            (b"ad/b", blob_b.id, 0o100644),
            (b"ad/bd/c", blob_c.id, 0o100755),
            (b"ad/c", blob_c.id, 0o100644),
            (b"c", blob_c.id, 0o100644),
        ]
        tree_id = commit_tree(self.store, blobs)
        self.assertEqual(
            [TreeEntry(p, m, h) for (p, h, m) in blobs],
            list(iter_tree_contents(self.store, tree_id)),
        )
        self.assertEqual([], list(iter_tree_contents(self.store, None)))

    def test_iter_tree_contents_include_trees(self):
        blob_a = make_object(Blob, data=b"a")
        blob_b = make_object(Blob, data=b"b")
        blob_c = make_object(Blob, data=b"c")
        for blob in [blob_a, blob_b, blob_c]:
            self.store.add_object(blob)

        blobs = [
            (b"a", blob_a.id, 0o100644),
            (b"ad/b", blob_b.id, 0o100644),
            (b"ad/bd/c", blob_c.id, 0o100755),
        ]
        tree_id = commit_tree(self.store, blobs)
        tree = self.store[tree_id]
        tree_ad = self.store[tree[b"ad"][1]]
        tree_bd = self.store[tree_ad[b"bd"][1]]

        expected = [
            TreeEntry(b"", 0o040000, tree_id),
            TreeEntry(b"a", 0o100644, blob_a.id),
            TreeEntry(b"ad", 0o040000, tree_ad.id),
            TreeEntry(b"ad/b", 0o100644, blob_b.id),
            TreeEntry(b"ad/bd", 0o040000, tree_bd.id),
            TreeEntry(b"ad/bd/c", 0o100755, blob_c.id),
        ]
        actual = iter_tree_contents(self.store, tree_id, include_trees=True)
        self.assertEqual(expected, list(actual))

    def make_tag(self, name, obj):
        tag = make_tag(obj, name=name)
        self.store.add_object(tag)
        return tag

    def test_peel_sha(self):
        self.store.add_object(testobject)
        tag1 = self.make_tag(b"1", testobject)
        tag2 = self.make_tag(b"2", testobject)
        tag3 = self.make_tag(b"3", testobject)
        for obj in [testobject, tag1, tag2, tag3]:
            self.assertEqual((obj, testobject), peel_sha(self.store, obj.id))

    def test_get_raw(self):
        self.store.add_object(testobject)
        self.assertEqual(
            (Blob.type_num, b"yummy data"), self.store.get_raw(testobject.id)
        )

    def test_close(self):
        # For now, just check that close doesn't barf.
        self.store.add_object(testobject)
        self.store.close()


class OverlayObjectStoreTests(ObjectStoreTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.bases = [MemoryObjectStore(), MemoryObjectStore()]
        self.store = OverlayObjectStore(self.bases, self.bases[0])


class MemoryObjectStoreTests(ObjectStoreTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.store = MemoryObjectStore()

    def test_add_pack(self):
        o = MemoryObjectStore()
        f, commit, abort = o.add_pack()
        try:
            b = make_object(Blob, data=b"more yummy data")
            write_pack_objects(f.write, [(b, None)])
        except BaseException:
            abort()
            raise
        else:
            commit()

    def test_add_pack_emtpy(self):
        o = MemoryObjectStore()
        f, commit, abort = o.add_pack()
        commit()

    def test_add_thin_pack(self):
        o = MemoryObjectStore()
        blob = make_object(Blob, data=b"yummy data")
        o.add_object(blob)

        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (blob.id, b"more yummy data")),
            ],
            store=o,
        )
        o.add_thin_pack(f.read, None)
        packed_blob_sha = sha_to_hex(entries[0][3])
        self.assertEqual(
            (Blob.type_num, b"more yummy data"), o.get_raw(packed_blob_sha)
        )

    def test_add_thin_pack_empty(self):
        o = MemoryObjectStore()

        f = BytesIO()
        entries = build_pack(f, [], store=o)
        self.assertEqual([], entries)
        o.add_thin_pack(f.read, None)


class PackBasedObjectStoreTests(ObjectStoreTests):
    def tearDown(self):
        for pack in self.store.packs:
            pack.close()

    def test_empty_packs(self):
        self.assertEqual([], list(self.store.packs))

    def test_pack_loose_objects(self):
        b1 = make_object(Blob, data=b"yummy data")
        self.store.add_object(b1)
        b2 = make_object(Blob, data=b"more yummy data")
        self.store.add_object(b2)
        b3 = make_object(Blob, data=b"even more yummy data")
        b4 = make_object(Blob, data=b"and more yummy data")
        self.store.add_objects([(b3, None), (b4, None)])
        self.assertEqual({b1.id, b2.id, b3.id, b4.id}, set(self.store))
        self.assertEqual(1, len(self.store.packs))
        self.assertEqual(2, self.store.pack_loose_objects())
        self.assertNotEqual([], list(self.store.packs))
        self.assertEqual(0, self.store.pack_loose_objects())

    def test_repack(self):
        b1 = make_object(Blob, data=b"yummy data")
        self.store.add_object(b1)
        b2 = make_object(Blob, data=b"more yummy data")
        self.store.add_object(b2)
        b3 = make_object(Blob, data=b"even more yummy data")
        b4 = make_object(Blob, data=b"and more yummy data")
        self.store.add_objects([(b3, None), (b4, None)])
        b5 = make_object(Blob, data=b"and more data")
        b6 = make_object(Blob, data=b"and some more data")
        self.store.add_objects([(b5, None), (b6, None)])
        self.assertEqual({b1.id, b2.id, b3.id, b4.id, b5.id, b6.id}, set(self.store))
        self.assertEqual(2, len(self.store.packs))
        self.assertEqual(6, self.store.repack())
        self.assertEqual(1, len(self.store.packs))
        self.assertEqual(0, self.store.pack_loose_objects())

    def test_repack_existing(self):
        b1 = make_object(Blob, data=b"yummy data")
        self.store.add_object(b1)
        b2 = make_object(Blob, data=b"more yummy data")
        self.store.add_object(b2)
        self.store.add_objects([(b1, None), (b2, None)])
        self.store.add_objects([(b2, None)])
        self.assertEqual({b1.id, b2.id}, set(self.store))
        self.assertEqual(2, len(self.store.packs))
        self.assertEqual(2, self.store.repack())
        self.assertEqual(1, len(self.store.packs))
        self.assertEqual(0, self.store.pack_loose_objects())

        self.assertEqual({b1.id, b2.id}, set(self.store))
        self.assertEqual(1, len(self.store.packs))
        self.assertEqual(2, self.store.repack())
        self.assertEqual(1, len(self.store.packs))
        self.assertEqual(0, self.store.pack_loose_objects())


class DiskObjectStoreTests(PackBasedObjectStoreTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.store_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store_dir)
        self.store = DiskObjectStore.init(self.store_dir)

    def tearDown(self):
        TestCase.tearDown(self)
        PackBasedObjectStoreTests.tearDown(self)

    def test_loose_compression_level(self):
        alternate_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, alternate_dir)
        alternate_store = DiskObjectStore(alternate_dir, loose_compression_level=6)
        b2 = make_object(Blob, data=b"yummy data")
        alternate_store.add_object(b2)

    def test_alternates(self):
        alternate_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, alternate_dir)
        alternate_store = DiskObjectStore(alternate_dir)
        b2 = make_object(Blob, data=b"yummy data")
        alternate_store.add_object(b2)
        store = DiskObjectStore(self.store_dir)
        self.assertRaises(KeyError, store.__getitem__, b2.id)
        store.add_alternate_path(alternate_dir)
        self.assertIn(b2.id, store)
        self.assertEqual(b2, store[b2.id])

    def test_read_alternate_paths(self):
        store = DiskObjectStore(self.store_dir)

        abs_path = os.path.abspath(os.path.normpath("/abspath"))
        # ensures in particular existence of the alternates file
        store.add_alternate_path(abs_path)
        self.assertEqual(set(store._read_alternate_paths()), {abs_path})

        store.add_alternate_path("relative-path")
        self.assertIn(
            os.path.join(store.path, "relative-path"),
            set(store._read_alternate_paths()),
        )

        # arguably, add_alternate_path() could strip comments.
        # Meanwhile it's more convenient to use it than to import INFODIR
        store.add_alternate_path("# comment")
        for alt_path in store._read_alternate_paths():
            self.assertNotIn("#", alt_path)

    def test_file_modes(self):
        self.store.add_object(testobject)
        path = self.store._get_shafile_path(testobject.id)
        mode = os.stat(path).st_mode

        packmode = "0o100444" if sys.platform != "win32" else "0o100666"
        self.assertEqual(oct(mode), packmode)

    def test_corrupted_object_raise_exception(self):
        """Corrupted sha1 disk file should raise specific exception"""
        self.store.add_object(testobject)
        self.assertEqual(
            (Blob.type_num, b"yummy data"), self.store.get_raw(testobject.id)
        )
        self.assertTrue(self.store.contains_loose(testobject.id))
        self.assertIsNotNone(self.store._get_loose_object(testobject.id))

        path = self.store._get_shafile_path(testobject.id)
        old_mode = os.stat(path).st_mode
        os.chmod(path, 0o600)
        with open(path, "wb") as f:  # corrupt the file
            f.write(b"")
        os.chmod(path, old_mode)

        expected_error_msg = "Corrupted empty file detected"
        try:
            self.store.contains_loose(testobject.id)
        except EmptyFileException as e:
            self.assertEqual(str(e), expected_error_msg)

        try:
            self.store._get_loose_object(testobject.id)
        except EmptyFileException as e:
            self.assertEqual(str(e), expected_error_msg)

        # this does not change iteration on loose objects though
        self.assertEqual([testobject.id], list(self.store._iter_loose_objects()))

    def test_tempfile_in_loose_store(self):
        self.store.add_object(testobject)
        self.assertEqual([testobject.id], list(self.store._iter_loose_objects()))

        # add temporary files to the loose store
        for i in range(256):
            dirname = os.path.join(self.store_dir, "%02x" % i)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            fd, n = tempfile.mkstemp(prefix="tmp_obj_", dir=dirname)
            os.close(fd)

        self.assertEqual([testobject.id], list(self.store._iter_loose_objects()))

    def test_add_alternate_path(self):
        store = DiskObjectStore(self.store_dir)
        self.assertEqual([], list(store._read_alternate_paths()))
        store.add_alternate_path("/foo/path")
        self.assertEqual(["/foo/path"], list(store._read_alternate_paths()))
        store.add_alternate_path("/bar/path")
        self.assertEqual(
            ["/foo/path", "/bar/path"], list(store._read_alternate_paths())
        )

    def test_rel_alternative_path(self):
        alternate_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, alternate_dir)
        alternate_store = DiskObjectStore(alternate_dir)
        b2 = make_object(Blob, data=b"yummy data")
        alternate_store.add_object(b2)
        store = DiskObjectStore(self.store_dir)
        self.assertRaises(KeyError, store.__getitem__, b2.id)
        store.add_alternate_path(os.path.relpath(alternate_dir, self.store_dir))
        self.assertEqual(list(alternate_store), list(store.alternates[0]))
        self.assertIn(b2.id, store)
        self.assertEqual(b2, store[b2.id])

    def test_pack_dir(self):
        o = DiskObjectStore(self.store_dir)
        self.assertEqual(os.path.join(self.store_dir, "pack"), o.pack_dir)

    def test_add_pack(self):
        o = DiskObjectStore(self.store_dir)
        self.addCleanup(o.close)
        f, commit, abort = o.add_pack()
        try:
            b = make_object(Blob, data=b"more yummy data")
            write_pack_objects(f.write, [(b, None)])
        except BaseException:
            abort()
            raise
        else:
            commit()

    def test_add_thin_pack(self):
        o = DiskObjectStore(self.store_dir)
        try:
            blob = make_object(Blob, data=b"yummy data")
            o.add_object(blob)

            f = BytesIO()
            entries = build_pack(
                f,
                [
                    (REF_DELTA, (blob.id, b"more yummy data")),
                ],
                store=o,
            )

            with o.add_thin_pack(f.read, None) as pack:
                packed_blob_sha = sha_to_hex(entries[0][3])
                pack.check_length_and_checksum()
                self.assertEqual(sorted([blob.id, packed_blob_sha]), list(pack))
                self.assertTrue(o.contains_packed(packed_blob_sha))
                self.assertTrue(o.contains_packed(blob.id))
                self.assertEqual(
                    (Blob.type_num, b"more yummy data"),
                    o.get_raw(packed_blob_sha),
                )
        finally:
            o.close()

    def test_add_thin_pack_empty(self):
        with closing(DiskObjectStore(self.store_dir)) as o:
            f = BytesIO()
            entries = build_pack(f, [], store=o)
            self.assertEqual([], entries)
            o.add_thin_pack(f.read, None)


class TreeLookupPathTests(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.store = MemoryObjectStore()
        blob_a = make_object(Blob, data=b"a")
        blob_b = make_object(Blob, data=b"b")
        blob_c = make_object(Blob, data=b"c")
        for blob in [blob_a, blob_b, blob_c]:
            self.store.add_object(blob)

        blobs = [
            (b"a", blob_a.id, 0o100644),
            (b"ad/b", blob_b.id, 0o100644),
            (b"ad/bd/c", blob_c.id, 0o100755),
            (b"ad/c", blob_c.id, 0o100644),
            (b"c", blob_c.id, 0o100644),
            (b"d", blob_c.id, S_IFGITLINK),
        ]
        self.tree_id = commit_tree(self.store, blobs)

    def get_object(self, sha):
        return self.store[sha]

    def test_lookup_blob(self):
        o_id = tree_lookup_path(self.get_object, self.tree_id, b"a")[1]
        self.assertIsInstance(self.store[o_id], Blob)

    def test_lookup_tree(self):
        o_id = tree_lookup_path(self.get_object, self.tree_id, b"ad")[1]
        self.assertIsInstance(self.store[o_id], Tree)
        o_id = tree_lookup_path(self.get_object, self.tree_id, b"ad/bd")[1]
        self.assertIsInstance(self.store[o_id], Tree)
        o_id = tree_lookup_path(self.get_object, self.tree_id, b"ad/bd/")[1]
        self.assertIsInstance(self.store[o_id], Tree)

    def test_lookup_submodule(self):
        tree_lookup_path(self.get_object, self.tree_id, b"d")[1]
        self.assertRaises(
            SubmoduleEncountered, tree_lookup_path, self.get_object,
            self.tree_id, b"d/a")

    def test_lookup_nonexistent(self):
        self.assertRaises(
            KeyError, tree_lookup_path, self.get_object, self.tree_id, b"j"
        )

    def test_lookup_not_tree(self):
        self.assertRaises(
            NotTreeError,
            tree_lookup_path,
            self.get_object,
            self.tree_id,
            b"ad/b/j",
        )


class ObjectStoreGraphWalkerTests(TestCase):
    def get_walker(self, heads, parent_map):
        new_parent_map = {
            k * 40: [(p * 40) for p in ps] for (k, ps) in parent_map.items()
        }
        return ObjectStoreGraphWalker(
            [x * 40 for x in heads], new_parent_map.__getitem__
        )

    def test_ack_invalid_value(self):
        gw = self.get_walker([], {})
        self.assertRaises(ValueError, gw.ack, "tooshort")

    def test_empty(self):
        gw = self.get_walker([], {})
        self.assertIs(None, next(gw))
        gw.ack(b"a" * 40)
        self.assertIs(None, next(gw))

    def test_descends(self):
        gw = self.get_walker([b"a"], {b"a": [b"b"], b"b": []})
        self.assertEqual(b"a" * 40, next(gw))
        self.assertEqual(b"b" * 40, next(gw))

    def test_present(self):
        gw = self.get_walker([b"a"], {b"a": [b"b"], b"b": []})
        gw.ack(b"a" * 40)
        self.assertIs(None, next(gw))

    def test_parent_present(self):
        gw = self.get_walker([b"a"], {b"a": [b"b"], b"b": []})
        self.assertEqual(b"a" * 40, next(gw))
        gw.ack(b"a" * 40)
        self.assertIs(None, next(gw))

    def test_child_ack_later(self):
        gw = self.get_walker([b"a"], {b"a": [b"b"], b"b": [b"c"], b"c": []})
        self.assertEqual(b"a" * 40, next(gw))
        self.assertEqual(b"b" * 40, next(gw))
        gw.ack(b"a" * 40)
        self.assertIs(None, next(gw))

    def test_only_once(self):
        # a  b
        # |  |
        # c  d
        # \ /
        #  e
        gw = self.get_walker(
            [b"a", b"b"],
            {
                b"a": [b"c"],
                b"b": [b"d"],
                b"c": [b"e"],
                b"d": [b"e"],
                b"e": [],
            },
        )
        walk = []
        acked = False
        walk.append(next(gw))
        walk.append(next(gw))
        # A branch (a, c) or (b, d) may be done after 2 steps or 3 depending on
        # the order walked: 3-step walks include (a, b, c) and (b, a, d), etc.
        if walk == [b"a" * 40, b"c" * 40] or walk == [b"b" * 40, b"d" * 40]:
            gw.ack(walk[0])
            acked = True

        walk.append(next(gw))
        if not acked and walk[2] == b"c" * 40:
            gw.ack(b"a" * 40)
        elif not acked and walk[2] == b"d" * 40:
            gw.ack(b"b" * 40)
        walk.append(next(gw))
        self.assertIs(None, next(gw))

        self.assertEqual([b"a" * 40, b"b" * 40, b"c" * 40, b"d" * 40], sorted(walk))
        self.assertLess(walk.index(b"a" * 40), walk.index(b"c" * 40))
        self.assertLess(walk.index(b"b" * 40), walk.index(b"d" * 40))


class CommitTreeChangesTests(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.blob_a = make_object(Blob, data=b"a")
        self.blob_b = make_object(Blob, data=b"b")
        self.blob_c = make_object(Blob, data=b"c")
        for blob in [self.blob_a, self.blob_b, self.blob_c]:
            self.store.add_object(blob)

        blobs = [
            (b"a", self.blob_a.id, 0o100644),
            (b"ad/b", self.blob_b.id, 0o100644),
            (b"ad/bd/c", self.blob_c.id, 0o100755),
            (b"ad/c", self.blob_c.id, 0o100644),
            (b"c", self.blob_c.id, 0o100644),
        ]
        self.tree_id = commit_tree(self.store, blobs)

    def test_no_changes(self):
        self.assertEqual(
            self.store[self.tree_id],
            commit_tree_changes(self.store, self.store[self.tree_id], []),
        )

    def test_add_blob(self):
        blob_d = make_object(Blob, data=b"d")
        new_tree = commit_tree_changes(
            self.store, self.store[self.tree_id], [(b"d", 0o100644, blob_d.id)]
        )
        self.assertEqual(
            new_tree[b"d"],
            (33188, b"c59d9b6344f1af00e504ba698129f07a34bbed8d"),
        )

    def test_add_blob_in_dir(self):
        blob_d = make_object(Blob, data=b"d")
        new_tree = commit_tree_changes(
            self.store,
            self.store[self.tree_id],
            [(b"e/f/d", 0o100644, blob_d.id)],
        )
        self.assertEqual(
            new_tree.items(),
            [
                TreeEntry(path=b"a", mode=stat.S_IFREG | 0o100644, sha=self.blob_a.id),
                TreeEntry(
                    path=b"ad",
                    mode=stat.S_IFDIR,
                    sha=b"0e2ce2cd7725ff4817791be31ccd6e627e801f4a",
                ),
                TreeEntry(path=b"c", mode=stat.S_IFREG | 0o100644, sha=self.blob_c.id),
                TreeEntry(
                    path=b"e",
                    mode=stat.S_IFDIR,
                    sha=b"6ab344e288724ac2fb38704728b8896e367ed108",
                ),
            ],
        )
        e_tree = self.store[new_tree[b"e"][1]]
        self.assertEqual(
            e_tree.items(),
            [
                TreeEntry(
                    path=b"f",
                    mode=stat.S_IFDIR,
                    sha=b"24d2c94d8af232b15a0978c006bf61ef4479a0a5",
                )
            ],
        )
        f_tree = self.store[e_tree[b"f"][1]]
        self.assertEqual(
            f_tree.items(),
            [TreeEntry(path=b"d", mode=stat.S_IFREG | 0o100644, sha=blob_d.id)],
        )

    def test_delete_blob(self):
        new_tree = commit_tree_changes(
            self.store, self.store[self.tree_id], [(b"ad/bd/c", None, None)]
        )
        self.assertEqual(set(new_tree), {b"a", b"ad", b"c"})
        ad_tree = self.store[new_tree[b"ad"][1]]
        self.assertEqual(set(ad_tree), {b"b", b"c"})


class TestReadPacksFile(TestCase):
    def test_read_packs(self):
        self.assertEqual(
            ["pack-1.pack"],
            list(
                read_packs_file(
                    BytesIO(
                        b"""P pack-1.pack
"""
                    )
                )
            ),
        )
