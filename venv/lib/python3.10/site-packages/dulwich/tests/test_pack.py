# test_pack.py -- Tests for the handling of git packs.
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
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

"""Tests for Dulwich packs."""


import os
import shutil
import sys
import tempfile
import zlib
from hashlib import sha1
from io import BytesIO

from dulwich.tests import TestCase

from ..errors import ApplyDeltaError, ChecksumMismatch
from ..file import GitFile
from ..object_store import MemoryObjectStore
from ..objects import Blob, Commit, Tree, hex_to_sha, sha_to_hex
from ..pack import (OFS_DELTA, REF_DELTA, DeltaChainIterator, MemoryPackIndex,
                    Pack, PackData, PackStreamReader, UnpackedObject,
                    _delta_encode_size, _encode_copy_operation, apply_delta,
                    compute_file_sha, create_delta, deltify_pack_objects,
                    load_pack_index, read_zlib_chunks, unpack_object,
                    write_pack, write_pack_header, write_pack_index_v1,
                    write_pack_index_v2, write_pack_object)
from .utils import build_pack, make_object

pack1_sha = b"bc63ddad95e7321ee734ea11a7a62d314e0d7481"

a_sha = b"6f670c0fb53f9463760b7295fbb814e965fb20c8"
tree_sha = b"b2a2766a2879c209ab1176e7e778b81ae422eeaa"
commit_sha = b"f18faa16531ac570a3fdc8c7ca16682548dafd12"
indexmode = "0o100644" if sys.platform != "win32" else "0o100666"


