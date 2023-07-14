# test_refs.py -- tests for refs.py
# Copyright (C) 2013 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for dulwich.refs."""

import os
import sys
import tempfile
from io import BytesIO

from dulwich import errors
from dulwich.tests import SkipTest, TestCase

from ..file import GitFile
from ..objects import ZERO_SHA
from ..refs import (DictRefsContainer, InfoRefsContainer, SymrefLoop,
                    _split_ref_line, check_ref_format, parse_symref_value,
                    read_packed_refs, read_packed_refs_with_peeled,
                    strip_peeled_refs, write_packed_refs)
from ..repo import Repo
from .utils import open_repo, tear_down_repo


class CheckRefFormatTests(TestCase):
    """Tests for the check_ref_format function.

    These are the same tests as in the git test suite.
    """

    def test_valid(self):
        self.assertTrue(check_ref_format(b"heads/foo"))
        self.assertTrue(check_ref_format(b"foo/bar/baz"))
        self.assertTrue(check_ref_format(b"refs///heads/foo"))
        self.assertTrue(check_ref_format(b"foo./bar"))
        self.assertTrue(check_ref_format(b"heads/foo@bar"))
        self.assertTrue(check_ref_format(b"heads/fix.lock.error"))

    def test_invalid(self):
        self.assertFalse(check_ref_format(b"foo"))
        self.assertFalse(check_ref_format(b"heads/foo/"))
        self.assertFalse(check_ref_format(b"./foo"))
        self.assertFalse(check_ref_format(b".refs/foo"))
        self.assertFalse(check_ref_format(b"heads/foo..bar"))
        self.assertFalse(check_ref_format(b"heads/foo?bar"))
        self.assertFalse(check_ref_format(b"heads/foo.lock"))
        self.assertFalse(check_ref_format(b"heads/v@{ation"))
        self.assertFalse(check_ref_format(b"heads/foo\bar"))


ONES = b"1" * 40
TWOS = b"2" * 40
THREES = b"3" * 40
FOURS = b"4" * 40


class PackedRefsFileTests(TestCase):
    def test_split_ref_line_errors(self):
        self.assertRaises(errors.PackedRefsException, _split_ref_line, b"singlefield")
        self.assertRaises(errors.PackedRefsException, _split_ref_line, b"badsha name")
        self.assertRaises(
            errors.PackedRefsException,
            _split_ref_line,
            ONES + b" bad/../refname",
        )

    def test_read_without_peeled(self):
        f = BytesIO(b"\n".join([b"# comment", ONES + b" ref/1", TWOS + b" ref/2"]))
        self.assertEqual(
            [(ONES, b"ref/1"), (TWOS, b"ref/2")], list(read_packed_refs(f))
        )

    def test_read_without_peeled_errors(self):
        f = BytesIO(b"\n".join([ONES + b" ref/1", b"^" + TWOS]))
        self.assertRaises(errors.PackedRefsException, list, read_packed_refs(f))

    def test_read_with_peeled(self):
        f = BytesIO(
            b"\n".join(
                [
                    ONES + b" ref/1",
                    TWOS + b" ref/2",
                    b"^" + THREES,
                    FOURS + b" ref/4",
                ]
            )
        )
        self.assertEqual(
            [
                (ONES, b"ref/1", None),
                (TWOS, b"ref/2", THREES),
                (FOURS, b"ref/4", None),
            ],
            list(read_packed_refs_with_peeled(f)),
        )

    def test_read_with_peeled_errors(self):
        f = BytesIO(b"\n".join([b"^" + TWOS, ONES + b" ref/1"]))
        self.assertRaises(errors.PackedRefsException, list, read_packed_refs(f))

        f = BytesIO(b"\n".join([ONES + b" ref/1", b"^" + TWOS, b"^" + THREES]))
        self.assertRaises(errors.PackedRefsException, list, read_packed_refs(f))

    def test_write_with_peeled(self):
        f = BytesIO()
        write_packed_refs(f, {b"ref/1": ONES, b"ref/2": TWOS}, {b"ref/1": THREES})
        self.assertEqual(
            b"\n".join(
                [
                    b"# pack-refs with: peeled",
                    ONES + b" ref/1",
                    b"^" + THREES,
                    TWOS + b" ref/2",
                ]
            )
            + b"\n",
            f.getvalue(),
        )

    def test_write_without_peeled(self):
        f = BytesIO()
        write_packed_refs(f, {b"ref/1": ONES, b"ref/2": TWOS})
        self.assertEqual(
            b"\n".join([ONES + b" ref/1", TWOS + b" ref/2"]) + b"\n",
            f.getvalue(),
        )


