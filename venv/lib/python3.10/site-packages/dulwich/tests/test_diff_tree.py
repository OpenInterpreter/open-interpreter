# test_diff_tree.py -- Tests for file and tree diff utilities.
# Copyright (C) 2010 Google, Inc.
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

"""Tests for file and tree diff utilities."""

from itertools import permutations

from dulwich.tests import TestCase

from ..diff_tree import (CHANGE_COPY, CHANGE_MODIFY, CHANGE_RENAME,
                         CHANGE_UNCHANGED, RenameDetector, TreeChange,
                         _count_blocks, _count_blocks_py, _is_tree,
                         _is_tree_py, _merge_entries, _merge_entries_py,
                         _similarity_score, _tree_change_key, tree_changes,
                         tree_changes_for_merge)
from ..index import commit_tree
from ..object_store import MemoryObjectStore
from ..objects import Blob, ShaFile, Tree, TreeEntry
from .utils import F, ext_functest_builder, functest_builder, make_object


class DiffTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.empty_tree = self.commit_tree([])

    def commit_tree(self, entries):
        commit_blobs = []
        for entry in entries:
            if len(entry) == 2:
                path, obj = entry
                mode = F
            else:
                path, obj, mode = entry
            if isinstance(obj, Blob):
                self.store.add_object(obj)
                sha = obj.id
            else:
                sha = obj
            commit_blobs.append((path, sha, mode))
        return self.store[commit_tree(self.store, commit_blobs)]