class PackTests(TestCase):
    """Base class for testing packs"""

    def setUp(self):
        super().setUp()
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir)

    datadir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../testdata/packs"))

    def get_pack_index(self, sha):
        """Returns a PackIndex from the datadir with the given sha"""
        return load_pack_index(
            os.path.join(self.datadir, "pack-%s.idx" % sha.decode("ascii"))
        )

    def get_pack_data(self, sha):
        """Returns a PackData object from the datadir with the given sha"""
        return PackData(
            os.path.join(self.datadir, "pack-%s.pack" % sha.decode("ascii"))
        )

    def get_pack(self, sha):
        return Pack(os.path.join(self.datadir, "pack-%s" % sha.decode("ascii")))

    def assertSucceeds(self, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except ChecksumMismatch as e:
            self.fail(e)


class PackIndexTests(PackTests):
    """Class that tests the index of packfiles"""

    def test_object_offset(self):
        """Tests that the correct object offset is returned from the index."""
        p = self.get_pack_index(pack1_sha)
        self.assertRaises(KeyError, p.object_offset, pack1_sha)
        self.assertEqual(p.object_offset(a_sha), 178)
        self.assertEqual(p.object_offset(tree_sha), 138)
        self.assertEqual(p.object_offset(commit_sha), 12)

    def test_object_sha1(self):
        """Tests that the correct object offset is returned from the index."""
        p = self.get_pack_index(pack1_sha)
        self.assertRaises(KeyError, p.object_sha1, 876)
        self.assertEqual(p.object_sha1(178), hex_to_sha(a_sha))
        self.assertEqual(p.object_sha1(138), hex_to_sha(tree_sha))
        self.assertEqual(p.object_sha1(12), hex_to_sha(commit_sha))

    def test_index_len(self):
        p = self.get_pack_index(pack1_sha)
        self.assertEqual(3, len(p))

    def test_get_stored_checksum(self):
        p = self.get_pack_index(pack1_sha)
        self.assertEqual(
            b"f2848e2ad16f329ae1c92e3b95e91888daa5bd01",
            sha_to_hex(p.get_stored_checksum()),
        )
        self.assertEqual(
            b"721980e866af9a5f93ad674144e1459b8ba3e7b7",
            sha_to_hex(p.get_pack_checksum()),
        )

    def test_index_check(self):
        p = self.get_pack_index(pack1_sha)
        self.assertSucceeds(p.check)

    def test_iterentries(self):
        p = self.get_pack_index(pack1_sha)
        entries = [(sha_to_hex(s), o, c) for s, o, c in p.iterentries()]
        self.assertEqual(
            [
                (b"6f670c0fb53f9463760b7295fbb814e965fb20c8", 178, None),
                (b"b2a2766a2879c209ab1176e7e778b81ae422eeaa", 138, None),
                (b"f18faa16531ac570a3fdc8c7ca16682548dafd12", 12, None),
            ],
            entries,
        )

    def test_iter(self):
        p = self.get_pack_index(pack1_sha)
        self.assertEqual({tree_sha, commit_sha, a_sha}, set(p))


class TestPackDeltas(TestCase):

    test_string1 = b"The answer was flailing in the wind"
    test_string2 = b"The answer was falling down the pipe"
    test_string3 = b"zzzzz"

    test_string_empty = b""
    test_string_big = b"Z" * 8192
    test_string_huge = b"Z" * 100000

    def _test_roundtrip(self, base, target):
        self.assertEqual(
            target,
            b"".join(apply_delta(base, list(create_delta(base, target))))
        )

    def test_nochange(self):
        self._test_roundtrip(self.test_string1, self.test_string1)

    def test_nochange_huge(self):
        self._test_roundtrip(self.test_string_huge, self.test_string_huge)

    def test_change(self):
        self._test_roundtrip(self.test_string1, self.test_string2)

    def test_rewrite(self):
        self._test_roundtrip(self.test_string1, self.test_string3)

    def test_empty_to_big(self):
        self._test_roundtrip(self.test_string_empty, self.test_string_big)

    def test_empty_to_huge(self):
        self._test_roundtrip(self.test_string_empty, self.test_string_huge)

    def test_huge_copy(self):
        self._test_roundtrip(
            self.test_string_huge + self.test_string1,
            self.test_string_huge + self.test_string2,
        )

    def test_dest_overflow(self):
        self.assertRaises(
            ApplyDeltaError,
            apply_delta,
            b"a" * 0x10000,
            b"\x80\x80\x04\x80\x80\x04\x80" + b"a" * 0x10000,
        )
        self.assertRaises(
            ApplyDeltaError, apply_delta, b"", b"\x00\x80\x02\xb0\x11\x11"
        )

    def test_pypy_issue(self):
        # Test for https://github.com/jelmer/dulwich/issues/509 /
        # https://bitbucket.org/pypy/pypy/issues/2499/cpyext-pystring_asstring-doesnt-work
        chunks = [
            b"tree 03207ccf58880a748188836155ceed72f03d65d6\n"
            b"parent 408fbab530fd4abe49249a636a10f10f44d07a21\n"
            b"author Victor Stinner <victor.stinner@gmail.com> "
            b"1421355207 +0100\n"
            b"committer Victor Stinner <victor.stinner@gmail.com> "
            b"1421355207 +0100\n"
            b"\n"
            b"Backout changeset 3a06020af8cf\n"
            b"\nStreamWriter: close() now clears the reference to the "
            b"transport\n"
            b"\nStreamWriter now raises an exception if it is closed: "
            b"write(), writelines(),\n"
            b"write_eof(), can_write_eof(), get_extra_info(), drain().\n"
        ]
        delta = [
            b"\xcd\x03\xad\x03]tree ff3c181a393d5a7270cddc01ea863818a8621ca8\n"
            b"parent 20a103cc90135494162e819f98d0edfc1f1fba6b\x91]7\x0510738"
            b"\x91\x99@\x0b10738 +0100\x93\x04\x01\xc9"
        ]
        res = apply_delta(chunks, delta)
        expected = [
            b"tree ff3c181a393d5a7270cddc01ea863818a8621ca8\n"
            b"parent 20a103cc90135494162e819f98d0edfc1f1fba6b",
            b"\nauthor Victor Stinner <victor.stinner@gmail.com> 14213",
            b"10738",
            b" +0100\ncommitter Victor Stinner <victor.stinner@gmail.com> " b"14213",
            b"10738 +0100",
            b"\n\nStreamWriter: close() now clears the reference to the "
            b"transport\n\n"
            b"StreamWriter now raises an exception if it is closed: "
            b"write(), writelines(),\n"
            b"write_eof(), can_write_eof(), get_extra_info(), drain().\n",
        ]
        self.assertEqual(b"".join(expected), b"".join(res))


class TestPackData(PackTests):
    """Tests getting the data from the packfile."""

    def test_create_pack(self):
        self.get_pack_data(pack1_sha).close()

    def test_from_file(self):
        path = os.path.join(self.datadir, "pack-%s.pack" % pack1_sha.decode("ascii"))
        with open(path, "rb") as f:
            PackData.from_file(f, os.path.getsize(path))

    def test_pack_len(self):
        with self.get_pack_data(pack1_sha) as p:
            self.assertEqual(3, len(p))

    def test_index_check(self):
        with self.get_pack_data(pack1_sha) as p:
            self.assertSucceeds(p.check)

    def test_iter_unpacked(self):
        with self.get_pack_data(pack1_sha) as p:
            commit_data = (
                b"tree b2a2766a2879c209ab1176e7e778b81ae422eeaa\n"
                b"author James Westby <jw+debian@jameswestby.net> "
                b"1174945067 +0100\n"
                b"committer James Westby <jw+debian@jameswestby.net> "
                b"1174945067 +0100\n"
                b"\n"
                b"Test commit\n"
            )
            blob_sha = b"6f670c0fb53f9463760b7295fbb814e965fb20c8"
            tree_data = b"100644 a\0" + hex_to_sha(blob_sha)
            actual = list(p.iter_unpacked())
            self.assertEqual(
                [
                    UnpackedObject(offset=12, pack_type_num=1, decomp_chunks=[commit_data], crc32=None),
                    UnpackedObject(offset=138, pack_type_num=2, decomp_chunks=[tree_data], crc32=None),
                    UnpackedObject(offset=178, pack_type_num=3, decomp_chunks=[b"test 1\n"], crc32=None),
                ],
                actual,
            )

    def test_iterentries(self):
        with self.get_pack_data(pack1_sha) as p:
            entries = {(sha_to_hex(s), o, c) for s, o, c in p.iterentries()}
            self.assertEqual(
                {
                    (
                        b"6f670c0fb53f9463760b7295fbb814e965fb20c8",
                        178,
                        1373561701,
                    ),
                    (
                        b"b2a2766a2879c209ab1176e7e778b81ae422eeaa",
                        138,
                        912998690,
                    ),
                    (
                        b"f18faa16531ac570a3fdc8c7ca16682548dafd12",
                        12,
                        3775879613,
                    ),
                },
                entries,
            )

    def test_create_index_v1(self):
        with self.get_pack_data(pack1_sha) as p:
            filename = os.path.join(self.tempdir, "v1test.idx")
            p.create_index_v1(filename)
            idx1 = load_pack_index(filename)
            idx2 = self.get_pack_index(pack1_sha)
            self.assertEqual(oct(os.stat(filename).st_mode), indexmode)
            self.assertEqual(idx1, idx2)

    def test_create_index_v2(self):
        with self.get_pack_data(pack1_sha) as p:
            filename = os.path.join(self.tempdir, "v2test.idx")
            p.create_index_v2(filename)
            idx1 = load_pack_index(filename)
            idx2 = self.get_pack_index(pack1_sha)
            self.assertEqual(oct(os.stat(filename).st_mode), indexmode)
            self.assertEqual(idx1, idx2)

    def test_compute_file_sha(self):
        f = BytesIO(b"abcd1234wxyz")
        self.assertEqual(
            sha1(b"abcd1234wxyz").hexdigest(), compute_file_sha(f).hexdigest()
        )
        self.assertEqual(
            sha1(b"abcd1234wxyz").hexdigest(),
            compute_file_sha(f, buffer_size=5).hexdigest(),
        )
        self.assertEqual(
            sha1(b"abcd1234").hexdigest(),
            compute_file_sha(f, end_ofs=-4).hexdigest(),
        )
        self.assertEqual(
            sha1(b"1234wxyz").hexdigest(),
            compute_file_sha(f, start_ofs=4).hexdigest(),
        )
        self.assertEqual(
            sha1(b"1234").hexdigest(),
            compute_file_sha(f, start_ofs=4, end_ofs=-4).hexdigest(),
        )

    def test_compute_file_sha_short_file(self):
        f = BytesIO(b"abcd1234wxyz")
        self.assertRaises(AssertionError, compute_file_sha, f, end_ofs=-20)
        self.assertRaises(AssertionError, compute_file_sha, f, end_ofs=20)
        self.assertRaises(
            AssertionError, compute_file_sha, f, start_ofs=10, end_ofs=-12
        )


class TestPack(PackTests):
    def test_len(self):
        with self.get_pack(pack1_sha) as p:
            self.assertEqual(3, len(p))

    def test_contains(self):
        with self.get_pack(pack1_sha) as p:
            self.assertIn(tree_sha, p)

    def test_get(self):
        with self.get_pack(pack1_sha) as p:
            self.assertEqual(type(p[tree_sha]), Tree)

    def test_iter(self):
        with self.get_pack(pack1_sha) as p:
            self.assertEqual({tree_sha, commit_sha, a_sha}, set(p))

    def test_iterobjects(self):
        with self.get_pack(pack1_sha) as p:
            expected = {p[s] for s in [commit_sha, tree_sha, a_sha]}
            self.assertEqual(expected, set(list(p.iterobjects())))

    def test_pack_tuples(self):
        with self.get_pack(pack1_sha) as p:
            tuples = p.pack_tuples()
            expected = {(p[s], None) for s in [commit_sha, tree_sha, a_sha]}
            self.assertEqual(expected, set(list(tuples)))
            self.assertEqual(expected, set(list(tuples)))
            self.assertEqual(3, len(tuples))

    def test_get_object_at(self):
        """Tests random access for non-delta objects"""
        with self.get_pack(pack1_sha) as p:
            obj = p[a_sha]
            self.assertEqual(obj.type_name, b"blob")
            self.assertEqual(obj.sha().hexdigest().encode("ascii"), a_sha)
            obj = p[tree_sha]
            self.assertEqual(obj.type_name, b"tree")
            self.assertEqual(obj.sha().hexdigest().encode("ascii"), tree_sha)
            obj = p[commit_sha]
            self.assertEqual(obj.type_name, b"commit")
            self.assertEqual(obj.sha().hexdigest().encode("ascii"), commit_sha)

    def test_copy(self):
        with self.get_pack(pack1_sha) as origpack:
            self.assertSucceeds(origpack.index.check)
            basename = os.path.join(self.tempdir, "Elch")
            write_pack(basename, origpack.pack_tuples())

            with Pack(basename) as newpack:
                self.assertEqual(origpack, newpack)
                self.assertSucceeds(newpack.index.check)
                self.assertEqual(origpack.name(), newpack.name())
                self.assertEqual(
                    origpack.index.get_pack_checksum(),
                    newpack.index.get_pack_checksum(),
                )

                wrong_version = origpack.index.version != newpack.index.version
                orig_checksum = origpack.index.get_stored_checksum()
                new_checksum = newpack.index.get_stored_checksum()
                self.assertTrue(wrong_version or orig_checksum == new_checksum)

    def test_commit_obj(self):
        with self.get_pack(pack1_sha) as p:
            commit = p[commit_sha]
            self.assertEqual(b"James Westby <jw+debian@jameswestby.net>", commit.author)
            self.assertEqual([], commit.parents)

    def _copy_pack(self, origpack):
        basename = os.path.join(self.tempdir, "somepack")
        write_pack(basename, origpack.pack_tuples())
        return Pack(basename)

    def test_keep_no_message(self):
        with self.get_pack(pack1_sha) as p:
            p = self._copy_pack(p)

        with p:
            keepfile_name = p.keep()

        # file should exist
        self.assertTrue(os.path.exists(keepfile_name))

        with open(keepfile_name) as f:
            buf = f.read()
            self.assertEqual("", buf)

    def test_keep_message(self):
        with self.get_pack(pack1_sha) as p:
            p = self._copy_pack(p)

        msg = b"some message"
        with p:
            keepfile_name = p.keep(msg)

        # file should exist
        self.assertTrue(os.path.exists(keepfile_name))

        # and contain the right message, with a linefeed
        with open(keepfile_name, "rb") as f:
            buf = f.read()
            self.assertEqual(msg + b"\n", buf)

    def test_name(self):
        with self.get_pack(pack1_sha) as p:
            self.assertEqual(pack1_sha, p.name())

    def test_length_mismatch(self):
        with self.get_pack_data(pack1_sha) as data:
            index = self.get_pack_index(pack1_sha)
            Pack.from_objects(data, index).check_length_and_checksum()

            data._file.seek(12)
            bad_file = BytesIO()
            write_pack_header(bad_file.write, 9999)
            bad_file.write(data._file.read())
            bad_file = BytesIO(bad_file.getvalue())
            bad_data = PackData("", file=bad_file)
            bad_pack = Pack.from_lazy_objects(lambda: bad_data, lambda: index)
            self.assertRaises(AssertionError, lambda: bad_pack.data)
            self.assertRaises(
                AssertionError, bad_pack.check_length_and_checksum
            )

    def test_checksum_mismatch(self):
        with self.get_pack_data(pack1_sha) as data:
            index = self.get_pack_index(pack1_sha)
            Pack.from_objects(data, index).check_length_and_checksum()

            data._file.seek(0)
            bad_file = BytesIO(data._file.read()[:-20] + (b"\xff" * 20))
            bad_data = PackData("", file=bad_file)
            bad_pack = Pack.from_lazy_objects(lambda: bad_data, lambda: index)
            self.assertRaises(ChecksumMismatch, lambda: bad_pack.data)
            self.assertRaises(
                ChecksumMismatch, bad_pack.check_length_and_checksum
            )

    def test_iterobjects_2(self):
        with self.get_pack(pack1_sha) as p:
            objs = {o.id: o for o in p.iterobjects()}
            self.assertEqual(3, len(objs))
            self.assertEqual(sorted(objs), sorted(p.index))
            self.assertIsInstance(objs[a_sha], Blob)
            self.assertIsInstance(objs[tree_sha], Tree)
            self.assertIsInstance(objs[commit_sha], Commit)

    def test_iterobjects_subset(self):
        with self.get_pack(pack1_sha) as p:
            objs = {o.id: o for o in p.iterobjects_subset([commit_sha])}
            self.assertEqual(1, len(objs))
            self.assertIsInstance(objs[commit_sha], Commit)


class TestThinPack(PackTests):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.blobs = {}
        for blob in (b"foo", b"bar", b"foo1234", b"bar2468"):
            self.blobs[blob] = make_object(Blob, data=blob)
        self.store.add_object(self.blobs[b"foo"])
        self.store.add_object(self.blobs[b"bar"])

        # Build a thin pack. 'foo' is as an external reference, 'bar' an
        # internal reference.
        self.pack_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pack_dir)
        self.pack_prefix = os.path.join(self.pack_dir, "pack")

        with open(self.pack_prefix + ".pack", "wb") as f:
            build_pack(
                f,
                [
                    (REF_DELTA, (self.blobs[b"foo"].id, b"foo1234")),
                    (Blob.type_num, b"bar"),
                    (REF_DELTA, (self.blobs[b"bar"].id, b"bar2468")),
                ],
                store=self.store,
            )

        # Index the new pack.
        with self.make_pack(True) as pack:
            with PackData(pack._data_path) as data:
                data.create_index(
                    self.pack_prefix + ".idx", resolve_ext_ref=pack.resolve_ext_ref)

        del self.store[self.blobs[b"bar"].id]

    def make_pack(self, resolve_ext_ref):
        return Pack(
            self.pack_prefix,
            resolve_ext_ref=self.store.get_raw if resolve_ext_ref else None,
        )

    def test_get_raw(self):
        with self.make_pack(False) as p:
            self.assertRaises(KeyError, p.get_raw, self.blobs[b"foo1234"].id)
        with self.make_pack(True) as p:
            self.assertEqual((3, b"foo1234"), p.get_raw(self.blobs[b"foo1234"].id))

    def test_get_unpacked_object(self):
        self.maxDiff = None
        with self.make_pack(False) as p:
            expected = UnpackedObject(
                7,
                delta_base=b"\x19\x10(\x15f=#\xf8\xb7ZG\xe7\xa0\x19e\xdc\xdc\x96F\x8c",
                decomp_chunks=[b'\x03\x07\x90\x03\x041234'],
            )
            expected.offset = 12
            got = p.get_unpacked_object(self.blobs[b"foo1234"].id)
            self.assertEqual(expected, got)
        with self.make_pack(True) as p:
            expected = UnpackedObject(
                7,
                delta_base=b"\x19\x10(\x15f=#\xf8\xb7ZG\xe7\xa0\x19e\xdc\xdc\x96F\x8c",
                decomp_chunks=[b'\x03\x07\x90\x03\x041234'],
            )
            expected.offset = 12
            got = p.get_unpacked_object(self.blobs[b"foo1234"].id)
            self.assertEqual(
                expected,
                got,
            )

    def test_iterobjects(self):
        with self.make_pack(False) as p:
            self.assertRaises(KeyError, list, p.iterobjects())
        with self.make_pack(True) as p:
            self.assertEqual(
                sorted(
                    [
                        self.blobs[b"foo1234"].id,
                        self.blobs[b"bar"].id,
                        self.blobs[b"bar2468"].id,
                    ]
                ),
                sorted(o.id for o in p.iterobjects()),
            )