# Dict of refs that we expect all RefsContainerTests subclasses to define.
_TEST_REFS = {
    b"HEAD": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
    b"refs/heads/40-char-ref-aaaaaaaaaaaaaaaaaa": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
    b"refs/heads/master": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
    b"refs/heads/packed": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
    b"refs/tags/refs-0.1": b"df6800012397fb85c56e7418dd4eb9405dee075c",
    b"refs/tags/refs-0.2": b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8",
    b"refs/heads/loop": b"ref: refs/heads/loop",
}


class RefsContainerTests:
    def test_keys(self):
        actual_keys = set(self._refs.keys())
        self.assertEqual(set(self._refs.allkeys()), actual_keys)
        self.assertEqual(set(_TEST_REFS.keys()), actual_keys)

        actual_keys = self._refs.keys(b"refs/heads")
        actual_keys.discard(b"loop")
        self.assertEqual(
            [b"40-char-ref-aaaaaaaaaaaaaaaaaa", b"master", b"packed"],
            sorted(actual_keys),
        )
        self.assertEqual(
            [b"refs-0.1", b"refs-0.2"], sorted(self._refs.keys(b"refs/tags"))
        )

    def test_iter(self):
        actual_keys = set(self._refs.keys())
        self.assertEqual(set(self._refs), actual_keys)
        self.assertEqual(set(_TEST_REFS.keys()), actual_keys)

    def test_as_dict(self):
        # refs/heads/loop does not show up even if it exists
        expected_refs = dict(_TEST_REFS)
        del expected_refs[b"refs/heads/loop"]
        self.assertEqual(expected_refs, self._refs.as_dict())

    def test_get_symrefs(self):
        self._refs.set_symbolic_ref(b"refs/heads/src", b"refs/heads/dst")
        symrefs = self._refs.get_symrefs()
        if b"HEAD" in symrefs:
            symrefs.pop(b"HEAD")
        self.assertEqual(
            {
                b"refs/heads/src": b"refs/heads/dst",
                b"refs/heads/loop": b"refs/heads/loop",
            },
            symrefs,
        )

    def test_setitem(self):
        self._refs[b"refs/some/ref"] = b"42d06bd4b77fed026b154d16493e5deab78f02ec"
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/some/ref"],
        )
        self.assertRaises(
            errors.RefFormatError,
            self._refs.__setitem__,
            b"notrefs/foo",
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
        )

    def test_set_if_equals(self):
        nines = b"9" * 40
        self.assertFalse(self._refs.set_if_equals(b"HEAD", b"c0ffee", nines))
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec", self._refs[b"HEAD"]
        )

        self.assertTrue(
            self._refs.set_if_equals(
                b"HEAD", b"42d06bd4b77fed026b154d16493e5deab78f02ec", nines
            )
        )
        self.assertEqual(nines, self._refs[b"HEAD"])

        # Setting the ref again is a no-op, but will return True.
        self.assertTrue(self._refs.set_if_equals(b"HEAD", nines, nines))
        self.assertEqual(nines, self._refs[b"HEAD"])

        self.assertTrue(self._refs.set_if_equals(b"refs/heads/master", None, nines))
        self.assertEqual(nines, self._refs[b"refs/heads/master"])

        self.assertTrue(
            self._refs.set_if_equals(b"refs/heads/nonexistent", ZERO_SHA, nines)
        )
        self.assertEqual(nines, self._refs[b"refs/heads/nonexistent"])

    def test_add_if_new(self):
        nines = b"9" * 40
        self.assertFalse(self._refs.add_if_new(b"refs/heads/master", nines))
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/heads/master"],
        )

        self.assertTrue(self._refs.add_if_new(b"refs/some/ref", nines))
        self.assertEqual(nines, self._refs[b"refs/some/ref"])

    def test_set_symbolic_ref(self):
        self._refs.set_symbolic_ref(b"refs/heads/symbolic", b"refs/heads/master")
        self.assertEqual(
            b"ref: refs/heads/master",
            self._refs.read_loose_ref(b"refs/heads/symbolic"),
        )
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/heads/symbolic"],
        )

    def test_set_symbolic_ref_overwrite(self):
        nines = b"9" * 40
        self.assertNotIn(b"refs/heads/symbolic", self._refs)
        self._refs[b"refs/heads/symbolic"] = nines
        self.assertEqual(nines, self._refs.read_loose_ref(b"refs/heads/symbolic"))
        self._refs.set_symbolic_ref(b"refs/heads/symbolic", b"refs/heads/master")
        self.assertEqual(
            b"ref: refs/heads/master",
            self._refs.read_loose_ref(b"refs/heads/symbolic"),
        )
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/heads/symbolic"],
        )

    def test_check_refname(self):
        self._refs._check_refname(b"HEAD")
        self._refs._check_refname(b"refs/stash")
        self._refs._check_refname(b"refs/heads/foo")

        self.assertRaises(errors.RefFormatError, self._refs._check_refname, b"refs")
        self.assertRaises(
            errors.RefFormatError, self._refs._check_refname, b"notrefs/foo"
        )

    def test_contains(self):
        self.assertIn(b"refs/heads/master", self._refs)
        self.assertNotIn(b"refs/heads/bar", self._refs)

    def test_delitem(self):
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/heads/master"],
        )
        del self._refs[b"refs/heads/master"]
        self.assertRaises(KeyError, lambda: self._refs[b"refs/heads/master"])

    def test_remove_if_equals(self):
        self.assertFalse(self._refs.remove_if_equals(b"HEAD", b"c0ffee"))
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec", self._refs[b"HEAD"]
        )
        self.assertTrue(
            self._refs.remove_if_equals(
                b"refs/tags/refs-0.2",
                b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8",
            )
        )
        self.assertTrue(self._refs.remove_if_equals(b"refs/tags/refs-0.2", ZERO_SHA))
        self.assertNotIn(b"refs/tags/refs-0.2", self._refs)

    def test_import_refs_name(self):
        self._refs[
            b"refs/remotes/origin/other"
        ] = b"48d01bd4b77fed026b154d16493e5deab78f02ec"
        self._refs.import_refs(
            b"refs/remotes/origin",
            {b"master": b"42d06bd4b77fed026b154d16493e5deab78f02ec"},
        )
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/remotes/origin/master"],
        )
        self.assertEqual(
            b"48d01bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/remotes/origin/other"],
        )

    def test_import_refs_name_prune(self):
        self._refs[
            b"refs/remotes/origin/other"
        ] = b"48d01bd4b77fed026b154d16493e5deab78f02ec"
        self._refs.import_refs(
            b"refs/remotes/origin",
            {b"master": b"42d06bd4b77fed026b154d16493e5deab78f02ec"},
            prune=True,
        )
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/remotes/origin/master"],
        )
        self.assertNotIn(b"refs/remotes/origin/other", self._refs)


