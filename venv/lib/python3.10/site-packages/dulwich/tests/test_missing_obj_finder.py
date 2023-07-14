# test_missing_obj_finder.py -- tests for MissingObjectFinder
# Copyright (C) 2012 syntevo GmbH
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

from dulwich.tests import TestCase

from ..object_store import MemoryObjectStore, MissingObjectFinder
from ..objects import Blob
from .utils import build_commit_graph, make_object, make_tag


class MissingObjectFinderTest(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.commits = []

    def cmt(self, n):
        return self.commits[n - 1]

    def assertMissingMatch(self, haves, wants, expected):
        for sha, path in MissingObjectFinder(self.store, haves, wants, shallow=set()):
            self.assertIn(
                sha,
                expected,
                "({},{}) erroneously reported as missing".format(sha, path)
            )
            expected.remove(sha)

        self.assertEqual(
            len(expected),
            0,
            "some objects are not reported as missing: {}".format(expected),
        )


class MOFLinearRepoTest(MissingObjectFinderTest):
    def setUp(self):
        super().setUp()
        # present in 1, removed in 3
        f1_1 = make_object(Blob, data=b"f1")
        # present in all revisions, changed in 2 and 3
        f2_1 = make_object(Blob, data=b"f2")
        f2_2 = make_object(Blob, data=b"f2-changed")
        f2_3 = make_object(Blob, data=b"f2-changed-again")
        # added in 2, left unmodified in 3
        f3_2 = make_object(Blob, data=b"f3")

        commit_spec = [[1], [2, 1], [3, 2]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f2_1)],
            2: [(b"f1", f1_1), (b"f2", f2_2), (b"f3", f3_2)],
            3: [(b"f2", f2_3), (b"f3", f3_2)],
        }
        # commit 1: f1 and f2
        # commit 2: f3 added, f2 changed. Missing shall report commit id and a
        # tree referenced by commit
        # commit 3: f1 removed, f2 changed. Commit sha and root tree sha shall
        # be reported as modified
        self.commits = build_commit_graph(self.store, commit_spec, trees)
        self.missing_1_2 = [self.cmt(2).id, self.cmt(2).tree, f2_2.id, f3_2.id]
        self.missing_2_3 = [self.cmt(3).id, self.cmt(3).tree, f2_3.id]
        self.missing_1_3 = [
            self.cmt(2).id,
            self.cmt(3).id,
            self.cmt(2).tree,
            self.cmt(3).tree,
            f2_2.id,
            f3_2.id,
            f2_3.id,
        ]

    def test_1_to_2(self):
        self.assertMissingMatch([self.cmt(1).id], [self.cmt(2).id], self.missing_1_2)

    def test_2_to_3(self):
        self.assertMissingMatch([self.cmt(2).id], [self.cmt(3).id], self.missing_2_3)

    def test_1_to_3(self):
        self.assertMissingMatch([self.cmt(1).id], [self.cmt(3).id], self.missing_1_3)

    def test_bogus_haves(self):
        """Ensure non-existent SHA in haves are tolerated"""
        bogus_sha = self.cmt(2).id[::-1]
        haves = [self.cmt(1).id, bogus_sha]
        wants = [self.cmt(3).id]
        self.assertMissingMatch(haves, wants, self.missing_1_3)

    def test_bogus_wants_failure(self):
        """Ensure non-existent SHA in wants are not tolerated"""
        bogus_sha = self.cmt(2).id[::-1]
        haves = [self.cmt(1).id]
        wants = [self.cmt(3).id, bogus_sha]
        self.assertRaises(
            KeyError, MissingObjectFinder, self.store, haves, wants, shallow=set())

    def test_no_changes(self):
        self.assertMissingMatch([self.cmt(3).id], [self.cmt(3).id], [])


