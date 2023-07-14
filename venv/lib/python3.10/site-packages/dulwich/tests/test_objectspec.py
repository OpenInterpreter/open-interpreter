# test_objectspec.py -- tests for objectspec.py
# Copyright (C) 2014 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for revision spec parsing."""

# TODO: Round-trip parse-serialize-parse and serialize-parse-serialize tests.


from dulwich.tests import TestCase

from ..objects import Blob
from ..objectspec import (parse_commit, parse_commit_range, parse_object,
                          parse_ref, parse_refs, parse_reftuple,
                          parse_reftuples, parse_tree)
from ..repo import MemoryRepo
from .utils import build_commit_graph


class ParseObjectTests(TestCase):
    """Test parse_object."""

    def test_nonexistent(self):
        r = MemoryRepo()
        self.assertRaises(KeyError, parse_object, r, "thisdoesnotexist")

    def test_blob_by_sha(self):
        r = MemoryRepo()
        b = Blob.from_string(b"Blah")
        r.object_store.add_object(b)
        self.assertEqual(b, parse_object(r, b.id))


class ParseCommitRangeTests(TestCase):
    """Test parse_commit_range."""

    def test_nonexistent(self):
        r = MemoryRepo()
        self.assertRaises(KeyError, parse_commit_range, r, "thisdoesnotexist")

    def test_commit_by_sha(self):
        r = MemoryRepo()
        c1, c2, c3 = build_commit_graph(r.object_store, [[1], [2, 1], [3, 1, 2]])
        self.assertEqual([c1], list(parse_commit_range(r, c1.id)))


class ParseCommitTests(TestCase):
    """Test parse_commit."""

    def test_nonexistent(self):
        r = MemoryRepo()
        self.assertRaises(KeyError, parse_commit, r, "thisdoesnotexist")

    def test_commit_by_sha(self):
        r = MemoryRepo()
        [c1] = build_commit_graph(r.object_store, [[1]])
        self.assertEqual(c1, parse_commit(r, c1.id))

    def test_commit_by_short_sha(self):
        r = MemoryRepo()
        [c1] = build_commit_graph(r.object_store, [[1]])
        self.assertEqual(c1, parse_commit(r, c1.id[:10]))