class DictRefsContainerTests(RefsContainerTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self._refs = DictRefsContainer(dict(_TEST_REFS))

    def test_invalid_refname(self):
        # FIXME: Move this test into RefsContainerTests, but requires
        # some way of injecting invalid refs.
        self._refs._refs[b"refs/stash"] = b"00" * 20
        expected_refs = dict(_TEST_REFS)
        del expected_refs[b"refs/heads/loop"]
        expected_refs[b"refs/stash"] = b"00" * 20
        self.assertEqual(expected_refs, self._refs.as_dict())


class DiskRefsContainerTests(RefsContainerTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self._repo = open_repo("refs.git")
        self.addCleanup(tear_down_repo, self._repo)
        self._refs = self._repo.refs

    def test_get_packed_refs(self):
        self.assertEqual(
            {
                b"refs/heads/packed": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
                b"refs/tags/refs-0.1": b"df6800012397fb85c56e7418dd4eb9405dee075c",
            },
            self._refs.get_packed_refs(),
        )

    def test_get_peeled_not_packed(self):
        # not packed
        self.assertEqual(None, self._refs.get_peeled(b"refs/tags/refs-0.2"))
        self.assertEqual(
            b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8",
            self._refs[b"refs/tags/refs-0.2"],
        )

        # packed, known not peelable
        self.assertEqual(
            self._refs[b"refs/heads/packed"],
            self._refs.get_peeled(b"refs/heads/packed"),
        )

        # packed, peeled
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs.get_peeled(b"refs/tags/refs-0.1"),
        )

    def test_setitem(self):
        RefsContainerTests.test_setitem(self)
        path = os.path.join(self._refs.path, b"refs", b"some", b"ref")
        with open(path, "rb") as f:
            self.assertEqual(b"42d06bd4b77fed026b154d16493e5deab78f02ec", f.read()[:40])

        self.assertRaises(
            OSError,
            self._refs.__setitem__,
            b"refs/some/ref/sub",
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
        )

    def test_delete_refs_container(self):
        # We shouldn't delete the refs directory
        self._refs[b'refs/heads/blah'] = b"42d06bd4b77fed026b154d16493e5deab78f02ec"
        for ref in self._refs.allkeys():
            del self._refs[ref]
        self.assertTrue(os.path.exists(os.path.join(self._refs.path, b'refs')))

    def test_setitem_packed(self):
        with open(os.path.join(self._refs.path, b"packed-refs"), "w") as f:
            f.write("# pack-refs with: peeled fully-peeled sorted \n")
            f.write("42d06bd4b77fed026b154d16493e5deab78f02ec refs/heads/packed\n")

        # It's allowed to set a new ref on a packed ref, the new ref will be
        # placed outside on refs/
        self._refs[b"refs/heads/packed"] = b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8"
        packed_ref_path = os.path.join(self._refs.path, b"refs", b"heads", b"packed")
        with open(packed_ref_path, "rb") as f:
            self.assertEqual(b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8", f.read()[:40])

        self.assertRaises(
            OSError,
            self._refs.__setitem__,
            b"refs/heads/packed/sub",
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
        )

        # this shouldn't overwrite the packed refs
        self.assertEqual(
            {b"refs/heads/packed": b"42d06bd4b77fed026b154d16493e5deab78f02ec"},
            self._refs.get_packed_refs(),
        )

    def test_add_packed_refs(self):
        # first, create a non-packed ref
        self._refs[b"refs/heads/packed"] = b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8"

        packed_ref_path = os.path.join(self._refs.path, b"refs", b"heads", b"packed")
        self.assertTrue(os.path.exists(packed_ref_path))

        # now overwrite that with a packed ref
        packed_refs_file_path = os.path.join(self._refs.path, b"packed-refs")
        self._refs.add_packed_refs(
            {
                b"refs/heads/packed": b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            }
        )

        # that should kill the file
        self.assertFalse(os.path.exists(packed_ref_path))

        # now delete the packed ref
        self._refs.add_packed_refs(
            {
                b"refs/heads/packed": None,
            }
        )

        # and it's gone!
        self.assertFalse(os.path.exists(packed_ref_path))

        self.assertRaises(
            KeyError,
            self._refs.__getitem__,
            b"refs/heads/packed",
        )

        # just in case, make sure we can't pack HEAD
        self.assertRaises(
            ValueError,
            self._refs.add_packed_refs,
            {b"HEAD": "02ac81614bcdbd585a37b4b0edf8cb8a"},
        )

        # delete all packed refs
        self._refs.add_packed_refs({ref: None for ref in self._refs.get_packed_refs()})

        self.assertEqual({}, self._refs.get_packed_refs())

        # remove the packed ref file, and check that adding nothing doesn't affect that
        os.remove(packed_refs_file_path)

        # adding nothing doesn't make it reappear
        self._refs.add_packed_refs({})

        self.assertFalse(os.path.exists(packed_refs_file_path))

    def test_setitem_symbolic(self):
        ones = b"1" * 40
        self._refs[b"HEAD"] = ones
        self.assertEqual(ones, self._refs[b"HEAD"])

        # ensure HEAD was not modified
        f = open(os.path.join(self._refs.path, b"HEAD"), "rb")
        v = next(iter(f)).rstrip(b"\n\r")
        f.close()
        self.assertEqual(b"ref: refs/heads/master", v)

        # ensure the symbolic link was written through
        f = open(os.path.join(self._refs.path, b"refs", b"heads", b"master"), "rb")
        self.assertEqual(ones, f.read()[:40])
        f.close()

    def test_set_if_equals(self):
        RefsContainerTests.test_set_if_equals(self)

        # ensure symref was followed
        self.assertEqual(b"9" * 40, self._refs[b"refs/heads/master"])

        # ensure lockfile was deleted
        self.assertFalse(
            os.path.exists(
                os.path.join(self._refs.path, b"refs", b"heads", b"master.lock")
            )
        )
        self.assertFalse(os.path.exists(os.path.join(self._refs.path, b"HEAD.lock")))

    def test_add_if_new_packed(self):
        # don't overwrite packed ref
        self.assertFalse(self._refs.add_if_new(b"refs/tags/refs-0.1", b"9" * 40))
        self.assertEqual(
            b"df6800012397fb85c56e7418dd4eb9405dee075c",
            self._refs[b"refs/tags/refs-0.1"],
        )

    def test_add_if_new_symbolic(self):
        # Use an empty repo instead of the default.
        repo_dir = os.path.join(tempfile.mkdtemp(), "test")
        os.makedirs(repo_dir)
        repo = Repo.init(repo_dir)
        self.addCleanup(tear_down_repo, repo)
        refs = repo.refs

        nines = b"9" * 40
        self.assertEqual(b"ref: refs/heads/master", refs.read_ref(b"HEAD"))
        self.assertNotIn(b"refs/heads/master", refs)
        self.assertTrue(refs.add_if_new(b"HEAD", nines))
        self.assertEqual(b"ref: refs/heads/master", refs.read_ref(b"HEAD"))
        self.assertEqual(nines, refs[b"HEAD"])
        self.assertEqual(nines, refs[b"refs/heads/master"])
        self.assertFalse(refs.add_if_new(b"HEAD", b"1" * 40))
        self.assertEqual(nines, refs[b"HEAD"])
        self.assertEqual(nines, refs[b"refs/heads/master"])

    def test_follow(self):
        self.assertEqual(
            (
                [b"HEAD", b"refs/heads/master"],
                b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            ),
            self._refs.follow(b"HEAD"),
        )
        self.assertEqual(
            (
                [b"refs/heads/master"],
                b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            ),
            self._refs.follow(b"refs/heads/master"),
        )
        self.assertRaises(SymrefLoop, self._refs.follow, b"refs/heads/loop")

    def test_set_overwrite_loop(self):
        self.assertRaises(SymrefLoop, self._refs.follow, b"refs/heads/loop")
        self._refs[b'refs/heads/loop'] = (
            b"42d06bd4b77fed026b154d16493e5deab78f02ec")
        self.assertEqual(
            ([b'refs/heads/loop'], b'42d06bd4b77fed026b154d16493e5deab78f02ec'),
            self._refs.follow(b"refs/heads/loop"))

    def test_delitem(self):
        RefsContainerTests.test_delitem(self)
        ref_file = os.path.join(self._refs.path, b"refs", b"heads", b"master")
        self.assertFalse(os.path.exists(ref_file))
        self.assertNotIn(b"refs/heads/master", self._refs.get_packed_refs())

    def test_delitem_symbolic(self):
        self.assertEqual(b"ref: refs/heads/master", self._refs.read_loose_ref(b"HEAD"))
        del self._refs[b"HEAD"]
        self.assertRaises(KeyError, lambda: self._refs[b"HEAD"])
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs[b"refs/heads/master"],
        )
        self.assertFalse(os.path.exists(os.path.join(self._refs.path, b"HEAD")))

    def test_remove_if_equals_symref(self):
        # HEAD is a symref, so shouldn't equal its dereferenced value
        self.assertFalse(
            self._refs.remove_if_equals(
                b"HEAD", b"42d06bd4b77fed026b154d16493e5deab78f02ec"
            )
        )
        self.assertTrue(
            self._refs.remove_if_equals(
                b"refs/heads/master",
                b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            )
        )
        self.assertRaises(KeyError, lambda: self._refs[b"refs/heads/master"])

        # HEAD is now a broken symref
        self.assertRaises(KeyError, lambda: self._refs[b"HEAD"])
        self.assertEqual(b"ref: refs/heads/master", self._refs.read_loose_ref(b"HEAD"))

        self.assertFalse(
            os.path.exists(
                os.path.join(self._refs.path, b"refs", b"heads", b"master.lock")
            )
        )
        self.assertFalse(os.path.exists(os.path.join(self._refs.path, b"HEAD.lock")))

    def test_remove_packed_without_peeled(self):
        refs_file = os.path.join(self._repo.path, "packed-refs")
        f = GitFile(refs_file)
        refs_data = f.read()
        f.close()
        f = GitFile(refs_file, "wb")
        f.write(
            b"\n".join(
                line
                for line in refs_data.split(b"\n")
                if not line or line[0] not in b"#^"
            )
        )
        f.close()
        self._repo = Repo(self._repo.path)
        refs = self._repo.refs
        self.assertTrue(
            refs.remove_if_equals(
                b"refs/heads/packed",
                b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            )
        )

    def test_remove_if_equals_packed(self):
        # test removing ref that is only packed
        self.assertEqual(
            b"df6800012397fb85c56e7418dd4eb9405dee075c",
            self._refs[b"refs/tags/refs-0.1"],
        )
        self.assertTrue(
            self._refs.remove_if_equals(
                b"refs/tags/refs-0.1",
                b"df6800012397fb85c56e7418dd4eb9405dee075c",
            )
        )
        self.assertRaises(KeyError, lambda: self._refs[b"refs/tags/refs-0.1"])

    def test_remove_parent(self):
        self._refs[b"refs/heads/foo/bar"] = b"df6800012397fb85c56e7418dd4eb9405dee075c"
        del self._refs[b"refs/heads/foo/bar"]
        ref_file = os.path.join(
            self._refs.path,
            b"refs",
            b"heads",
            b"foo",
            b"bar",
        )
        self.assertFalse(os.path.exists(ref_file))
        ref_file = os.path.join(self._refs.path, b"refs", b"heads", b"foo")
        self.assertFalse(os.path.exists(ref_file))
        ref_file = os.path.join(self._refs.path, b"refs", b"heads")
        self.assertTrue(os.path.exists(ref_file))
        self._refs[b"refs/heads/foo"] = b"df6800012397fb85c56e7418dd4eb9405dee075c"

    def test_read_ref(self):
        self.assertEqual(b"ref: refs/heads/master", self._refs.read_ref(b"HEAD"))
        self.assertEqual(
            b"42d06bd4b77fed026b154d16493e5deab78f02ec",
            self._refs.read_ref(b"refs/heads/packed"),
        )
        self.assertEqual(None, self._refs.read_ref(b"nonexistent"))

    def test_read_loose_ref(self):
        self._refs[b"refs/heads/foo"] = b"df6800012397fb85c56e7418dd4eb9405dee075c"

        self.assertEqual(None, self._refs.read_ref(b"refs/heads/foo/bar"))

    def test_non_ascii(self):
        try:
            encoded_ref = os.fsencode("refs/tags/schön")
        except UnicodeEncodeError as exc:
            raise SkipTest(
                "filesystem encoding doesn't support special character"
            ) from exc
        p = os.path.join(os.fsencode(self._repo.path), encoded_ref)
        with open(p, "w") as f:
            f.write("00" * 20)

        expected_refs = dict(_TEST_REFS)
        expected_refs[encoded_ref] = b"00" * 20
        del expected_refs[b"refs/heads/loop"]

        self.assertEqual(expected_refs, self._repo.get_refs())

    def test_cyrillic(self):
        if sys.platform in ("darwin", "win32"):
            raise SkipTest("filesystem encoding doesn't support arbitrary bytes")
        # reported in https://github.com/dulwich/dulwich/issues/608
        name = b"\xcd\xee\xe2\xe0\xff\xe2\xe5\xf2\xea\xe01"
        encoded_ref = b"refs/heads/" + name
        with open(os.path.join(os.fsencode(self._repo.path), encoded_ref), "w") as f:
            f.write("00" * 20)

        expected_refs = set(_TEST_REFS.keys())
        expected_refs.add(encoded_ref)

        self.assertEqual(expected_refs, set(self._repo.refs.allkeys()))
        self.assertEqual(
            {r[len(b"refs/") :] for r in expected_refs if r.startswith(b"refs/")},
            set(self._repo.refs.subkeys(b"refs/")),
        )
        expected_refs.remove(b"refs/heads/loop")
        expected_refs.add(b"HEAD")
        self.assertEqual(expected_refs, set(self._repo.get_refs().keys()))


_TEST_REFS_SERIALIZED = (
    b"42d06bd4b77fed026b154d16493e5deab78f02ec\t"
    b"refs/heads/40-char-ref-aaaaaaaaaaaaaaaaaa\n"
    b"42d06bd4b77fed026b154d16493e5deab78f02ec\trefs/heads/master\n"
    b"42d06bd4b77fed026b154d16493e5deab78f02ec\trefs/heads/packed\n"
    b"df6800012397fb85c56e7418dd4eb9405dee075c\trefs/tags/refs-0.1\n"
    b"3ec9c43c84ff242e3ef4a9fc5bc111fd780a76a8\trefs/tags/refs-0.2\n"
)


class InfoRefsContainerTests(TestCase):
    def test_invalid_refname(self):
        text = _TEST_REFS_SERIALIZED + b"00" * 20 + b"\trefs/stash\n"
        refs = InfoRefsContainer(BytesIO(text))
        expected_refs = dict(_TEST_REFS)
        del expected_refs[b"HEAD"]
        expected_refs[b"refs/stash"] = b"00" * 20
        del expected_refs[b"refs/heads/loop"]
        self.assertEqual(expected_refs, refs.as_dict())

    def test_keys(self):
        refs = InfoRefsContainer(BytesIO(_TEST_REFS_SERIALIZED))
        actual_keys = set(refs.keys())
        self.assertEqual(set(refs.allkeys()), actual_keys)
        expected_refs = dict(_TEST_REFS)
        del expected_refs[b"HEAD"]
        del expected_refs[b"refs/heads/loop"]
        self.assertEqual(set(expected_refs.keys()), actual_keys)

        actual_keys = refs.keys(b"refs/heads")
        actual_keys.discard(b"loop")
        self.assertEqual(
            [b"40-char-ref-aaaaaaaaaaaaaaaaaa", b"master", b"packed"],
            sorted(actual_keys),
        )
        self.assertEqual([b"refs-0.1", b"refs-0.2"], sorted(refs.keys(b"refs/tags")))

    def test_as_dict(self):
        refs = InfoRefsContainer(BytesIO(_TEST_REFS_SERIALIZED))
        # refs/heads/loop does not show up even if it exists
        expected_refs = dict(_TEST_REFS)
        del expected_refs[b"HEAD"]
        del expected_refs[b"refs/heads/loop"]
        self.assertEqual(expected_refs, refs.as_dict())

    def test_contains(self):
        refs = InfoRefsContainer(BytesIO(_TEST_REFS_SERIALIZED))
        self.assertIn(b"refs/heads/master", refs)
        self.assertNotIn(b"refs/heads/bar", refs)

    def test_get_peeled(self):
        refs = InfoRefsContainer(BytesIO(_TEST_REFS_SERIALIZED))
        # refs/heads/loop does not show up even if it exists
        self.assertEqual(
            _TEST_REFS[b"refs/heads/master"],
            refs.get_peeled(b"refs/heads/master"),
        )


class ParseSymrefValueTests(TestCase):
    def test_valid(self):
        self.assertEqual(b"refs/heads/foo", parse_symref_value(b"ref: refs/heads/foo"))

    def test_invalid(self):
        self.assertRaises(ValueError, parse_symref_value, b"foobar")


class StripPeeledRefsTests(TestCase):

    all_refs = {
        b"refs/heads/master": b"8843d7f92416211de9ebb963ff4ce28125932878",
        b"refs/heads/testing": b"186a005b134d8639a58b6731c7c1ea821a6eedba",
        b"refs/tags/1.0.0": b"a93db4b0360cc635a2b93675010bac8d101f73f0",
        b"refs/tags/1.0.0^{}": b"a93db4b0360cc635a2b93675010bac8d101f73f0",
        b"refs/tags/2.0.0": b"0749936d0956c661ac8f8d3483774509c165f89e",
        b"refs/tags/2.0.0^{}": b"0749936d0956c661ac8f8d3483774509c165f89e",
    }
    non_peeled_refs = {
        b"refs/heads/master": b"8843d7f92416211de9ebb963ff4ce28125932878",
        b"refs/heads/testing": b"186a005b134d8639a58b6731c7c1ea821a6eedba",
        b"refs/tags/1.0.0": b"a93db4b0360cc635a2b93675010bac8d101f73f0",
        b"refs/tags/2.0.0": b"0749936d0956c661ac8f8d3483774509c165f89e",
    }

    def test_strip_peeled_refs(self):
        # Simple check of two dicts
        self.assertEqual(strip_peeled_refs(self.all_refs), self.non_peeled_refs)