class TreeChangesTest(DiffTestCase):
    def setUp(self):
        super().setUp()
        self.detector = RenameDetector(self.store)

    def assertMergeFails(self, merge_entries, name, mode, sha):
        t = Tree()
        t[name] = (mode, sha)
        self.assertRaises((TypeError, ValueError), merge_entries, "", t, t)

    def _do_test_merge_entries(self, merge_entries):
        blob_a1 = make_object(Blob, data=b"a1")
        blob_a2 = make_object(Blob, data=b"a2")
        blob_b1 = make_object(Blob, data=b"b1")
        blob_c2 = make_object(Blob, data=b"c2")
        tree1 = self.commit_tree([(b"a", blob_a1, 0o100644), (b"b", blob_b1, 0o100755)])
        tree2 = self.commit_tree([(b"a", blob_a2, 0o100644), (b"c", blob_c2, 0o100755)])

        self.assertEqual([], merge_entries(b"", self.empty_tree, self.empty_tree))
        self.assertEqual(
            [
                ((None, None, None), (b"a", 0o100644, blob_a1.id)),
                ((None, None, None), (b"b", 0o100755, blob_b1.id)),
            ],
            merge_entries(b"", self.empty_tree, tree1),
        )
        self.assertEqual(
            [
                ((None, None, None), (b"x/a", 0o100644, blob_a1.id)),
                ((None, None, None), (b"x/b", 0o100755, blob_b1.id)),
            ],
            merge_entries(b"x", self.empty_tree, tree1),
        )

        self.assertEqual(
            [
                ((b"a", 0o100644, blob_a2.id), (None, None, None)),
                ((b"c", 0o100755, blob_c2.id), (None, None, None)),
            ],
            merge_entries(b"", tree2, self.empty_tree),
        )

        self.assertEqual(
            [
                ((b"a", 0o100644, blob_a1.id), (b"a", 0o100644, blob_a2.id)),
                ((b"b", 0o100755, blob_b1.id), (None, None, None)),
                ((None, None, None), (b"c", 0o100755, blob_c2.id)),
            ],
            merge_entries(b"", tree1, tree2),
        )

        self.assertEqual(
            [
                ((b"a", 0o100644, blob_a2.id), (b"a", 0o100644, blob_a1.id)),
                ((None, None, None), (b"b", 0o100755, blob_b1.id)),
                ((b"c", 0o100755, blob_c2.id), (None, None, None)),
            ],
            merge_entries(b"", tree2, tree1),
        )

        self.assertMergeFails(merge_entries, 0xDEADBEEF, 0o100644, "1" * 40)
        self.assertMergeFails(merge_entries, b"a", b"deadbeef", "1" * 40)
        self.assertMergeFails(merge_entries, b"a", 0o100644, 0xDEADBEEF)

    test_merge_entries = functest_builder(_do_test_merge_entries, _merge_entries_py)
    test_merge_entries_extension = ext_functest_builder(
        _do_test_merge_entries, _merge_entries
    )

    def _do_test_is_tree(self, is_tree):
        self.assertFalse(is_tree(TreeEntry(None, None, None)))
        self.assertFalse(is_tree(TreeEntry(b"a", 0o100644, b"a" * 40)))
        self.assertFalse(is_tree(TreeEntry(b"a", 0o100755, b"a" * 40)))
        self.assertFalse(is_tree(TreeEntry(b"a", 0o120000, b"a" * 40)))
        self.assertTrue(is_tree(TreeEntry(b"a", 0o040000, b"a" * 40)))
        self.assertRaises(TypeError, is_tree, TreeEntry(b"a", b"x", b"a" * 40))
        self.assertRaises(AttributeError, is_tree, 1234)

    test_is_tree = functest_builder(_do_test_is_tree, _is_tree_py)
    test_is_tree_extension = ext_functest_builder(_do_test_is_tree, _is_tree)

    def assertChangesEqual(self, expected, tree1, tree2, **kwargs):
        actual = list(tree_changes(self.store, tree1.id, tree2.id, **kwargs))
        self.assertEqual(expected, actual)

    # For brevity, the following tests use tuples instead of TreeEntry objects.

    def test_tree_changes_empty(self):
        self.assertChangesEqual([], self.empty_tree, self.empty_tree)

    def test_tree_changes_no_changes(self):
        blob = make_object(Blob, data=b"blob")
        tree = self.commit_tree([(b"a", blob), (b"b/c", blob)])
        self.assertChangesEqual([], self.empty_tree, self.empty_tree)
        self.assertChangesEqual([], tree, tree)
        self.assertChangesEqual(
            [
                TreeChange(CHANGE_UNCHANGED, (b"a", F, blob.id), (b"a", F, blob.id)),
                TreeChange(
                    CHANGE_UNCHANGED,
                    (b"b/c", F, blob.id),
                    (b"b/c", F, blob.id),
                ),
            ],
            tree,
            tree,
            want_unchanged=True,
        )

    def test_tree_changes_add_delete(self):
        blob_a = make_object(Blob, data=b"a")
        blob_b = make_object(Blob, data=b"b")
        tree = self.commit_tree([(b"a", blob_a, 0o100644), (b"x/b", blob_b, 0o100755)])
        self.assertChangesEqual(
            [
                TreeChange.add((b"a", 0o100644, blob_a.id)),
                TreeChange.add((b"x/b", 0o100755, blob_b.id)),
            ],
            self.empty_tree,
            tree,
        )
        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", 0o100644, blob_a.id)),
                TreeChange.delete((b"x/b", 0o100755, blob_b.id)),
            ],
            tree,
            self.empty_tree,
        )

    def test_tree_changes_modify_contents(self):
        blob_a1 = make_object(Blob, data=b"a1")
        blob_a2 = make_object(Blob, data=b"a2")
        tree1 = self.commit_tree([(b"a", blob_a1)])
        tree2 = self.commit_tree([(b"a", blob_a2)])
        self.assertChangesEqual(
            [TreeChange(CHANGE_MODIFY, (b"a", F, blob_a1.id), (b"a", F, blob_a2.id))],
            tree1,
            tree2,
        )

    def test_tree_changes_modify_mode(self):
        blob_a = make_object(Blob, data=b"a")
        tree1 = self.commit_tree([(b"a", blob_a, 0o100644)])
        tree2 = self.commit_tree([(b"a", blob_a, 0o100755)])
        self.assertChangesEqual(
            [
                TreeChange(
                    CHANGE_MODIFY,
                    (b"a", 0o100644, blob_a.id),
                    (b"a", 0o100755, blob_a.id),
                )
            ],
            tree1,
            tree2,
        )

    def test_tree_changes_change_type(self):
        blob_a1 = make_object(Blob, data=b"a")
        blob_a2 = make_object(Blob, data=b"/foo/bar")
        tree1 = self.commit_tree([(b"a", blob_a1, 0o100644)])
        tree2 = self.commit_tree([(b"a", blob_a2, 0o120000)])
        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", 0o100644, blob_a1.id)),
                TreeChange.add((b"a", 0o120000, blob_a2.id)),
            ],
            tree1,
            tree2,
        )

    def test_tree_changes_change_type_same(self):
        blob_a1 = make_object(Blob, data=b"a")
        blob_a2 = make_object(Blob, data=b"/foo/bar")
        tree1 = self.commit_tree([(b"a", blob_a1, 0o100644)])
        tree2 = self.commit_tree([(b"a", blob_a2, 0o120000)])
        self.assertChangesEqual(
            [
                TreeChange(
                    CHANGE_MODIFY,
                    (b"a", 0o100644, blob_a1.id),
                    (b"a", 0o120000, blob_a2.id),
                )
            ],
            tree1,
            tree2,
            change_type_same=True,
        )

    def test_tree_changes_to_tree(self):
        blob_a = make_object(Blob, data=b"a")
        blob_x = make_object(Blob, data=b"x")
        tree1 = self.commit_tree([(b"a", blob_a)])
        tree2 = self.commit_tree([(b"a/x", blob_x)])
        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", F, blob_a.id)),
                TreeChange.add((b"a/x", F, blob_x.id)),
            ],
            tree1,
            tree2,
        )

    def test_tree_changes_complex(self):
        blob_a_1 = make_object(Blob, data=b"a1_1")
        blob_bx1_1 = make_object(Blob, data=b"bx1_1")
        blob_bx2_1 = make_object(Blob, data=b"bx2_1")
        blob_by1_1 = make_object(Blob, data=b"by1_1")
        blob_by2_1 = make_object(Blob, data=b"by2_1")
        tree1 = self.commit_tree(
            [
                (b"a", blob_a_1),
                (b"b/x/1", blob_bx1_1),
                (b"b/x/2", blob_bx2_1),
                (b"b/y/1", blob_by1_1),
                (b"b/y/2", blob_by2_1),
            ]
        )

        blob_a_2 = make_object(Blob, data=b"a1_2")
        blob_bx1_2 = blob_bx1_1
        blob_by_2 = make_object(Blob, data=b"by_2")
        blob_c_2 = make_object(Blob, data=b"c_2")
        tree2 = self.commit_tree(
            [
                (b"a", blob_a_2),
                (b"b/x/1", blob_bx1_2),
                (b"b/y", blob_by_2),
                (b"c", blob_c_2),
            ]
        )

        self.assertChangesEqual(
            [
                TreeChange(
                    CHANGE_MODIFY,
                    (b"a", F, blob_a_1.id),
                    (b"a", F, blob_a_2.id),
                ),
                TreeChange.delete((b"b/x/2", F, blob_bx2_1.id)),
                TreeChange.add((b"b/y", F, blob_by_2.id)),
                TreeChange.delete((b"b/y/1", F, blob_by1_1.id)),
                TreeChange.delete((b"b/y/2", F, blob_by2_1.id)),
                TreeChange.add((b"c", F, blob_c_2.id)),
            ],
            tree1,
            tree2,
        )

    def test_tree_changes_name_order(self):
        blob = make_object(Blob, data=b"a")
        tree1 = self.commit_tree([(b"a", blob), (b"a.", blob), (b"a..", blob)])
        # Tree order is the reverse of this, so if we used tree order, 'a..'
        # would not be merged.
        tree2 = self.commit_tree([(b"a/x", blob), (b"a./x", blob), (b"a..", blob)])

        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", F, blob.id)),
                TreeChange.add((b"a/x", F, blob.id)),
                TreeChange.delete((b"a.", F, blob.id)),
                TreeChange.add((b"a./x", F, blob.id)),
            ],
            tree1,
            tree2,
        )

    def test_tree_changes_prune(self):
        blob_a1 = make_object(Blob, data=b"a1")
        blob_a2 = make_object(Blob, data=b"a2")
        blob_x = make_object(Blob, data=b"x")
        tree1 = self.commit_tree([(b"a", blob_a1), (b"b/x", blob_x)])
        tree2 = self.commit_tree([(b"a", blob_a2), (b"b/x", blob_x)])
        # Remove identical items so lookups will fail unless we prune.
        subtree = self.store[tree1[b"b"][1]]
        for entry in subtree.items():
            del self.store[entry.sha]
        del self.store[subtree.id]

        self.assertChangesEqual(
            [TreeChange(CHANGE_MODIFY, (b"a", F, blob_a1.id), (b"a", F, blob_a2.id))],
            tree1,
            tree2,
        )

    def test_tree_changes_rename_detector(self):
        blob_a1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob_a2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob_b = make_object(Blob, data=b"b")
        tree1 = self.commit_tree([(b"a", blob_a1), (b"b", blob_b)])
        tree2 = self.commit_tree([(b"c", blob_a2), (b"b", blob_b)])
        detector = RenameDetector(self.store)

        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", F, blob_a1.id)),
                TreeChange.add((b"c", F, blob_a2.id)),
            ],
            tree1,
            tree2,
        )
        self.assertChangesEqual(
            [
                TreeChange.delete((b"a", F, blob_a1.id)),
                TreeChange(
                    CHANGE_UNCHANGED,
                    (b"b", F, blob_b.id),
                    (b"b", F, blob_b.id),
                ),
                TreeChange.add((b"c", F, blob_a2.id)),
            ],
            tree1,
            tree2,
            want_unchanged=True,
        )
        self.assertChangesEqual(
            [TreeChange(CHANGE_RENAME, (b"a", F, blob_a1.id), (b"c", F, blob_a2.id))],
            tree1,
            tree2,
            rename_detector=detector,
        )
        self.assertChangesEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob_a1.id), (b"c", F, blob_a2.id)),
                TreeChange(
                    CHANGE_UNCHANGED,
                    (b"b", F, blob_b.id),
                    (b"b", F, blob_b.id),
                ),
            ],
            tree1,
            tree2,
            rename_detector=detector,
            want_unchanged=True,
        )

    def assertChangesForMergeEqual(self, expected, parent_trees, merge_tree, **kwargs):
        parent_tree_ids = [t.id for t in parent_trees]
        actual = list(
            tree_changes_for_merge(self.store, parent_tree_ids, merge_tree.id, **kwargs)
        )
        self.assertEqual(expected, actual)

        parent_tree_ids.reverse()
        expected = [list(reversed(cs)) for cs in expected]
        actual = list(
            tree_changes_for_merge(self.store, parent_tree_ids, merge_tree.id, **kwargs)
        )
        self.assertEqual(expected, actual)

    def test_tree_changes_for_merge_add_no_conflict(self):
        blob = make_object(Blob, data=b"blob")
        parent1 = self.commit_tree([])
        parent2 = merge = self.commit_tree([(b"a", blob)])
        self.assertChangesForMergeEqual([], [parent1, parent2], merge)
        self.assertChangesForMergeEqual([], [parent2, parent2], merge)

    def test_tree_changes_for_merge_add_modify_conflict(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        parent1 = self.commit_tree([])
        parent2 = self.commit_tree([(b"a", blob1)])
        merge = self.commit_tree([(b"a", blob2)])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange.add((b"a", F, blob2.id)),
                    TreeChange(CHANGE_MODIFY, (b"a", F, blob1.id), (b"a", F, blob2.id)),
                ]
            ],
            [parent1, parent2],
            merge,
        )

    def test_tree_changes_for_merge_modify_modify_conflict(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        blob3 = make_object(Blob, data=b"3")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = self.commit_tree([(b"a", blob2)])
        merge = self.commit_tree([(b"a", blob3)])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange(CHANGE_MODIFY, (b"a", F, blob1.id), (b"a", F, blob3.id)),
                    TreeChange(CHANGE_MODIFY, (b"a", F, blob2.id), (b"a", F, blob3.id)),
                ]
            ],
            [parent1, parent2],
            merge,
        )

    def test_tree_changes_for_merge_modify_no_conflict(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = merge = self.commit_tree([(b"a", blob2)])
        self.assertChangesForMergeEqual([], [parent1, parent2], merge)

    def test_tree_changes_for_merge_delete_delete_conflict(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = self.commit_tree([(b"a", blob2)])
        merge = self.commit_tree([])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange.delete((b"a", F, blob1.id)),
                    TreeChange.delete((b"a", F, blob2.id)),
                ]
            ],
            [parent1, parent2],
            merge,
        )

    def test_tree_changes_for_merge_delete_no_conflict(self):
        blob = make_object(Blob, data=b"blob")
        has = self.commit_tree([(b"a", blob)])
        doesnt_have = self.commit_tree([])
        self.assertChangesForMergeEqual([], [has, has], doesnt_have)
        self.assertChangesForMergeEqual([], [has, doesnt_have], doesnt_have)

    def test_tree_changes_for_merge_octopus_no_conflict(self):
        r = list(range(5))
        blobs = [make_object(Blob, data=bytes(i)) for i in r]
        parents = [self.commit_tree([(b"a", blobs[i])]) for i in r]
        for i in r:
            # Take the SHA from each of the parents.
            self.assertChangesForMergeEqual([], parents, parents[i])

    def test_tree_changes_for_merge_octopus_modify_conflict(self):
        # Because the octopus merge strategy is limited, I doubt it's possible
        # to create this with the git command line. But the output is well-
        # defined, so test it anyway.
        r = list(range(5))
        parent_blobs = [make_object(Blob, data=bytes(i)) for i in r]
        merge_blob = make_object(Blob, data=b"merge")
        parents = [self.commit_tree([(b"a", parent_blobs[i])]) for i in r]
        merge = self.commit_tree([(b"a", merge_blob)])
        expected = [
            [
                TreeChange(
                    CHANGE_MODIFY,
                    (b"a", F, parent_blobs[i].id),
                    (b"a", F, merge_blob.id),
                )
                for i in r
            ]
        ]
        self.assertChangesForMergeEqual(expected, parents, merge)

    def test_tree_changes_for_merge_octopus_delete(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"3")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = self.commit_tree([(b"a", blob2)])
        parent3 = merge = self.commit_tree([])
        self.assertChangesForMergeEqual([], [parent1, parent1, parent1], merge)
        self.assertChangesForMergeEqual([], [parent1, parent1, parent3], merge)
        self.assertChangesForMergeEqual([], [parent1, parent3, parent3], merge)
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange.delete((b"a", F, blob1.id)),
                    TreeChange.delete((b"a", F, blob2.id)),
                    None,
                ]
            ],
            [parent1, parent2, parent3],
            merge,
        )

    def test_tree_changes_for_merge_add_add_same_conflict(self):
        blob = make_object(Blob, data=b"a\nb\nc\nd\n")
        parent1 = self.commit_tree([(b"a", blob)])
        parent2 = self.commit_tree([])
        merge = self.commit_tree([(b"b", blob)])
        add = TreeChange.add((b"b", F, blob.id))
        self.assertChangesForMergeEqual([[add, add]], [parent1, parent2], merge)

    def test_tree_changes_for_merge_add_exact_rename_conflict(self):
        blob = make_object(Blob, data=b"a\nb\nc\nd\n")
        parent1 = self.commit_tree([(b"a", blob)])
        parent2 = self.commit_tree([])
        merge = self.commit_tree([(b"b", blob)])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange(CHANGE_RENAME, (b"a", F, blob.id), (b"b", F, blob.id)),
                    TreeChange.add((b"b", F, blob.id)),
                ]
            ],
            [parent1, parent2],
            merge,
            rename_detector=self.detector,
        )

    def test_tree_changes_for_merge_add_content_rename_conflict(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = self.commit_tree([])
        merge = self.commit_tree([(b"b", blob2)])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob2.id)),
                    TreeChange.add((b"b", F, blob2.id)),
                ]
            ],
            [parent1, parent2],
            merge,
            rename_detector=self.detector,
        )

    def test_tree_changes_for_merge_modify_rename_conflict(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        parent1 = self.commit_tree([(b"a", blob1)])
        parent2 = self.commit_tree([(b"b", blob1)])
        merge = self.commit_tree([(b"b", blob2)])
        self.assertChangesForMergeEqual(
            [
                [
                    TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob2.id)),
                    TreeChange(CHANGE_MODIFY, (b"b", F, blob1.id), (b"b", F, blob2.id)),
                ]
            ],
            [parent1, parent2],
            merge,
            rename_detector=self.detector,
        )