class ParseRefTests(TestCase):
    def test_nonexistent(self):
        r = {}
        self.assertRaises(KeyError, parse_ref, r, b"thisdoesnotexist")

    def test_ambiguous_ref(self):
        r = {
            b"ambig1": "bla",
            b"refs/ambig1": "bla",
            b"refs/tags/ambig1": "bla",
            b"refs/heads/ambig1": "bla",
            b"refs/remotes/ambig1": "bla",
            b"refs/remotes/ambig1/HEAD": "bla",
        }
        self.assertEqual(b"ambig1", parse_ref(r, b"ambig1"))

    def test_ambiguous_ref2(self):
        r = {
            b"refs/ambig2": "bla",
            b"refs/tags/ambig2": "bla",
            b"refs/heads/ambig2": "bla",
            b"refs/remotes/ambig2": "bla",
            b"refs/remotes/ambig2/HEAD": "bla",
        }
        self.assertEqual(b"refs/ambig2", parse_ref(r, b"ambig2"))

    def test_ambiguous_tag(self):
        r = {
            b"refs/tags/ambig3": "bla",
            b"refs/heads/ambig3": "bla",
            b"refs/remotes/ambig3": "bla",
            b"refs/remotes/ambig3/HEAD": "bla",
        }
        self.assertEqual(b"refs/tags/ambig3", parse_ref(r, b"ambig3"))

    def test_ambiguous_head(self):
        r = {
            b"refs/heads/ambig4": "bla",
            b"refs/remotes/ambig4": "bla",
            b"refs/remotes/ambig4/HEAD": "bla",
        }
        self.assertEqual(b"refs/heads/ambig4", parse_ref(r, b"ambig4"))

    def test_ambiguous_remote(self):
        r = {b"refs/remotes/ambig5": "bla", b"refs/remotes/ambig5/HEAD": "bla"}
        self.assertEqual(b"refs/remotes/ambig5", parse_ref(r, b"ambig5"))

    def test_ambiguous_remote_head(self):
        r = {b"refs/remotes/ambig6/HEAD": "bla"}
        self.assertEqual(b"refs/remotes/ambig6/HEAD", parse_ref(r, b"ambig6"))

    def test_heads_full(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(b"refs/heads/foo", parse_ref(r, b"refs/heads/foo"))

    def test_heads_partial(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(b"refs/heads/foo", parse_ref(r, b"heads/foo"))

    def test_tags_partial(self):
        r = {b"refs/tags/foo": "bla"}
        self.assertEqual(b"refs/tags/foo", parse_ref(r, b"tags/foo"))


class ParseRefsTests(TestCase):
    def test_nonexistent(self):
        r = {}
        self.assertRaises(KeyError, parse_refs, r, [b"thisdoesnotexist"])

    def test_head(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual([b"refs/heads/foo"], parse_refs(r, [b"foo"]))

    def test_full(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual([b"refs/heads/foo"], parse_refs(r, b"refs/heads/foo"))


class ParseReftupleTests(TestCase):
    def test_nonexistent(self):
        r = {}
        self.assertRaises(KeyError, parse_reftuple, r, r, b"thisdoesnotexist")

    def test_head(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", False),
            parse_reftuple(r, r, b"foo"),
        )
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", True),
            parse_reftuple(r, r, b"+foo"),
        )
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", True),
            parse_reftuple(r, {}, b"+foo"),
        )
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", True),
            parse_reftuple(r, {}, b"foo", True),
        )

    def test_full(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", False),
            parse_reftuple(r, r, b"refs/heads/foo"),
        )

    def test_no_left_ref(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            (None, b"refs/heads/foo", False),
            parse_reftuple(r, r, b":refs/heads/foo"),
        )

    def test_no_right_ref(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            (b"refs/heads/foo", None, False),
            parse_reftuple(r, r, b"refs/heads/foo:"),
        )

    def test_default_with_string(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            (b"refs/heads/foo", b"refs/heads/foo", False),
            parse_reftuple(r, r, "foo"),
        )


class ParseReftuplesTests(TestCase):
    def test_nonexistent(self):
        r = {}
        self.assertRaises(KeyError, parse_reftuples, r, r, [b"thisdoesnotexist"])

    def test_head(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            [(b"refs/heads/foo", b"refs/heads/foo", False)],
            parse_reftuples(r, r, [b"foo"]),
        )

    def test_full(self):
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            [(b"refs/heads/foo", b"refs/heads/foo", False)],
            parse_reftuples(r, r, b"refs/heads/foo"),
        )
        r = {b"refs/heads/foo": "bla"}
        self.assertEqual(
            [(b"refs/heads/foo", b"refs/heads/foo", True)],
            parse_reftuples(r, r, b"refs/heads/foo", True),
        )


class ParseTreeTests(TestCase):
    """Test parse_tree."""

    def test_nonexistent(self):
        r = MemoryRepo()
        self.assertRaises(KeyError, parse_tree, r, "thisdoesnotexist")

    def test_from_commit(self):
        r = MemoryRepo()
        c1, c2, c3 = build_commit_graph(r.object_store, [[1], [2, 1], [3, 1, 2]])
        self.assertEqual(r[c1.tree], parse_tree(r, c1.id))
        self.assertEqual(r[c1.tree], parse_tree(r, c1.tree))

    def test_from_ref(self):
        r = MemoryRepo()
        c1, c2, c3 = build_commit_graph(r.object_store, [[1], [2, 1], [3, 1, 2]])
        r.refs[b'refs/heads/foo'] = c1.id
        self.assertEqual(r[c1.tree], parse_tree(r, b'foo'))
