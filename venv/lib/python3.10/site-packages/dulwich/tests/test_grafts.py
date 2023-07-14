# test_grafts.py -- Tests for graftpoints
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

"""Tests for graftpoints."""

import os
import shutil
import tempfile

from dulwich.tests import TestCase

from ..errors import ObjectFormatException
from ..objects import Tree
from ..repo import MemoryRepo, Repo, parse_graftpoints, serialize_graftpoints


def makesha(digit):
    return (str(digit).encode("ascii") * 40)[:40]


class GraftParserTests(TestCase):
    def assertParse(self, expected, graftpoints):
        self.assertEqual(expected, parse_graftpoints(iter(graftpoints)))

    def test_no_grafts(self):
        self.assertParse({}, [])

    def test_no_parents(self):
        self.assertParse({makesha(0): []}, [makesha(0)])

    def test_parents(self):
        self.assertParse(
            {makesha(0): [makesha(1), makesha(2)]},
            [b" ".join([makesha(0), makesha(1), makesha(2)])],
        )

    def test_multiple_hybrid(self):
        self.assertParse(
            {
                makesha(0): [],
                makesha(1): [makesha(2)],
                makesha(3): [makesha(4), makesha(5)],
            },
            [
                makesha(0),
                b" ".join([makesha(1), makesha(2)]),
                b" ".join([makesha(3), makesha(4), makesha(5)]),
            ],
        )


class GraftSerializerTests(TestCase):
    def assertSerialize(self, expected, graftpoints):
        self.assertEqual(sorted(expected), sorted(serialize_graftpoints(graftpoints)))

    def test_no_grafts(self):
        self.assertSerialize(b"", {})

    def test_no_parents(self):
        self.assertSerialize(makesha(0), {makesha(0): []})

    def test_parents(self):
        self.assertSerialize(
            b" ".join([makesha(0), makesha(1), makesha(2)]),
            {makesha(0): [makesha(1), makesha(2)]},
        )

    def test_multiple_hybrid(self):
        self.assertSerialize(
            b"\n".join(
                [
                    makesha(0),
                    b" ".join([makesha(1), makesha(2)]),
                    b" ".join([makesha(3), makesha(4), makesha(5)]),
                ]
            ),
            {
                makesha(0): [],
                makesha(1): [makesha(2)],
                makesha(3): [makesha(4), makesha(5)],
            },
        )


class GraftsInRepositoryBase:
    def tearDown(self):
        super().tearDown()

    def get_repo_with_grafts(self, grafts):
        r = self._repo
        r._add_graftpoints(grafts)
        return r

    def test_no_grafts(self):
        r = self.get_repo_with_grafts({})

        shas = [e.commit.id for e in r.get_walker()]
        self.assertEqual(shas, self._shas[::-1])

    def test_no_parents_graft(self):
        r = self.get_repo_with_grafts({self._repo.head(): []})

        self.assertEqual([e.commit.id for e in r.get_walker()], [r.head()])

    def test_existing_parent_graft(self):
        r = self.get_repo_with_grafts({self._shas[-1]: [self._shas[0]]})

        self.assertEqual(
            [e.commit.id for e in r.get_walker()],
            [self._shas[-1], self._shas[0]],
        )

    def test_remove_graft(self):
        r = self.get_repo_with_grafts({self._repo.head(): []})
        r._remove_graftpoints([self._repo.head()])

        self.assertEqual([e.commit.id for e in r.get_walker()], self._shas[::-1])

    def test_object_store_fail_invalid_parents(self):
        r = self._repo

        self.assertRaises(
            ObjectFormatException, r._add_graftpoints, {self._shas[-1]: ["1"]}
        )


class GraftsInRepoTests(GraftsInRepositoryBase, TestCase):
    def setUp(self):
        super().setUp()
        self._repo_dir = os.path.join(tempfile.mkdtemp())
        r = self._repo = Repo.init(self._repo_dir)
        self.addCleanup(shutil.rmtree, self._repo_dir)

        self._shas = []

        commit_kwargs = {
            "committer": b"Test Committer <test@nodomain.com>",
            "author": b"Test Author <test@nodomain.com>",
            "commit_timestamp": 12395,
            "commit_timezone": 0,
            "author_timestamp": 12395,
            "author_timezone": 0,
        }

        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))
        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))
        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))

    def test_init_with_empty_info_grafts(self):
        r = self._repo
        r._put_named_file(os.path.join("info", "grafts"), b"")

        r = Repo(self._repo_dir)
        self.assertEqual({}, r._graftpoints)

    def test_init_with_info_grafts(self):
        r = self._repo
        r._put_named_file(
            os.path.join("info", "grafts"),
            self._shas[-1] + b" " + self._shas[0],
        )

        r = Repo(self._repo_dir)
        self.assertEqual({self._shas[-1]: [self._shas[0]]}, r._graftpoints)


class GraftsInMemoryRepoTests(GraftsInRepositoryBase, TestCase):
    def setUp(self):
        super().setUp()
        r = self._repo = MemoryRepo()

        self._shas = []

        tree = Tree()

        commit_kwargs = {
            "committer": b"Test Committer <test@nodomain.com>",
            "author": b"Test Author <test@nodomain.com>",
            "commit_timestamp": 12395,
            "commit_timezone": 0,
            "author_timestamp": 12395,
            "author_timezone": 0,
            "tree": tree.id,
        }

        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))
        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))
        self._shas.append(r.do_commit(b"empty commit", **commit_kwargs))