class RenameDetectionTest(DiffTestCase):
    def _do_test_count_blocks(self, count_blocks):
        blob = make_object(Blob, data=b"a\nb\na\n")
        self.assertBlockCountEqual({b"a\n": 4, b"b\n": 2}, count_blocks(blob))

    test_count_blocks = functest_builder(_do_test_count_blocks, _count_blocks_py)
    test_count_blocks_extension = ext_functest_builder(
        _do_test_count_blocks, _count_blocks
    )

    def _do_test_count_blocks_no_newline(self, count_blocks):
        blob = make_object(Blob, data=b"a\na")
        self.assertBlockCountEqual({b"a\n": 2, b"a": 1}, _count_blocks(blob))

    test_count_blocks_no_newline = functest_builder(
        _do_test_count_blocks_no_newline, _count_blocks_py
    )
    test_count_blocks_no_newline_extension = ext_functest_builder(
        _do_test_count_blocks_no_newline, _count_blocks
    )

    def assertBlockCountEqual(self, expected, got):
        self.assertEqual(
            {(hash(l) & 0xFFFFFFFF): c for (l, c) in expected.items()},
            {(h & 0xFFFFFFFF): c for (h, c) in got.items()},
        )

    def _do_test_count_blocks_chunks(self, count_blocks):
        blob = ShaFile.from_raw_chunks(Blob.type_num, [b"a\nb", b"\na\n"])
        self.assertBlockCountEqual({b"a\n": 4, b"b\n": 2}, _count_blocks(blob))

    test_count_blocks_chunks = functest_builder(
        _do_test_count_blocks_chunks, _count_blocks_py
    )
    test_count_blocks_chunks_extension = ext_functest_builder(
        _do_test_count_blocks_chunks, _count_blocks
    )

    def _do_test_count_blocks_long_lines(self, count_blocks):
        a = b"a" * 64
        data = a + b"xxx\ny\n" + a + b"zzz\n"
        blob = make_object(Blob, data=data)
        self.assertBlockCountEqual(
            {b"a" * 64: 128, b"xxx\n": 4, b"y\n": 2, b"zzz\n": 4},
            _count_blocks(blob),
        )

    test_count_blocks_long_lines = functest_builder(
        _do_test_count_blocks_long_lines, _count_blocks_py
    )
    test_count_blocks_long_lines_extension = ext_functest_builder(
        _do_test_count_blocks_long_lines, _count_blocks
    )

    def assertSimilar(self, expected_score, blob1, blob2):
        self.assertEqual(expected_score, _similarity_score(blob1, blob2))
        self.assertEqual(expected_score, _similarity_score(blob2, blob1))

    def test_similarity_score(self):
        blob0 = make_object(Blob, data=b"")
        blob1 = make_object(Blob, data=b"ab\ncd\ncd\n")
        blob2 = make_object(Blob, data=b"ab\n")
        blob3 = make_object(Blob, data=b"cd\n")
        blob4 = make_object(Blob, data=b"cd\ncd\n")

        self.assertSimilar(100, blob0, blob0)
        self.assertSimilar(0, blob0, blob1)
        self.assertSimilar(33, blob1, blob2)
        self.assertSimilar(33, blob1, blob3)
        self.assertSimilar(66, blob1, blob4)
        self.assertSimilar(0, blob2, blob3)
        self.assertSimilar(50, blob3, blob4)

    def test_similarity_score_cache(self):
        blob1 = make_object(Blob, data=b"ab\ncd\n")
        blob2 = make_object(Blob, data=b"ab\n")

        block_cache = {}
        self.assertEqual(50, _similarity_score(blob1, blob2, block_cache=block_cache))
        self.assertEqual({blob1.id, blob2.id}, set(block_cache))

        def fail_chunks():
            self.fail("Unexpected call to as_raw_chunks()")

        blob1.as_raw_chunks = blob2.as_raw_chunks = fail_chunks
        blob1.raw_length = lambda: 6
        blob2.raw_length = lambda: 3
        self.assertEqual(50, _similarity_score(blob1, blob2, block_cache=block_cache))

    def test_tree_entry_sort(self):
        sha = "abcd" * 10
        expected_entries = [
            TreeChange.add(TreeEntry(b"aaa", F, sha)),
            TreeChange(
                CHANGE_COPY,
                TreeEntry(b"bbb", F, sha),
                TreeEntry(b"aab", F, sha),
            ),
            TreeChange(
                CHANGE_MODIFY,
                TreeEntry(b"bbb", F, sha),
                TreeEntry(b"bbb", F, b"dabc" * 10),
            ),
            TreeChange(
                CHANGE_RENAME,
                TreeEntry(b"bbc", F, sha),
                TreeEntry(b"ddd", F, sha),
            ),
            TreeChange.delete(TreeEntry(b"ccc", F, sha)),
        ]

        for perm in permutations(expected_entries):
            self.assertEqual(expected_entries, sorted(perm, key=_tree_change_key))

    def detect_renames(self, tree1, tree2, want_unchanged=False, **kwargs):
        detector = RenameDetector(self.store, **kwargs)
        return detector.changes_with_renames(
            tree1.id, tree2.id, want_unchanged=want_unchanged
        )

    def test_no_renames(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\ne\nf\n")
        blob3 = make_object(Blob, data=b"a\nb\ng\nh\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"a", blob1), (b"b", blob3)])
        self.assertEqual(
            [TreeChange(CHANGE_MODIFY, (b"b", F, blob2.id), (b"b", F, blob3.id))],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_one_to_one(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"c", blob1), (b"d", blob2)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"c", F, blob1.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob2.id), (b"d", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_split_different_type(self):
        blob = make_object(Blob, data=b"/foo")
        tree1 = self.commit_tree([(b"a", blob, 0o100644)])
        tree2 = self.commit_tree([(b"a", blob, 0o120000)])
        self.assertEqual(
            [
                TreeChange.add((b"a", 0o120000, blob.id)),
                TreeChange.delete((b"a", 0o100644, blob.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_and_different_type(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"a", blob2, 0o120000), (b"b", blob1)])
        self.assertEqual(
            [
                TreeChange.add((b"a", 0o120000, blob2.id)),
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob1.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_one_to_many(self):
        blob = make_object(Blob, data=b"1")
        tree1 = self.commit_tree([(b"a", blob)])
        tree2 = self.commit_tree([(b"b", blob), (b"c", blob)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob.id), (b"b", F, blob.id)),
                TreeChange(CHANGE_COPY, (b"a", F, blob.id), (b"c", F, blob.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_many_to_one(self):
        blob = make_object(Blob, data=b"1")
        tree1 = self.commit_tree([(b"a", blob), (b"b", blob)])
        tree2 = self.commit_tree([(b"c", blob)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob.id), (b"c", F, blob.id)),
                TreeChange.delete((b"b", F, blob.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_many_to_many(self):
        blob = make_object(Blob, data=b"1")
        tree1 = self.commit_tree([(b"a", blob), (b"b", blob)])
        tree2 = self.commit_tree([(b"c", blob), (b"d", blob), (b"e", blob)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob.id), (b"c", F, blob.id)),
                TreeChange(CHANGE_COPY, (b"a", F, blob.id), (b"e", F, blob.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob.id), (b"d", F, blob.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_copy_modify(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"a", blob2), (b"b", blob1)])
        self.assertEqual(
            [
                TreeChange(CHANGE_MODIFY, (b"a", F, blob1.id), (b"a", F, blob2.id)),
                TreeChange(CHANGE_COPY, (b"a", F, blob1.id), (b"b", F, blob1.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_copy_change_mode(self):
        blob = make_object(Blob, data=b"a\nb\nc\nd\n")
        tree1 = self.commit_tree([(b"a", blob)])
        tree2 = self.commit_tree([(b"a", blob, 0o100755), (b"b", blob)])
        self.assertEqual(
            [
                TreeChange(
                    CHANGE_MODIFY,
                    (b"a", F, blob.id),
                    (b"a", 0o100755, blob.id),
                ),
                TreeChange(CHANGE_COPY, (b"a", F, blob.id), (b"b", F, blob.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_rename_threshold(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\n")
        blob2 = make_object(Blob, data=b"a\nb\nd\n")
        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"b", blob2)])
        self.assertEqual(
            [TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob2.id))],
            self.detect_renames(tree1, tree2, rename_threshold=50),
        )
        self.assertEqual(
            [
                TreeChange.delete((b"a", F, blob1.id)),
                TreeChange.add((b"b", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2, rename_threshold=75),
        )

    def test_content_rename_max_files(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd")
        blob4 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob2 = make_object(Blob, data=b"e\nf\ng\nh\n")
        blob3 = make_object(Blob, data=b"e\nf\ng\ni\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"c", blob3), (b"d", blob4)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"d", F, blob4.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob2.id), (b"c", F, blob3.id)),
            ],
            self.detect_renames(tree1, tree2),
        )
        self.assertEqual(
            [
                TreeChange.delete((b"a", F, blob1.id)),
                TreeChange.delete((b"b", F, blob2.id)),
                TreeChange.add((b"c", F, blob3.id)),
                TreeChange.add((b"d", F, blob4.id)),
            ],
            self.detect_renames(tree1, tree2, max_files=1),
        )

    def test_content_rename_one_to_one(self):
        b11 = make_object(Blob, data=b"a\nb\nc\nd\n")
        b12 = make_object(Blob, data=b"a\nb\nc\ne\n")
        b21 = make_object(Blob, data=b"e\nf\ng\n\nh")
        b22 = make_object(Blob, data=b"e\nf\ng\n\ni")
        tree1 = self.commit_tree([(b"a", b11), (b"b", b21)])
        tree2 = self.commit_tree([(b"c", b12), (b"d", b22)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, b11.id), (b"c", F, b12.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, b21.id), (b"d", F, b22.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_content_rename_one_to_one_ordering(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\ne\nf\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\nd\ng\nh\n")
        # 6/10 match to blob1, 8/10 match to blob2
        blob3 = make_object(Blob, data=b"a\nb\nc\nd\ng\ni\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"c", blob3)])
        self.assertEqual(
            [
                TreeChange.delete((b"a", F, blob1.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob2.id), (b"c", F, blob3.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

        tree3 = self.commit_tree([(b"a", blob2), (b"b", blob1)])
        tree4 = self.commit_tree([(b"c", blob3)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob2.id), (b"c", F, blob3.id)),
                TreeChange.delete((b"b", F, blob1.id)),
            ],
            self.detect_renames(tree3, tree4),
        )

    def test_content_rename_one_to_many(self):
        blob1 = make_object(Blob, data=b"aa\nb\nc\nd\ne\n")
        blob2 = make_object(Blob, data=b"ab\nb\nc\nd\ne\n")  # 8/11 match
        blob3 = make_object(Blob, data=b"aa\nb\nc\nd\nf\n")  # 9/11 match
        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"b", blob2), (b"c", blob3)])
        self.assertEqual(
            [
                TreeChange(CHANGE_COPY, (b"a", F, blob1.id), (b"b", F, blob2.id)),
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"c", F, blob3.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_content_rename_many_to_one(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob3 = make_object(Blob, data=b"a\nb\nc\nf\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"c", blob3)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"c", F, blob3.id)),
                TreeChange.delete((b"b", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_content_rename_many_to_many(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob3 = make_object(Blob, data=b"a\nb\nc\nf\n")
        blob4 = make_object(Blob, data=b"a\nb\nc\ng\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"c", blob3), (b"d", blob4)])
        # TODO(dborowitz): Distribute renames rather than greedily choosing
        # copies.
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"c", F, blob3.id)),
                TreeChange(CHANGE_COPY, (b"a", F, blob1.id), (b"d", F, blob4.id)),
                TreeChange.delete((b"b", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_content_rename_with_more_deletions(self):
        blob1 = make_object(Blob, data=b"")
        tree1 = self.commit_tree(
            [(b"a", blob1), (b"b", blob1), (b"c", blob1), (b"d", blob1)]
        )
        tree2 = self.commit_tree([(b"e", blob1), (b"f", blob1), (b"g", blob1)])
        self.maxDiff = None
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"e", F, blob1.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob1.id), (b"f", F, blob1.id)),
                TreeChange(CHANGE_RENAME, (b"c", F, blob1.id), (b"g", F, blob1.id)),
                TreeChange.delete((b"d", F, blob1.id)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_content_rename_gitlink(self):
        blob1 = make_object(Blob, data=b"blob1")
        blob2 = make_object(Blob, data=b"blob2")
        link1 = b"1" * 40
        link2 = b"2" * 40
        tree1 = self.commit_tree([(b"a", blob1), (b"b", link1, 0o160000)])
        tree2 = self.commit_tree([(b"c", blob2), (b"d", link2, 0o160000)])
        self.assertEqual(
            [
                TreeChange.delete((b"a", 0o100644, blob1.id)),
                TreeChange.delete((b"b", 0o160000, link1)),
                TreeChange.add((b"c", 0o100644, blob2.id)),
                TreeChange.add((b"d", 0o160000, link2)),
            ],
            self.detect_renames(tree1, tree2),
        )

    def test_exact_rename_swap(self):
        blob1 = make_object(Blob, data=b"1")
        blob2 = make_object(Blob, data=b"2")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"a", blob2), (b"b", blob1)])
        self.assertEqual(
            [
                TreeChange(CHANGE_MODIFY, (b"a", F, blob1.id), (b"a", F, blob2.id)),
                TreeChange(CHANGE_MODIFY, (b"b", F, blob2.id), (b"b", F, blob1.id)),
            ],
            self.detect_renames(tree1, tree2),
        )
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob1.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob2.id), (b"a", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2, rewrite_threshold=50),
        )

    def test_content_rename_swap(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"e\nf\ng\nh\n")
        blob3 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob4 = make_object(Blob, data=b"e\nf\ng\ni\n")
        tree1 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        tree2 = self.commit_tree([(b"a", blob4), (b"b", blob3)])
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob3.id)),
                TreeChange(CHANGE_RENAME, (b"b", F, blob2.id), (b"a", F, blob4.id)),
            ],
            self.detect_renames(tree1, tree2, rewrite_threshold=60),
        )

    def test_rewrite_threshold(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        blob3 = make_object(Blob, data=b"a\nb\nf\ng\n")

        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"a", blob3), (b"b", blob2)])

        no_renames = [
            TreeChange(CHANGE_MODIFY, (b"a", F, blob1.id), (b"a", F, blob3.id)),
            TreeChange(CHANGE_COPY, (b"a", F, blob1.id), (b"b", F, blob2.id)),
        ]
        self.assertEqual(no_renames, self.detect_renames(tree1, tree2))
        self.assertEqual(
            no_renames, self.detect_renames(tree1, tree2, rewrite_threshold=40)
        )
        self.assertEqual(
            [
                TreeChange.add((b"a", F, blob3.id)),
                TreeChange(CHANGE_RENAME, (b"a", F, blob1.id), (b"b", F, blob2.id)),
            ],
            self.detect_renames(tree1, tree2, rewrite_threshold=80),
        )

    def test_find_copies_harder_exact(self):
        blob = make_object(Blob, data=b"blob")
        tree1 = self.commit_tree([(b"a", blob)])
        tree2 = self.commit_tree([(b"a", blob), (b"b", blob)])
        self.assertEqual(
            [TreeChange.add((b"b", F, blob.id))],
            self.detect_renames(tree1, tree2),
        )
        self.assertEqual(
            [TreeChange(CHANGE_COPY, (b"a", F, blob.id), (b"b", F, blob.id))],
            self.detect_renames(tree1, tree2, find_copies_harder=True),
        )

    def test_find_copies_harder_content(self):
        blob1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        tree1 = self.commit_tree([(b"a", blob1)])
        tree2 = self.commit_tree([(b"a", blob1), (b"b", blob2)])
        self.assertEqual(
            [TreeChange.add((b"b", F, blob2.id))],
            self.detect_renames(tree1, tree2),
        )
        self.assertEqual(
            [TreeChange(CHANGE_COPY, (b"a", F, blob1.id), (b"b", F, blob2.id))],
            self.detect_renames(tree1, tree2, find_copies_harder=True),
        )

    def test_find_copies_harder_with_rewrites(self):
        blob_a1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob_a2 = make_object(Blob, data=b"f\ng\nh\ni\n")
        blob_b2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        tree1 = self.commit_tree([(b"a", blob_a1)])
        tree2 = self.commit_tree([(b"a", blob_a2), (b"b", blob_b2)])
        self.assertEqual(
            [
                TreeChange(CHANGE_MODIFY, (b"a", F, blob_a1.id), (b"a", F, blob_a2.id)),
                TreeChange(CHANGE_COPY, (b"a", F, blob_a1.id), (b"b", F, blob_b2.id)),
            ],
            self.detect_renames(tree1, tree2, find_copies_harder=True),
        )
        self.assertEqual(
            [
                TreeChange.add((b"a", F, blob_a2.id)),
                TreeChange(CHANGE_RENAME, (b"a", F, blob_a1.id), (b"b", F, blob_b2.id)),
            ],
            self.detect_renames(
                tree1, tree2, rewrite_threshold=50, find_copies_harder=True
            ),
        )

    def test_reuse_detector(self):
        blob = make_object(Blob, data=b"blob")
        tree1 = self.commit_tree([(b"a", blob)])
        tree2 = self.commit_tree([(b"b", blob)])
        detector = RenameDetector(self.store)
        changes = [TreeChange(CHANGE_RENAME, (b"a", F, blob.id), (b"b", F, blob.id))]
        self.assertEqual(changes, detector.changes_with_renames(tree1.id, tree2.id))
        self.assertEqual(changes, detector.changes_with_renames(tree1.id, tree2.id))

    def test_want_unchanged(self):
        blob_a1 = make_object(Blob, data=b"a\nb\nc\nd\n")
        blob_b = make_object(Blob, data=b"b")
        blob_c2 = make_object(Blob, data=b"a\nb\nc\ne\n")
        tree1 = self.commit_tree([(b"a", blob_a1), (b"b", blob_b)])
        tree2 = self.commit_tree([(b"c", blob_c2), (b"b", blob_b)])
        self.assertEqual(
            [TreeChange(CHANGE_RENAME, (b"a", F, blob_a1.id), (b"c", F, blob_c2.id))],
            self.detect_renames(tree1, tree2),
        )
        self.assertEqual(
            [
                TreeChange(CHANGE_RENAME, (b"a", F, blob_a1.id), (b"c", F, blob_c2.id)),
                TreeChange(
                    CHANGE_UNCHANGED,
                    (b"b", F, blob_b.id),
                    (b"b", F, blob_b.id),
                ),
            ],
            self.detect_renames(tree1, tree2, want_unchanged=True),
        )