class WritePackTests(TestCase):
    def test_write_pack_header(self):
        f = BytesIO()
        write_pack_header(f.write, 42)
        self.assertEqual(b"PACK\x00\x00\x00\x02\x00\x00\x00*", f.getvalue())

    def test_write_pack_object(self):
        f = BytesIO()
        f.write(b"header")
        offset = f.tell()
        crc32 = write_pack_object(f.write, Blob.type_num, b"blob")
        self.assertEqual(crc32, zlib.crc32(f.getvalue()[6:]) & 0xFFFFFFFF)

        f.write(b"x")  # unpack_object needs extra trailing data.
        f.seek(offset)
        unpacked, unused = unpack_object(f.read, compute_crc32=True)
        self.assertEqual(Blob.type_num, unpacked.pack_type_num)
        self.assertEqual(Blob.type_num, unpacked.obj_type_num)
        self.assertEqual([b"blob"], unpacked.decomp_chunks)
        self.assertEqual(crc32, unpacked.crc32)
        self.assertEqual(b"x", unused)

    def test_write_pack_object_sha(self):
        f = BytesIO()
        f.write(b"header")
        offset = f.tell()
        sha_a = sha1(b"foo")
        sha_b = sha_a.copy()
        write_pack_object(f.write, Blob.type_num, b"blob", sha=sha_a)
        self.assertNotEqual(sha_a.digest(), sha_b.digest())
        sha_b.update(f.getvalue()[offset:])
        self.assertEqual(sha_a.digest(), sha_b.digest())

    def test_write_pack_object_compression_level(self):
        f = BytesIO()
        f.write(b"header")
        offset = f.tell()
        sha_a = sha1(b"foo")
        sha_b = sha_a.copy()
        write_pack_object(f.write, Blob.type_num, b"blob", sha=sha_a, compression_level=6)
        self.assertNotEqual(sha_a.digest(), sha_b.digest())
        sha_b.update(f.getvalue()[offset:])
        self.assertEqual(sha_a.digest(), sha_b.digest())