class MOFMergeForkRepoTest(MissingObjectFinderTest):
    # 1 --- 2 --- 4 --- 6 --- 7
    #          \        /
    #           3  ---
    #            \
    #             5

    def setUp(self):
        super().setUp()
        f1_1 = make_object(Blob, data=b"f1")
        f1_2 = make_object(Blob, data=b"f1-2")
        f1_4 = make_object(Blob, data=b"f1-4")
        f1_7 = make_object(Blob, data=b"f1-2")  # same data as in rev 2
        f2_1 = make_object(Blob, data=b"f2")
        f2_3 = make_object(Blob, data=b"f2-3")
        f3_3 = make_object(Blob, data=b"f3")
        f3_5 = make_object(Blob, data=b"f3-5")
        commit_spec = [[1], [2, 1], [3, 2], [4, 2], [5, 3], [6, 3, 4], [7, 6]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f2_1)],
            2: [(b"f1", f1_2), (b"f2", f2_1)],  # f1 changed
            # f3 added, f2 changed
            3: [(b"f1", f1_2), (b"f2", f2_3), (b"f3", f3_3)],
            4: [(b"f1", f1_4), (b"f2", f2_1)],  # f1 changed
            5: [(b"f1", f1_2), (b"f3", f3_5)],  # f2 removed, f3 changed
            # merged 3 and 4
            6: [(b"f1", f1_4), (b"f2", f2_3), (b"f3", f3_3)],
            # f1 changed to match rev2. f3 removed
            7: [(b"f1", f1_7), (b"f2", f2_3)],
        }
        self.commits = build_commit_graph(self.store, commit_spec, trees)

        self.f1_2_id = f1_2.id
        self.f1_4_id = f1_4.id
        self.f1_7_id = f1_7.id
        self.f2_3_id = f2_3.id
        self.f3_3_id = f3_3.id

        self.assertEqual(f1_2.id, f1_7.id, "[sanity]")

    def test_have6_want7(self):
        # have 6, want 7. Ideally, shall not report f1_7 as it's the same as
        # f1_2, however, to do so, MissingObjectFinder shall not record trees
        # of common commits only, but also all parent trees and tree items,
        # which is an overkill (i.e. in sha_done it records f1_4 as known, and
        # doesn't record f1_2 was known prior to that, hence can't detect f1_7
        # is in fact f1_2 and shall not be reported)
        self.assertMissingMatch(
            [self.cmt(6).id],
            [self.cmt(7).id],
            [self.cmt(7).id, self.cmt(7).tree, self.f1_7_id],
        )

    def test_have4_want7(self):
        # have 4, want 7. Shall not include rev5 as it is not in the tree
        # between 4 and 7 (well, it is, but its SHA's are irrelevant for 4..7
        # commit hierarchy)
        self.assertMissingMatch(
            [self.cmt(4).id],
            [self.cmt(7).id],
            [
                self.cmt(7).id,
                self.cmt(6).id,
                self.cmt(3).id,
                self.cmt(7).tree,
                self.cmt(6).tree,
                self.cmt(3).tree,
                self.f2_3_id,
                self.f3_3_id,
            ],
        )

    def test_have1_want6(self):
        # have 1, want 6. Shall not include rev5
        self.assertMissingMatch(
            [self.cmt(1).id],
            [self.cmt(6).id],
            [
                self.cmt(6).id,
                self.cmt(4).id,
                self.cmt(3).id,
                self.cmt(2).id,
                self.cmt(6).tree,
                self.cmt(4).tree,
                self.cmt(3).tree,
                self.cmt(2).tree,
                self.f1_2_id,
                self.f1_4_id,
                self.f2_3_id,
                self.f3_3_id,
            ],
        )

    def test_have3_want6(self):
        # have 3, want 7. Shall not report rev2 and its tree, because
        # haves(3) means has parents, i.e. rev2, too
        # BUT shall report any changes descending rev2 (excluding rev3)
        # Shall NOT report f1_7 as it's technically == f1_2
        self.assertMissingMatch(
            [self.cmt(3).id],
            [self.cmt(7).id],
            [
                self.cmt(7).id,
                self.cmt(6).id,
                self.cmt(4).id,
                self.cmt(7).tree,
                self.cmt(6).tree,
                self.cmt(4).tree,
                self.f1_4_id,
            ],
        )

    def test_have5_want7(self):
        # have 5, want 7. Common parent is rev2, hence children of rev2 from
        # a descent line other than rev5 shall be reported
        # expects f1_4 from rev6. f3_5 is known in rev5;
        # f1_7 shall be the same as f1_2 (known, too)
        self.assertMissingMatch(
            [self.cmt(5).id],
            [self.cmt(7).id],
            [
                self.cmt(7).id,
                self.cmt(6).id,
                self.cmt(4).id,
                self.cmt(7).tree,
                self.cmt(6).tree,
                self.cmt(4).tree,
                self.f1_4_id,
            ],
        )


class MOFTagsTest(MissingObjectFinderTest):
    def setUp(self):
        super().setUp()
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1]]
        trees = {1: [(b"f1", f1_1)]}
        self.commits = build_commit_graph(self.store, commit_spec, trees)

        self._normal_tag = make_tag(self.cmt(1))
        self.store.add_object(self._normal_tag)

        self._tag_of_tag = make_tag(self._normal_tag)
        self.store.add_object(self._tag_of_tag)

        self._tag_of_tree = make_tag(self.store[self.cmt(1).tree])
        self.store.add_object(self._tag_of_tree)

        self._tag_of_blob = make_tag(f1_1)
        self.store.add_object(self._tag_of_blob)

        self._tag_of_tag_of_blob = make_tag(self._tag_of_blob)
        self.store.add_object(self._tag_of_tag_of_blob)

        self.f1_1_id = f1_1.id

    def test_tagged_commit(self):
        # The user already has the tagged commit, all they want is the tag,
        # so send them only the tag object.
        self.assertMissingMatch(
            [self.cmt(1).id], [self._normal_tag.id], [self._normal_tag.id]
        )

    # The remaining cases are unusual, but do happen in the wild.
    def test_tagged_tag(self):
        # User already has tagged tag, send only tag of tag
        self.assertMissingMatch(
            [self._normal_tag.id], [self._tag_of_tag.id], [self._tag_of_tag.id]
        )
        # User needs both tags, but already has commit
        self.assertMissingMatch(
            [self.cmt(1).id],
            [self._tag_of_tag.id],
            [self._normal_tag.id, self._tag_of_tag.id],
        )

    def test_tagged_tree(self):
        self.assertMissingMatch(
            [],
            [self._tag_of_tree.id],
            [self._tag_of_tree.id, self.cmt(1).tree, self.f1_1_id],
        )

    def test_tagged_blob(self):
        self.assertMissingMatch(
            [], [self._tag_of_blob.id], [self._tag_of_blob.id, self.f1_1_id]
        )

    def test_tagged_tagged_blob(self):
        self.assertMissingMatch(
            [],
            [self._tag_of_tag_of_blob.id],
            [self._tag_of_tag_of_blob.id, self._tag_of_blob.id, self.f1_1_id],
        )
