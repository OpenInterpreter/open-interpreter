# test_utils.py -- Tests for git test utilities.
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

"""Tests for git test utilities."""

from dulwich.tests import TestCase

from ..object_store import MemoryObjectStore
from ..objects import Blob
from .utils import build_commit_graph, make_object


class BuildCommitGraphTest(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()

    def test_linear(self):
        c1, c2 = build_commit_graph(self.store, [[1], [2, 1]])
        for obj_id in [c1.id, c2.id, c1.tree, c2.tree]:
            self.assertIn(obj_id, self.store)
        self.assertEqual([], c1.parents)
        self.assertEqual([c1.id], c2.parents)
        self.assertEqual(c1.tree, c2.tree)
        self.assertEqual([], self.store[c1.tree].items())
        self.assertGreater(c2.commit_time, c1.commit_time)

    def test_merge(self):
        c1, c2, c3, c4 = build_commit_graph(
            self.store, [[1], [2, 1], [3, 1], [4, 2, 3]]
        )
        self.assertEqual([c2.id, c3.id], c4.parents)
        self.assertGreater(c4.commit_time, c2.commit_time)
        self.assertGreater(c4.commit_time, c3.commit_time)

    def test_missing_parent(self):
        self.assertRaises(
            ValueError, build_commit_graph, self.store, [[1], [3, 2], [2, 1]]
        )

    def test_trees(self):
        a1 = make_object(Blob, data=b"aaa1")
        a2 = make_object(Blob, data=b"aaa2")
        c1, c2 = build_commit_graph(
            self.store,
            [[1], [2, 1]],
            trees={1: [(b"a", a1)], 2: [(b"a", a2, 0o100644)]},
        )
        self.assertEqual((0o100644, a1.id), self.store[c1.tree][b"a"])
        self.assertEqual((0o100644, a2.id), self.store[c2.tree][b"a"])

    def test_attrs(self):
        c1, c2 = build_commit_graph(
            self.store, [[1], [2, 1]], attrs={1: {"message": b"Hooray!"}}
        )
        self.assertEqual(b"Hooray!", c1.message)
        self.assertEqual(b"Commit 2", c2.message)

    def test_commit_time(self):
        c1, c2, c3 = build_commit_graph(
            self.store,
            [[1], [2, 1], [3, 2]],
            attrs={1: {"commit_time": 124}, 2: {"commit_time": 123}},
        )
        self.assertEqual(124, c1.commit_time)
        self.assertEqual(123, c2.commit_time)
        self.assertTrue(c2.commit_time < c1.commit_time < c3.commit_time)