pack_checksum = hex_to_sha("721980e866af9a5f93ad674144e1459b8ba3e7b7")


class BaseTestPackIndexWriting:
    def assertSucceeds(self, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except ChecksumMismatch as e:
            self.fail(e)

    def index(self, filename, entries, pack_checksum):
        raise NotImplementedError(self.index)

    def test_empty(self):
        idx = self.index("empty.idx", [], pack_checksum)
        self.assertEqual(idx.get_pack_checksum(), pack_checksum)
        self.assertEqual(0, len(idx))

    def test_large(self):
        entry1_sha = hex_to_sha("4e6388232ec39792661e2e75db8fb117fc869ce6")
        entry2_sha = hex_to_sha("e98f071751bd77f59967bfa671cd2caebdccc9a2")
        entries = [
            (entry1_sha, 0xF2972D0830529B87, 24),
            (entry2_sha, (~0xF2972D0830529B87) & (2 ** 64 - 1), 92),
        ]
        if not self._supports_large:
            self.assertRaises(
                TypeError, self.index, "single.idx", entries, pack_checksum
            )
            return
        idx = self.index("single.idx", entries, pack_checksum)
        self.assertEqual(idx.get_pack_checksum(), pack_checksum)
        self.assertEqual(2, len(idx))
        actual_entries = list(idx.iterentries())
        self.assertEqual(len(entries), len(actual_entries))
        for mine, actual in zip(entries, actual_entries):
            my_sha, my_offset, my_crc = mine
            actual_sha, actual_offset, actual_crc = actual
            self.assertEqual(my_sha, actual_sha)
            self.assertEqual(my_offset, actual_offset)
            if self._has_crc32_checksum:
                self.assertEqual(my_crc, actual_crc)
            else:
                self.assertIsNone(actual_crc)

    def test_single(self):
        entry_sha = hex_to_sha("6f670c0fb53f9463760b7295fbb814e965fb20c8")
        my_entries = [(entry_sha, 178, 42)]
        idx = self.index("single.idx", my_entries, pack_checksum)
        self.assertEqual(idx.get_pack_checksum(), pack_checksum)
        self.assertEqual(1, len(idx))
        actual_entries = list(idx.iterentries())
        self.assertEqual(len(my_entries), len(actual_entries))
        for mine, actual in zip(my_entries, actual_entries):
            my_sha, my_offset, my_crc = mine
            actual_sha, actual_offset, actual_crc = actual
            self.assertEqual(my_sha, actual_sha)
            self.assertEqual(my_offset, actual_offset)
            if self._has_crc32_checksum:
                self.assertEqual(my_crc, actual_crc)
            else:
                self.assertIsNone(actual_crc)


class BaseTestFilePackIndexWriting(BaseTestPackIndexWriting):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def index(self, filename, entries, pack_checksum):
        path = os.path.join(self.tempdir, filename)
        self.writeIndex(path, entries, pack_checksum)
        idx = load_pack_index(path)
        self.assertSucceeds(idx.check)
        self.assertEqual(idx.version, self._expected_version)
        return idx

    def writeIndex(self, filename, entries, pack_checksum):
        # FIXME: Write to BytesIO instead rather than hitting disk ?
        with GitFile(filename, "wb") as f:
            self._write_fn(f, entries, pack_checksum)


class TestMemoryIndexWriting(TestCase, BaseTestPackIndexWriting):
    def setUp(self):
        TestCase.setUp(self)
        self._has_crc32_checksum = True
        self._supports_large = True

    def index(self, filename, entries, pack_checksum):
        return MemoryPackIndex(entries, pack_checksum)

    def tearDown(self):
        TestCase.tearDown(self)


class TestPackIndexWritingv1(TestCase, BaseTestFilePackIndexWriting):
    def setUp(self):
        TestCase.setUp(self)
        BaseTestFilePackIndexWriting.setUp(self)
        self._has_crc32_checksum = False
        self._expected_version = 1
        self._supports_large = False
        self._write_fn = write_pack_index_v1

    def tearDown(self):
        TestCase.tearDown(self)
        BaseTestFilePackIndexWriting.tearDown(self)


class TestPackIndexWritingv2(TestCase, BaseTestFilePackIndexWriting):
    def setUp(self):
        TestCase.setUp(self)
        BaseTestFilePackIndexWriting.setUp(self)
        self._has_crc32_checksum = True
        self._supports_large = True
        self._expected_version = 2
        self._write_fn = write_pack_index_v2

    def tearDown(self):
        TestCase.tearDown(self)
        BaseTestFilePackIndexWriting.tearDown(self)


class ReadZlibTests(TestCase):

    decomp = (
        b"tree 4ada885c9196b6b6fa08744b5862bf92896fc002\n"
        b"parent None\n"
        b"author Jelmer Vernooij <jelmer@samba.org> 1228980214 +0000\n"
        b"committer Jelmer Vernooij <jelmer@samba.org> 1228980214 +0000\n"
        b"\n"
        b"Provide replacement for mmap()'s offset argument."
    )
    comp = zlib.compress(decomp)
    extra = b"nextobject"

    def setUp(self):
        super().setUp()
        self.read = BytesIO(self.comp + self.extra).read
        self.unpacked = UnpackedObject(Tree.type_num, decomp_len=len(self.decomp), crc32=0)

    def test_decompress_size(self):
        good_decomp_len = len(self.decomp)
        self.unpacked.decomp_len = -1
        self.assertRaises(ValueError, read_zlib_chunks, self.read, self.unpacked)
        self.unpacked.decomp_len = good_decomp_len - 1
        self.assertRaises(zlib.error, read_zlib_chunks, self.read, self.unpacked)
        self.unpacked.decomp_len = good_decomp_len + 1
        self.assertRaises(zlib.error, read_zlib_chunks, self.read, self.unpacked)

    def test_decompress_truncated(self):
        read = BytesIO(self.comp[:10]).read
        self.assertRaises(zlib.error, read_zlib_chunks, read, self.unpacked)

        read = BytesIO(self.comp).read
        self.assertRaises(zlib.error, read_zlib_chunks, read, self.unpacked)

    def test_decompress_empty(self):
        unpacked = UnpackedObject(Tree.type_num, decomp_len=0)
        comp = zlib.compress(b"")
        read = BytesIO(comp + self.extra).read
        unused = read_zlib_chunks(read, unpacked)
        self.assertEqual(b"", b"".join(unpacked.decomp_chunks))
        self.assertNotEqual(b"", unused)
        self.assertEqual(self.extra, unused + read())

    def test_decompress_no_crc32(self):
        self.unpacked.crc32 = None
        read_zlib_chunks(self.read, self.unpacked)
        self.assertEqual(None, self.unpacked.crc32)

    def _do_decompress_test(self, buffer_size, **kwargs):
        unused = read_zlib_chunks(
            self.read, self.unpacked, buffer_size=buffer_size, **kwargs
        )
        self.assertEqual(self.decomp, b"".join(self.unpacked.decomp_chunks))
        self.assertEqual(zlib.crc32(self.comp), self.unpacked.crc32)
        self.assertNotEqual(b"", unused)
        self.assertEqual(self.extra, unused + self.read())

    def test_simple_decompress(self):
        self._do_decompress_test(4096)
        self.assertEqual(None, self.unpacked.comp_chunks)

    # These buffer sizes are not intended to be realistic, but rather simulate
    # larger buffer sizes that may end at various places.
    def test_decompress_buffer_size_1(self):
        self._do_decompress_test(1)

    def test_decompress_buffer_size_2(self):
        self._do_decompress_test(2)

    def test_decompress_buffer_size_3(self):
        self._do_decompress_test(3)

    def test_decompress_buffer_size_4(self):
        self._do_decompress_test(4)

    def test_decompress_include_comp(self):
        self._do_decompress_test(4096, include_comp=True)
        self.assertEqual(self.comp, b"".join(self.unpacked.comp_chunks))


class DeltifyTests(TestCase):
    def test_empty(self):
        self.assertEqual([], list(deltify_pack_objects([])))

    def test_single(self):
        b = Blob.from_string(b"foo")
        self.assertEqual(
            [UnpackedObject(b.type_num, sha=b.sha().digest(), delta_base=None, decomp_chunks=b.as_raw_chunks())],
            list(deltify_pack_objects([(b, b"")])),
        )

    def test_simple_delta(self):
        b1 = Blob.from_string(b"a" * 101)
        b2 = Blob.from_string(b"a" * 100)
        delta = list(create_delta(b1.as_raw_chunks(), b2.as_raw_chunks()))
        self.assertEqual(
            [
                UnpackedObject(b1.type_num, sha=b1.sha().digest(), delta_base=None, decomp_chunks=b1.as_raw_chunks()),
                UnpackedObject(b2.type_num, sha=b2.sha().digest(), delta_base=b1.sha().digest(), decomp_chunks=delta),
            ],
            list(deltify_pack_objects([(b1, b""), (b2, b"")])),
        )


class TestPackStreamReader(TestCase):
    def test_read_objects_emtpy(self):
        f = BytesIO()
        build_pack(f, [])
        reader = PackStreamReader(f.read)
        self.assertEqual(0, len(list(reader.read_objects())))

    def test_read_objects(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (Blob.type_num, b"blob"),
                (OFS_DELTA, (0, b"blob1")),
            ],
        )
        reader = PackStreamReader(f.read)
        objects = list(reader.read_objects(compute_crc32=True))
        self.assertEqual(2, len(objects))

        unpacked_blob, unpacked_delta = objects

        self.assertEqual(entries[0][0], unpacked_blob.offset)
        self.assertEqual(Blob.type_num, unpacked_blob.pack_type_num)
        self.assertEqual(Blob.type_num, unpacked_blob.obj_type_num)
        self.assertEqual(None, unpacked_blob.delta_base)
        self.assertEqual(b"blob", b"".join(unpacked_blob.decomp_chunks))
        self.assertEqual(entries[0][4], unpacked_blob.crc32)

        self.assertEqual(entries[1][0], unpacked_delta.offset)
        self.assertEqual(OFS_DELTA, unpacked_delta.pack_type_num)
        self.assertEqual(None, unpacked_delta.obj_type_num)
        self.assertEqual(
            unpacked_delta.offset - unpacked_blob.offset,
            unpacked_delta.delta_base,
        )
        delta = create_delta(b"blob", b"blob1")
        self.assertEqual(b''.join(delta), b"".join(unpacked_delta.decomp_chunks))
        self.assertEqual(entries[1][4], unpacked_delta.crc32)

    def test_read_objects_buffered(self):
        f = BytesIO()
        build_pack(
            f,
            [
                (Blob.type_num, b"blob"),
                (OFS_DELTA, (0, b"blob1")),
            ],
        )
        reader = PackStreamReader(f.read, zlib_bufsize=4)
        self.assertEqual(2, len(list(reader.read_objects())))

    def test_read_objects_empty(self):
        reader = PackStreamReader(BytesIO().read)
        self.assertRaises(AssertionError, list, reader.read_objects())


class TestPackIterator(DeltaChainIterator):

    _compute_crc32 = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._unpacked_offsets = set()

    def _result(self, unpacked):
        """Return entries in the same format as build_pack."""
        return (
            unpacked.offset,
            unpacked.obj_type_num,
            b"".join(unpacked.obj_chunks),
            unpacked.sha(),
            unpacked.crc32,
        )

    def _resolve_object(self, offset, pack_type_num, base_chunks):
        assert offset not in self._unpacked_offsets, (
            "Attempted to re-inflate offset %i" % offset
        )
        self._unpacked_offsets.add(offset)
        return super()._resolve_object(
            offset, pack_type_num, base_chunks
        )


class DeltaChainIteratorTests(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.fetched = set()

    def store_blobs(self, blobs_data):
        blobs = []
        for data in blobs_data:
            blob = make_object(Blob, data=data)
            blobs.append(blob)
            self.store.add_object(blob)
        return blobs

    def get_raw_no_repeat(self, bin_sha):
        """Wrapper around store.get_raw that doesn't allow repeat lookups."""
        hex_sha = sha_to_hex(bin_sha)
        self.assertNotIn(
            hex_sha,
            self.fetched,
            "Attempted to re-fetch object %s" % hex_sha
        )
        self.fetched.add(hex_sha)
        return self.store.get_raw(hex_sha)

    def make_pack_iter(self, f, thin=None):
        if thin is None:
            thin = bool(list(self.store))
        resolve_ext_ref = thin and self.get_raw_no_repeat or None
        data = PackData("test.pack", file=f)
        return TestPackIterator.for_pack_data(data, resolve_ext_ref=resolve_ext_ref)

    def make_pack_iter_subset(self, f, subset, thin=None):
        if thin is None:
            thin = bool(list(self.store))
        resolve_ext_ref = thin and self.get_raw_no_repeat or None
        data = PackData("test.pack", file=f)
        assert data
        index = MemoryPackIndex.for_pack(data)
        pack = Pack.from_objects(data, index)
        return TestPackIterator.for_pack_subset(pack, subset, resolve_ext_ref=resolve_ext_ref)

    def assertEntriesMatch(self, expected_indexes, entries, pack_iter):
        expected = [entries[i] for i in expected_indexes]
        self.assertEqual(expected, list(pack_iter._walk_all_chains()))

    def test_no_deltas(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (Commit.type_num, b"commit"),
                (Blob.type_num, b"blob"),
                (Tree.type_num, b"tree"),
            ],
        )
        self.assertEntriesMatch([0, 1, 2], entries, self.make_pack_iter(f))
        f.seek(0)
        self.assertEntriesMatch([], entries, self.make_pack_iter_subset(f, []))
        f.seek(0)
        self.assertEntriesMatch([1, 0], entries, self.make_pack_iter_subset(f, [entries[0][3], entries[1][3]]))
        f.seek(0)
        self.assertEntriesMatch(
            [1, 0], entries, self.make_pack_iter_subset(f, [sha_to_hex(entries[0][3]), sha_to_hex(entries[1][3])]))

    def test_ofs_deltas(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (Blob.type_num, b"blob"),
                (OFS_DELTA, (0, b"blob1")),
                (OFS_DELTA, (0, b"blob2")),
            ],
        )
        # Delta resolution changed to DFS
        self.assertEntriesMatch([0, 2, 1], entries, self.make_pack_iter(f))
        f.seek(0)
        self.assertEntriesMatch(
            [0, 2, 1], entries,
            self.make_pack_iter_subset(f, [entries[1][3], entries[2][3]]))

    def test_ofs_deltas_chain(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (Blob.type_num, b"blob"),
                (OFS_DELTA, (0, b"blob1")),
                (OFS_DELTA, (1, b"blob2")),
            ],
        )
        self.assertEntriesMatch([0, 1, 2], entries, self.make_pack_iter(f))

    def test_ref_deltas(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (1, b"blob1")),
                (Blob.type_num, (b"blob")),
                (REF_DELTA, (1, b"blob2")),
            ],
        )
        # Delta resolution changed to DFS
        self.assertEntriesMatch([1, 2, 0], entries, self.make_pack_iter(f))

    def test_ref_deltas_chain(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (2, b"blob1")),
                (Blob.type_num, (b"blob")),
                (REF_DELTA, (1, b"blob2")),
            ],
        )
        self.assertEntriesMatch([1, 2, 0], entries, self.make_pack_iter(f))

    def test_ofs_and_ref_deltas(self):
        # Deltas pending on this offset are popped before deltas depending on
        # this ref.
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (1, b"blob1")),
                (Blob.type_num, (b"blob")),
                (OFS_DELTA, (1, b"blob2")),
            ],
        )

        # Delta resolution changed to DFS
        self.assertEntriesMatch([1, 0, 2], entries, self.make_pack_iter(f))

    def test_mixed_chain(self):
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (Blob.type_num, b"blob"),
                (REF_DELTA, (2, b"blob2")),
                (OFS_DELTA, (0, b"blob1")),
                (OFS_DELTA, (1, b"blob3")),
                (OFS_DELTA, (0, b"bob")),
            ])
        # Delta resolution changed to DFS
        self.assertEntriesMatch([0, 4, 2, 1, 3], entries, self.make_pack_iter(f))

    def test_long_chain(self):
        n = 100
        objects_spec = [(Blob.type_num, b"blob")]
        for i in range(n):
            objects_spec.append((OFS_DELTA, (i, b"blob" + str(i).encode("ascii"))))
        f = BytesIO()
        entries = build_pack(f, objects_spec)
        self.assertEntriesMatch(range(n + 1), entries, self.make_pack_iter(f))

    def test_branchy_chain(self):
        n = 100
        objects_spec = [(Blob.type_num, b"blob")]
        for i in range(n):
            objects_spec.append((OFS_DELTA, (0, b"blob" + str(i).encode("ascii"))))
        f = BytesIO()
        entries = build_pack(f, objects_spec)
        # Delta resolution changed to DFS
        indices = [0] + list(range(100, 0, -1))
        self.assertEntriesMatch(indices, entries, self.make_pack_iter(f))

    def test_ext_ref(self):
        (blob,) = self.store_blobs([b"blob"])
        f = BytesIO()
        entries = build_pack(f, [(REF_DELTA, (blob.id, b"blob1"))], store=self.store)
        pack_iter = self.make_pack_iter(f)
        self.assertEntriesMatch([0], entries, pack_iter)
        self.assertEqual([hex_to_sha(blob.id)], pack_iter.ext_refs())

    def test_ext_ref_chain(self):
        (blob,) = self.store_blobs([b"blob"])
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (1, b"blob2")),
                (REF_DELTA, (blob.id, b"blob1")),
            ],
            store=self.store,
        )
        pack_iter = self.make_pack_iter(f)
        self.assertEntriesMatch([1, 0], entries, pack_iter)
        self.assertEqual([hex_to_sha(blob.id)], pack_iter.ext_refs())

    def test_ext_ref_chain_degenerate(self):
        # Test a degenerate case where the sender is sending a REF_DELTA
        # object that expands to an object already in the repository.
        (blob,) = self.store_blobs([b"blob"])
        (blob2,) = self.store_blobs([b"blob2"])
        assert blob.id < blob2.id

        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (blob.id, b"blob2")),
                (REF_DELTA, (0, b"blob3")),
            ],
            store=self.store,
        )
        pack_iter = self.make_pack_iter(f)
        self.assertEntriesMatch([0, 1], entries, pack_iter)
        self.assertEqual([hex_to_sha(blob.id)], pack_iter.ext_refs())

    def test_ext_ref_multiple_times(self):
        (blob,) = self.store_blobs([b"blob"])
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (blob.id, b"blob1")),
                (REF_DELTA, (blob.id, b"blob2")),
            ],
            store=self.store,
        )
        pack_iter = self.make_pack_iter(f)
        self.assertEntriesMatch([0, 1], entries, pack_iter)
        self.assertEqual([hex_to_sha(blob.id)], pack_iter.ext_refs())

    def test_multiple_ext_refs(self):
        b1, b2 = self.store_blobs([b"foo", b"bar"])
        f = BytesIO()
        entries = build_pack(
            f,
            [
                (REF_DELTA, (b1.id, b"foo1")),
                (REF_DELTA, (b2.id, b"bar2")),
            ],
            store=self.store,
        )
        pack_iter = self.make_pack_iter(f)
        self.assertEntriesMatch([0, 1], entries, pack_iter)
        self.assertEqual([hex_to_sha(b1.id), hex_to_sha(b2.id)], pack_iter.ext_refs())

    def test_bad_ext_ref_non_thin_pack(self):
        (blob,) = self.store_blobs([b"blob"])
        f = BytesIO()
        build_pack(f, [(REF_DELTA, (blob.id, b"blob1"))], store=self.store)
        pack_iter = self.make_pack_iter(f, thin=False)
        try:
            list(pack_iter._walk_all_chains())
            self.fail()
        except KeyError as e:
            self.assertEqual(([blob.id],), e.args)

    def test_bad_ext_ref_thin_pack(self):
        b1, b2, b3 = self.store_blobs([b"foo", b"bar", b"baz"])
        f = BytesIO()
        build_pack(
            f,
            [
                (REF_DELTA, (1, b"foo99")),
                (REF_DELTA, (b1.id, b"foo1")),
                (REF_DELTA, (b2.id, b"bar2")),
                (REF_DELTA, (b3.id, b"baz3")),
            ],
            store=self.store,
        )
        del self.store[b2.id]
        del self.store[b3.id]
        pack_iter = self.make_pack_iter(f)
        try:
            list(pack_iter._walk_all_chains())
            self.fail()
        except KeyError as e:
            self.assertEqual((sorted([b2.id, b3.id]),), (sorted(e.args[0]),))


class DeltaEncodeSizeTests(TestCase):
    def test_basic(self):
        self.assertEqual(b"\x00", _delta_encode_size(0))
        self.assertEqual(b"\x01", _delta_encode_size(1))
        self.assertEqual(b"\xfa\x01", _delta_encode_size(250))
        self.assertEqual(b"\xe8\x07", _delta_encode_size(1000))
        self.assertEqual(b"\xa0\x8d\x06", _delta_encode_size(100000))


class EncodeCopyOperationTests(TestCase):
    def test_basic(self):
        self.assertEqual(b"\x80", _encode_copy_operation(0, 0))
        self.assertEqual(b"\x91\x01\x0a", _encode_copy_operation(1, 10))
        self.assertEqual(b"\xb1\x64\xe8\x03", _encode_copy_operation(100, 1000))
        self.assertEqual(b"\x93\xe8\x03\x01", _encode_copy_operation(1000, 1))
