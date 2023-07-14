# test_objects.py -- tests for objects.py
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
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

"""Tests for git base objects."""

# TODO: Round-trip parse-serialize-parse and serialize-parse-serialize tests.


import datetime
import os
import stat
from contextlib import contextmanager
from io import BytesIO
from itertools import permutations

from dulwich.tests import TestCase

from ..errors import ObjectFormatException
from ..objects import (MAX_TIME, Blob, Commit, ShaFile, Tag, Tree, TreeEntry,
                       _parse_tree_py, _sorted_tree_items_py, check_hexsha,
                       check_identity, format_timezone, hex_to_filename,
                       hex_to_sha, object_class, parse_timezone, parse_tree,
                       pretty_format_tree_entry, sha_to_hex, sorted_tree_items)
from .utils import (ext_functest_builder, functest_builder, make_commit,
                    make_object)

a_sha = b"6f670c0fb53f9463760b7295fbb814e965fb20c8"
b_sha = b"2969be3e8ee1c0222396a5611407e4769f14e54b"
c_sha = b"954a536f7819d40e6f637f849ee187dd10066349"
tree_sha = b"70c190eb48fa8bbb50ddc692a17b44cb781af7f6"
tag_sha = b"71033db03a03c6a36721efcf1968dd8f8e0cf023"


class TestHexToSha(TestCase):
    def test_simple(self):
        self.assertEqual(b"\xab\xcd" * 10, hex_to_sha(b"abcd" * 10))

    def test_reverse(self):
        self.assertEqual(b"abcd" * 10, sha_to_hex(b"\xab\xcd" * 10))


class BlobReadTests(TestCase):
    """Test decompression of blobs"""

    def get_sha_file(self, cls, base, sha):
        dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", base)
        return cls.from_path(hex_to_filename(dir, sha))

    def get_blob(self, sha):
        """Return the blob named sha from the test data dir"""
        return self.get_sha_file(Blob, "blobs", sha)

    def get_tree(self, sha):
        return self.get_sha_file(Tree, "trees", sha)

    def get_tag(self, sha):
        return self.get_sha_file(Tag, "tags", sha)

    def commit(self, sha):
        return self.get_sha_file(Commit, "commits", sha)

    def test_decompress_simple_blob(self):
        b = self.get_blob(a_sha)
        self.assertEqual(b.data, b"test 1\n")
        self.assertEqual(b.sha().hexdigest().encode("ascii"), a_sha)

    def test_hash(self):
        b = self.get_blob(a_sha)
        self.assertEqual(hash(b.id), hash(b))

    def test_parse_empty_blob_object(self):
        sha = b"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        b = self.get_blob(sha)
        self.assertEqual(b.data, b"")
        self.assertEqual(b.id, sha)
        self.assertEqual(b.sha().hexdigest().encode("ascii"), sha)

    def test_create_blob_from_string(self):
        string = b"test 2\n"
        b = Blob.from_string(string)
        self.assertEqual(b.data, string)
        self.assertEqual(b.sha().hexdigest().encode("ascii"), b_sha)

    def test_legacy_from_file(self):
        b1 = Blob.from_string(b"foo")
        b_raw = b1.as_legacy_object()
        b2 = b1.from_file(BytesIO(b_raw))
        self.assertEqual(b1, b2)

    def test_legacy_from_file_compression_level(self):
        b1 = Blob.from_string(b"foo")
        b_raw = b1.as_legacy_object(compression_level=6)
        b2 = b1.from_file(BytesIO(b_raw))
        self.assertEqual(b1, b2)

    def test_chunks(self):
        string = b"test 5\n"
        b = Blob.from_string(string)
        self.assertEqual([string], b.chunked)

    def test_splitlines(self):
        for case in [
            [],
            [b"foo\nbar\n"],
            [b"bl\na", b"blie"],
            [b"bl\na", b"blie", b"bloe\n"],
            [b"", b"bl\na", b"blie", b"bloe\n"],
            [b"", b"", b"", b"bla\n"],
            [b"", b"", b"", b"bla\n", b""],
            [b"bl", b"", b"a\naaa"],
            [b"a\naaa", b"a"],
        ]:
            b = Blob()
            b.chunked = case
            self.assertEqual(b.data.splitlines(True), b.splitlines())

    def test_set_chunks(self):
        b = Blob()
        b.chunked = [b"te", b"st", b" 5\n"]
        self.assertEqual(b"test 5\n", b.data)
        b.chunked = [b"te", b"st", b" 6\n"]
        self.assertEqual(b"test 6\n", b.as_raw_string())
        self.assertEqual(b"test 6\n", bytes(b))

    def test_parse_legacy_blob(self):
        string = b"test 3\n"
        b = self.get_blob(c_sha)
        self.assertEqual(b.data, string)
        self.assertEqual(b.sha().hexdigest().encode("ascii"), c_sha)

    def test_eq(self):
        blob1 = self.get_blob(a_sha)
        blob2 = self.get_blob(a_sha)
        self.assertEqual(blob1, blob2)

    def test_read_tree_from_file(self):
        t = self.get_tree(tree_sha)
        self.assertEqual(t.items()[0], (b"a", 33188, a_sha))
        self.assertEqual(t.items()[1], (b"b", 33188, b_sha))

    def test_read_tree_from_file_parse_count(self):
        old_deserialize = Tree._deserialize

        def reset_deserialize():
            Tree._deserialize = old_deserialize

        self.addCleanup(reset_deserialize)
        self.deserialize_count = 0

        def counting_deserialize(*args, **kwargs):
            self.deserialize_count += 1
            return old_deserialize(*args, **kwargs)

        Tree._deserialize = counting_deserialize
        t = self.get_tree(tree_sha)
        self.assertEqual(t.items()[0], (b"a", 33188, a_sha))
        self.assertEqual(t.items()[1], (b"b", 33188, b_sha))
        self.assertEqual(self.deserialize_count, 1)

    def test_read_tag_from_file(self):
        t = self.get_tag(tag_sha)
        self.assertEqual(
            t.object, (Commit, b"51b668fd5bf7061b7d6fa525f88803e6cfadaa51")
        )
        self.assertEqual(t.name, b"signed")
        self.assertEqual(t.tagger, b"Ali Sabil <ali.sabil@gmail.com>")
        self.assertEqual(t.tag_time, 1231203091)
        self.assertEqual(t.message, b"This is a signed tag\n")
        self.assertEqual(
            t.signature,
            b"-----BEGIN PGP SIGNATURE-----\n"
            b"Version: GnuPG v1.4.9 (GNU/Linux)\n"
            b"\n"
            b"iEYEABECAAYFAkliqx8ACgkQqSMmLy9u/"
            b"kcx5ACfakZ9NnPl02tOyYP6pkBoEkU1\n"
            b"5EcAn0UFgokaSvS371Ym/4W9iJj6vh3h\n"
            b"=ql7y\n"
            b"-----END PGP SIGNATURE-----\n",
        )

    def test_read_commit_from_file(self):
        sha = b"60dacdc733de308bb77bb76ce0fb0f9b44c9769e"
        c = self.commit(sha)
        self.assertEqual(c.tree, tree_sha)
        self.assertEqual(c.parents, [b"0d89f20333fbb1d2f3a94da77f4981373d8f4310"])
        self.assertEqual(c.author, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.committer, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.commit_time, 1174759230)
        self.assertEqual(c.commit_timezone, 0)
        self.assertEqual(c.author_timezone, 0)
        self.assertEqual(c.message, b"Test commit\n")

    def test_read_commit_no_parents(self):
        sha = b"0d89f20333fbb1d2f3a94da77f4981373d8f4310"
        c = self.commit(sha)
        self.assertEqual(c.tree, b"90182552c4a85a45ec2a835cadc3451bebdfe870")
        self.assertEqual(c.parents, [])
        self.assertEqual(c.author, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.committer, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.commit_time, 1174758034)
        self.assertEqual(c.commit_timezone, 0)
        self.assertEqual(c.author_timezone, 0)
        self.assertEqual(c.message, b"Test commit\n")

    def test_read_commit_two_parents(self):
        sha = b"5dac377bdded4c9aeb8dff595f0faeebcc8498cc"
        c = self.commit(sha)
        self.assertEqual(c.tree, b"d80c186a03f423a81b39df39dc87fd269736ca86")
        self.assertEqual(
            c.parents,
            [
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
            ],
        )
        self.assertEqual(c.author, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.committer, b"James Westby <jw+debian@jameswestby.net>")
        self.assertEqual(c.commit_time, 1174773719)
        self.assertEqual(c.commit_timezone, 0)
        self.assertEqual(c.author_timezone, 0)
        self.assertEqual(c.message, b"Merge ../b\n")

    def test_stub_sha(self):
        sha = b"5" * 40
        c = make_commit(id=sha, message=b"foo")
        self.assertIsInstance(c, Commit)
        self.assertEqual(sha, c.id)
        self.assertNotEqual(sha, c.sha())


class ShaFileCheckTests(TestCase):
    def assertCheckFails(self, cls, data):
        obj = cls()

        def do_check():
            obj.set_raw_string(data)
            obj.check()

        self.assertRaises(ObjectFormatException, do_check)

    def assertCheckSucceeds(self, cls, data):
        obj = cls()
        obj.set_raw_string(data)
        self.assertEqual(None, obj.check())


small_buffer_zlib_object = (
    b"\x48\x89\x15\xcc\x31\x0e\xc2\x30\x0c\x40\x51\xe6"
    b"\x9c\xc2\x3b\xaa\x64\x37\xc4\xc1\x12\x42\x5c\xc5"
    b"\x49\xac\x52\xd4\x92\xaa\x78\xe1\xf6\x94\xed\xeb"
    b"\x0d\xdf\x75\x02\xa2\x7c\xea\xe5\x65\xd5\x81\x8b"
    b"\x9a\x61\xba\xa0\xa9\x08\x36\xc9\x4c\x1a\xad\x88"
    b"\x16\xba\x46\xc4\xa8\x99\x6a\x64\xe1\xe0\xdf\xcd"
    b"\xa0\xf6\x75\x9d\x3d\xf8\xf1\xd0\x77\xdb\xfb\xdc"
    b"\x86\xa3\x87\xf1\x2f\x93\xed\x00\xb7\xc7\xd2\xab"
    b"\x2e\xcf\xfe\xf1\x3b\x50\xa4\x91\x53\x12\x24\x38"
    b"\x23\x21\x86\xf0\x03\x2f\x91\x24\x52"
)


class ShaFileTests(TestCase):
    def test_deflated_smaller_window_buffer(self):
        # zlib on some systems uses smaller buffers,
        # resulting in a different header.
        # See https://github.com/libgit2/libgit2/pull/464
        sf = ShaFile.from_file(BytesIO(small_buffer_zlib_object))
        self.assertEqual(sf.type_name, b"tag")
        self.assertEqual(sf.tagger, b" <@localhost>")


class CommitSerializationTests(TestCase):
    def make_commit(self, **kwargs):
        attrs = {
            "tree": b"d80c186a03f423a81b39df39dc87fd269736ca86",
            "parents": [
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
            ],
            "author": b"James Westby <jw+debian@jameswestby.net>",
            "committer": b"James Westby <jw+debian@jameswestby.net>",
            "commit_time": 1174773719,
            "author_time": 1174773719,
            "commit_timezone": 0,
            "author_timezone": 0,
            "message": b"Merge ../b\n",
        }
        attrs.update(kwargs)
        return make_commit(**attrs)

    def test_encoding(self):
        c = self.make_commit(encoding=b"iso8859-1")
        self.assertIn(b"encoding iso8859-1\n", c.as_raw_string())

    def test_short_timestamp(self):
        c = self.make_commit(commit_time=30)
        c1 = Commit()
        c1.set_raw_string(c.as_raw_string())
        self.assertEqual(30, c1.commit_time)

    def test_full_tree(self):
        c = self.make_commit(commit_time=30)
        t = Tree()
        t.add(b"data-x", 0o644, Blob().id)
        c.tree = t
        c1 = Commit()
        c1.set_raw_string(c.as_raw_string())
        self.assertEqual(t.id, c1.tree)
        self.assertEqual(c.as_raw_string(), c1.as_raw_string())

    def test_raw_length(self):
        c = self.make_commit()
        self.assertEqual(len(c.as_raw_string()), c.raw_length())

    def test_simple(self):
        c = self.make_commit()
        self.assertEqual(c.id, b"5dac377bdded4c9aeb8dff595f0faeebcc8498cc")
        self.assertEqual(
            b"tree d80c186a03f423a81b39df39dc87fd269736ca86\n"
            b"parent ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd\n"
            b"parent 4cffe90e0a41ad3f5190079d7c8f036bde29cbe6\n"
            b"author James Westby <jw+debian@jameswestby.net> "
            b"1174773719 +0000\n"
            b"committer James Westby <jw+debian@jameswestby.net> "
            b"1174773719 +0000\n"
            b"\n"
            b"Merge ../b\n",
            c.as_raw_string(),
        )

    def test_timezone(self):
        c = self.make_commit(commit_timezone=(5 * 60))
        self.assertIn(b" +0005\n", c.as_raw_string())

    def test_neg_timezone(self):
        c = self.make_commit(commit_timezone=(-1 * 3600))
        self.assertIn(b" -0100\n", c.as_raw_string())

    def test_deserialize(self):
        c = self.make_commit()
        d = Commit()
        d._deserialize(c.as_raw_chunks())
        self.assertEqual(c, d)

    def test_serialize_gpgsig(self):
        commit = self.make_commit(
            gpgsig=b"""-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAABCgAGBQJULCdfAAoJEACAbyvXKaRXuKwP/RyP9PA49uAvu8tQVCC/uBa8
vi975+xvO14R8Pp8k2nps7lSxCdtCd+xVT1VRHs0wNhOZo2YCVoU1HATkPejqSeV
NScTHcxnk4/+bxyfk14xvJkNp7FlQ3npmBkA+lbV0Ubr33rvtIE5jiJPyz+SgWAg
xdBG2TojV0squj00GoH/euK6aX7GgZtwdtpTv44haCQdSuPGDcI4TORqR6YSqvy3
GPE+3ZqXPFFb+KILtimkxitdwB7CpwmNse2vE3rONSwTvi8nq3ZoQYNY73CQGkUy
qoFU0pDtw87U3niFin1ZccDgH0bB6624sLViqrjcbYJeg815Htsu4rmzVaZADEVC
XhIO4MThebusdk0AcNGjgpf3HRHk0DPMDDlIjm+Oao0cqovvF6VyYmcb0C+RmhJj
dodLXMNmbqErwTk3zEkW0yZvNIYXH7m9SokPCZa4eeIM7be62X6h1mbt0/IU6Th+
v18fS0iTMP/Viug5und+05C/v04kgDo0CPphAbXwWMnkE4B6Tl9sdyUYXtvQsL7x
0+WP1gL27ANqNZiI07Kz/BhbBAQI/+2TFT7oGr0AnFPQ5jHp+3GpUf6OKuT1wT3H
ND189UFuRuubxb42vZhpcXRbqJVWnbECTKVUPsGZqat3enQUB63uM4i6/RdONDZA
fDeF1m4qYs+cUXKNUZ03
=X6RT
-----END PGP SIGNATURE-----"""
        )
        self.maxDiff = None
        self.assertEqual(
            b"""\
tree d80c186a03f423a81b39df39dc87fd269736ca86
parent ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd
parent 4cffe90e0a41ad3f5190079d7c8f036bde29cbe6
author James Westby <jw+debian@jameswestby.net> 1174773719 +0000
committer James Westby <jw+debian@jameswestby.net> 1174773719 +0000
gpgsig -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v1
 
 iQIcBAABCgAGBQJULCdfAAoJEACAbyvXKaRXuKwP/RyP9PA49uAvu8tQVCC/uBa8
 vi975+xvO14R8Pp8k2nps7lSxCdtCd+xVT1VRHs0wNhOZo2YCVoU1HATkPejqSeV
 NScTHcxnk4/+bxyfk14xvJkNp7FlQ3npmBkA+lbV0Ubr33rvtIE5jiJPyz+SgWAg
 xdBG2TojV0squj00GoH/euK6aX7GgZtwdtpTv44haCQdSuPGDcI4TORqR6YSqvy3
 GPE+3ZqXPFFb+KILtimkxitdwB7CpwmNse2vE3rONSwTvi8nq3ZoQYNY73CQGkUy
 qoFU0pDtw87U3niFin1ZccDgH0bB6624sLViqrjcbYJeg815Htsu4rmzVaZADEVC
 XhIO4MThebusdk0AcNGjgpf3HRHk0DPMDDlIjm+Oao0cqovvF6VyYmcb0C+RmhJj
 dodLXMNmbqErwTk3zEkW0yZvNIYXH7m9SokPCZa4eeIM7be62X6h1mbt0/IU6Th+
 v18fS0iTMP/Viug5und+05C/v04kgDo0CPphAbXwWMnkE4B6Tl9sdyUYXtvQsL7x
 0+WP1gL27ANqNZiI07Kz/BhbBAQI/+2TFT7oGr0AnFPQ5jHp+3GpUf6OKuT1wT3H
 ND189UFuRuubxb42vZhpcXRbqJVWnbECTKVUPsGZqat3enQUB63uM4i6/RdONDZA
 fDeF1m4qYs+cUXKNUZ03
 =X6RT
 -----END PGP SIGNATURE-----

Merge ../b
""",
            commit.as_raw_string(),
        )

    def test_serialize_mergetag(self):
        tag = make_object(
            Tag,
            object=(Commit, b"a38d6181ff27824c79fc7df825164a212eff6a3f"),
            object_type_name=b"commit",
            name=b"v2.6.22-rc7",
            tag_time=1183319674,
            tag_timezone=0,
            tagger=b"Linus Torvalds <torvalds@woody.linux-foundation.org>",
            message=default_message,
        )
        commit = self.make_commit(mergetag=[tag])

        self.assertEqual(
            b"""tree d80c186a03f423a81b39df39dc87fd269736ca86
parent ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd
parent 4cffe90e0a41ad3f5190079d7c8f036bde29cbe6
author James Westby <jw+debian@jameswestby.net> 1174773719 +0000
committer James Westby <jw+debian@jameswestby.net> 1174773719 +0000
mergetag object a38d6181ff27824c79fc7df825164a212eff6a3f
 type commit
 tag v2.6.22-rc7
 tagger Linus Torvalds <torvalds@woody.linux-foundation.org> 1183319674 +0000
 
 Linux 2.6.22-rc7
 -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v1.4.7 (GNU/Linux)
 
 iD8DBQBGiAaAF3YsRnbiHLsRAitMAKCiLboJkQECM/jpYsY3WPfvUgLXkACgg3ql
 OK2XeQOiEeXtT76rV4t2WR4=
 =ivrA
 -----END PGP SIGNATURE-----

Merge ../b
""",
            commit.as_raw_string(),
        )

    def test_serialize_mergetags(self):
        tag = make_object(
            Tag,
            object=(Commit, b"a38d6181ff27824c79fc7df825164a212eff6a3f"),
            object_type_name=b"commit",
            name=b"v2.6.22-rc7",
            tag_time=1183319674,
            tag_timezone=0,
            tagger=b"Linus Torvalds <torvalds@woody.linux-foundation.org>",
            message=default_message,
        )
        commit = self.make_commit(mergetag=[tag, tag])

        self.assertEqual(
            b"""tree d80c186a03f423a81b39df39dc87fd269736ca86
parent ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd
parent 4cffe90e0a41ad3f5190079d7c8f036bde29cbe6
author James Westby <jw+debian@jameswestby.net> 1174773719 +0000
committer James Westby <jw+debian@jameswestby.net> 1174773719 +0000
mergetag object a38d6181ff27824c79fc7df825164a212eff6a3f
 type commit
 tag v2.6.22-rc7
 tagger Linus Torvalds <torvalds@woody.linux-foundation.org> 1183319674 +0000
 
 Linux 2.6.22-rc7
 -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v1.4.7 (GNU/Linux)
 
 iD8DBQBGiAaAF3YsRnbiHLsRAitMAKCiLboJkQECM/jpYsY3WPfvUgLXkACgg3ql
 OK2XeQOiEeXtT76rV4t2WR4=
 =ivrA
 -----END PGP SIGNATURE-----
mergetag object a38d6181ff27824c79fc7df825164a212eff6a3f
 type commit
 tag v2.6.22-rc7
 tagger Linus Torvalds <torvalds@woody.linux-foundation.org> 1183319674 +0000
 
 Linux 2.6.22-rc7
 -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v1.4.7 (GNU/Linux)
 
 iD8DBQBGiAaAF3YsRnbiHLsRAitMAKCiLboJkQECM/jpYsY3WPfvUgLXkACgg3ql
 OK2XeQOiEeXtT76rV4t2WR4=
 =ivrA
 -----END PGP SIGNATURE-----

Merge ../b
""",
            commit.as_raw_string(),
        )

    def test_deserialize_mergetag(self):
        tag = make_object(
            Tag,
            object=(Commit, b"a38d6181ff27824c79fc7df825164a212eff6a3f"),
            object_type_name=b"commit",
            name=b"v2.6.22-rc7",
            tag_time=1183319674,
            tag_timezone=0,
            tagger=b"Linus Torvalds <torvalds@woody.linux-foundation.org>",
            message=default_message,
        )
        commit = self.make_commit(mergetag=[tag])

        d = Commit()
        d._deserialize(commit.as_raw_chunks())
        self.assertEqual(commit, d)

    def test_deserialize_mergetags(self):
        tag = make_object(
            Tag,
            object=(Commit, b"a38d6181ff27824c79fc7df825164a212eff6a3f"),
            object_type_name=b"commit",
            name=b"v2.6.22-rc7",
            tag_time=1183319674,
            tag_timezone=0,
            tagger=b"Linus Torvalds <torvalds@woody.linux-foundation.org>",
            message=default_message,
        )
        commit = self.make_commit(mergetag=[tag, tag])

        d = Commit()
        d._deserialize(commit.as_raw_chunks())
        self.assertEqual(commit, d)


default_committer = b"James Westby <jw+debian@jameswestby.net> 1174773719 +0000"


class CommitParseTests(ShaFileCheckTests):
    def make_commit_lines(
        self,
        tree=b"d80c186a03f423a81b39df39dc87fd269736ca86",
        parents=[
            b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
            b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
        ],
        author=default_committer,
        committer=default_committer,
        encoding=None,
        message=b"Merge ../b\n",
        extra=None,
    ):
        lines = []
        if tree is not None:
            lines.append(b"tree " + tree)
        if parents is not None:
            lines.extend(b"parent " + p for p in parents)
        if author is not None:
            lines.append(b"author " + author)
        if committer is not None:
            lines.append(b"committer " + committer)
        if encoding is not None:
            lines.append(b"encoding " + encoding)
        if extra is not None:
            for name, value in sorted(extra.items()):
                lines.append(name + b" " + value)
        lines.append(b"")
        if message is not None:
            lines.append(message)
        return lines

    def make_commit_text(self, **kwargs):
        return b"\n".join(self.make_commit_lines(**kwargs))

    def test_simple(self):
        c = Commit.from_string(self.make_commit_text())
        self.assertEqual(b"Merge ../b\n", c.message)
        self.assertEqual(b"James Westby <jw+debian@jameswestby.net>", c.author)
        self.assertEqual(b"James Westby <jw+debian@jameswestby.net>", c.committer)
        self.assertEqual(b"d80c186a03f423a81b39df39dc87fd269736ca86", c.tree)
        self.assertEqual(
            [
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
            ],
            c.parents,
        )
        expected_time = datetime.datetime(2007, 3, 24, 22, 1, 59)
        self.assertEqual(
            expected_time, datetime.datetime.utcfromtimestamp(c.commit_time)
        )
        self.assertEqual(0, c.commit_timezone)
        self.assertEqual(
            expected_time, datetime.datetime.utcfromtimestamp(c.author_time)
        )
        self.assertEqual(0, c.author_timezone)
        self.assertEqual(None, c.encoding)

    def test_custom(self):
        c = Commit.from_string(self.make_commit_text(extra={b"extra-field": b"data"}))
        self.assertEqual([(b"extra-field", b"data")], c._extra)

    def test_encoding(self):
        c = Commit.from_string(self.make_commit_text(encoding=b"UTF-8"))
        self.assertEqual(b"UTF-8", c.encoding)

    def test_check(self):
        self.assertCheckSucceeds(Commit, self.make_commit_text())
        self.assertCheckSucceeds(Commit, self.make_commit_text(parents=None))
        self.assertCheckSucceeds(Commit, self.make_commit_text(encoding=b"UTF-8"))

        self.assertCheckFails(Commit, self.make_commit_text(tree=b"xxx"))
        self.assertCheckFails(Commit, self.make_commit_text(parents=[a_sha, b"xxx"]))
        bad_committer = b"some guy without an email address 1174773719 +0000"
        self.assertCheckFails(Commit, self.make_commit_text(committer=bad_committer))
        self.assertCheckFails(Commit, self.make_commit_text(author=bad_committer))
        self.assertCheckFails(Commit, self.make_commit_text(author=None))
        self.assertCheckFails(Commit, self.make_commit_text(committer=None))
        self.assertCheckFails(
            Commit, self.make_commit_text(author=None, committer=None)
        )

    def test_check_duplicates(self):
        # duplicate each of the header fields
        for i in range(5):
            lines = self.make_commit_lines(parents=[a_sha], encoding=b"UTF-8")
            lines.insert(i, lines[i])
            text = b"\n".join(lines)
            if lines[i].startswith(b"parent"):
                # duplicate parents are ok for now
                self.assertCheckSucceeds(Commit, text)
            else:
                self.assertCheckFails(Commit, text)

    def test_check_order(self):
        lines = self.make_commit_lines(parents=[a_sha], encoding=b"UTF-8")
        headers = lines[:5]
        rest = lines[5:]
        # of all possible permutations, ensure only the original succeeds
        for perm in permutations(headers):
            perm = list(perm)
            text = b"\n".join(perm + rest)
            if perm == headers:
                self.assertCheckSucceeds(Commit, text)
            else:
                self.assertCheckFails(Commit, text)

    def test_check_commit_with_unparseable_time(self):
        identity_with_wrong_time = (
            b"Igor Sysoev <igor@sysoev.ru> 18446743887488505614+42707004"
        )

        # Those fail at reading time
        self.assertCheckFails(
            Commit,
            self.make_commit_text(
                author=default_committer, committer=identity_with_wrong_time
            ),
        )
        self.assertCheckFails(
            Commit,
            self.make_commit_text(
                author=identity_with_wrong_time, committer=default_committer
            ),
        )

    def test_check_commit_with_overflow_date(self):
        """Date with overflow should raise an ObjectFormatException when checked"""
        identity_with_wrong_time = (
            b"Igor Sysoev <igor@sysoev.ru> 18446743887488505614 +42707004"
        )
        commit0 = Commit.from_string(
            self.make_commit_text(
                author=identity_with_wrong_time, committer=default_committer
            )
        )
        commit1 = Commit.from_string(
            self.make_commit_text(
                author=default_committer, committer=identity_with_wrong_time
            )
        )

        # Those fails when triggering the check() method
        for commit in [commit0, commit1]:
            with self.assertRaises(ObjectFormatException):
                commit.check()

    def test_mangled_author_line(self):
        """Mangled author line should successfully parse"""
        author_line = (
            b'Karl MacMillan <kmacmill@redhat.com> <"Karl MacMillan '
            b'<kmacmill@redhat.com>"> 1197475547 -0500'
        )
        expected_identity = (
            b'Karl MacMillan <kmacmill@redhat.com> <"Karl MacMillan '
            b'<kmacmill@redhat.com>">'
        )
        commit = Commit.from_string(self.make_commit_text(author=author_line))

        # The commit parses properly
        self.assertEqual(commit.author, expected_identity)

        # But the check fails because the author identity is bogus
        with self.assertRaises(ObjectFormatException):
            commit.check()

    def test_parse_gpgsig(self):
        c = Commit.from_string(
            b"""tree aaff74984cccd156a469afa7d9ab10e4777beb24
author Jelmer Vernooij <jelmer@samba.org> 1412179807 +0200
committer Jelmer Vernooij <jelmer@samba.org> 1412179807 +0200
gpgsig -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v1
 
 iQIcBAABCgAGBQJULCdfAAoJEACAbyvXKaRXuKwP/RyP9PA49uAvu8tQVCC/uBa8
 vi975+xvO14R8Pp8k2nps7lSxCdtCd+xVT1VRHs0wNhOZo2YCVoU1HATkPejqSeV
 NScTHcxnk4/+bxyfk14xvJkNp7FlQ3npmBkA+lbV0Ubr33rvtIE5jiJPyz+SgWAg
 xdBG2TojV0squj00GoH/euK6aX7GgZtwdtpTv44haCQdSuPGDcI4TORqR6YSqvy3
 GPE+3ZqXPFFb+KILtimkxitdwB7CpwmNse2vE3rONSwTvi8nq3ZoQYNY73CQGkUy
 qoFU0pDtw87U3niFin1ZccDgH0bB6624sLViqrjcbYJeg815Htsu4rmzVaZADEVC
 XhIO4MThebusdk0AcNGjgpf3HRHk0DPMDDlIjm+Oao0cqovvF6VyYmcb0C+RmhJj
 dodLXMNmbqErwTk3zEkW0yZvNIYXH7m9SokPCZa4eeIM7be62X6h1mbt0/IU6Th+
 v18fS0iTMP/Viug5und+05C/v04kgDo0CPphAbXwWMnkE4B6Tl9sdyUYXtvQsL7x
 0+WP1gL27ANqNZiI07Kz/BhbBAQI/+2TFT7oGr0AnFPQ5jHp+3GpUf6OKuT1wT3H
 ND189UFuRuubxb42vZhpcXRbqJVWnbECTKVUPsGZqat3enQUB63uM4i6/RdONDZA
 fDeF1m4qYs+cUXKNUZ03
 =X6RT
 -----END PGP SIGNATURE-----

foo
"""
        )
        self.assertEqual(b"foo\n", c.message)
        self.assertEqual([], c._extra)
        self.assertEqual(
            b"""-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAABCgAGBQJULCdfAAoJEACAbyvXKaRXuKwP/RyP9PA49uAvu8tQVCC/uBa8
vi975+xvO14R8Pp8k2nps7lSxCdtCd+xVT1VRHs0wNhOZo2YCVoU1HATkPejqSeV
NScTHcxnk4/+bxyfk14xvJkNp7FlQ3npmBkA+lbV0Ubr33rvtIE5jiJPyz+SgWAg
xdBG2TojV0squj00GoH/euK6aX7GgZtwdtpTv44haCQdSuPGDcI4TORqR6YSqvy3
GPE+3ZqXPFFb+KILtimkxitdwB7CpwmNse2vE3rONSwTvi8nq3ZoQYNY73CQGkUy
qoFU0pDtw87U3niFin1ZccDgH0bB6624sLViqrjcbYJeg815Htsu4rmzVaZADEVC
XhIO4MThebusdk0AcNGjgpf3HRHk0DPMDDlIjm+Oao0cqovvF6VyYmcb0C+RmhJj
dodLXMNmbqErwTk3zEkW0yZvNIYXH7m9SokPCZa4eeIM7be62X6h1mbt0/IU6Th+
v18fS0iTMP/Viug5und+05C/v04kgDo0CPphAbXwWMnkE4B6Tl9sdyUYXtvQsL7x
0+WP1gL27ANqNZiI07Kz/BhbBAQI/+2TFT7oGr0AnFPQ5jHp+3GpUf6OKuT1wT3H
ND189UFuRuubxb42vZhpcXRbqJVWnbECTKVUPsGZqat3enQUB63uM4i6/RdONDZA
fDeF1m4qYs+cUXKNUZ03
=X6RT
-----END PGP SIGNATURE-----""",
            c.gpgsig,
        )

    def test_parse_header_trailing_newline(self):
        c = Commit.from_string(
            b"""\
tree a7d6277f78d3ecd0230a1a5df6db00b1d9c521ac
parent c09b6dec7a73760fbdb478383a3c926b18db8bbe
author Neil Matatall <oreoshake@github.com> 1461964057 -1000
committer Neil Matatall <oreoshake@github.com> 1461964057 -1000
gpgsig -----BEGIN PGP SIGNATURE-----
 
 wsBcBAABCAAQBQJXI80ZCRA6pcNDcVZ70gAAarcIABs72xRX3FWeox349nh6ucJK
 CtwmBTusez2Zwmq895fQEbZK7jpaGO5TRO4OvjFxlRo0E08UFx3pxZHSpj6bsFeL
 hHsDXnCaotphLkbgKKRdGZo7tDqM84wuEDlh4MwNe7qlFC7bYLDyysc81ZX5lpMm
 2MFF1TvjLAzSvkT7H1LPkuR3hSvfCYhikbPOUNnKOo0sYjeJeAJ/JdAVQ4mdJIM0
 gl3REp9+A+qBEpNQI7z94Pg5Bc5xenwuDh3SJgHvJV6zBWupWcdB3fAkVd4TPnEZ
 nHxksHfeNln9RKseIDcy4b2ATjhDNIJZARHNfr6oy4u3XPW4svRqtBsLoMiIeuI=
 =ms6q
 -----END PGP SIGNATURE-----
 

3.3.0 version bump and docs
"""
        )
        self.assertEqual([], c._extra)
        self.assertEqual(
            b"""\
-----BEGIN PGP SIGNATURE-----

wsBcBAABCAAQBQJXI80ZCRA6pcNDcVZ70gAAarcIABs72xRX3FWeox349nh6ucJK
CtwmBTusez2Zwmq895fQEbZK7jpaGO5TRO4OvjFxlRo0E08UFx3pxZHSpj6bsFeL
hHsDXnCaotphLkbgKKRdGZo7tDqM84wuEDlh4MwNe7qlFC7bYLDyysc81ZX5lpMm
2MFF1TvjLAzSvkT7H1LPkuR3hSvfCYhikbPOUNnKOo0sYjeJeAJ/JdAVQ4mdJIM0
gl3REp9+A+qBEpNQI7z94Pg5Bc5xenwuDh3SJgHvJV6zBWupWcdB3fAkVd4TPnEZ
nHxksHfeNln9RKseIDcy4b2ATjhDNIJZARHNfr6oy4u3XPW4svRqtBsLoMiIeuI=
=ms6q
-----END PGP SIGNATURE-----\n""",
            c.gpgsig,
        )


_TREE_ITEMS = {
    b"a.c": (0o100755, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
    b"a": (stat.S_IFDIR, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
    b"a/c": (stat.S_IFDIR, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
}

_SORTED_TREE_ITEMS = [
    TreeEntry(b"a.c", 0o100755, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
    TreeEntry(b"a", stat.S_IFDIR, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
    TreeEntry(b"a/c", stat.S_IFDIR, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
]


class TreeTests(ShaFileCheckTests):
    def test_add(self):
        myhexsha = b"d80c186a03f423a81b39df39dc87fd269736ca86"
        x = Tree()
        x.add(b"myname", 0o100755, myhexsha)
        self.assertEqual(x[b"myname"], (0o100755, myhexsha))
        self.assertEqual(b"100755 myname\0" + hex_to_sha(myhexsha), x.as_raw_string())

    def test_simple(self):
        myhexsha = b"d80c186a03f423a81b39df39dc87fd269736ca86"
        x = Tree()
        x[b"myname"] = (0o100755, myhexsha)
        self.assertEqual(b"100755 myname\0" + hex_to_sha(myhexsha), x.as_raw_string())
        self.assertEqual(b"100755 myname\0" + hex_to_sha(myhexsha), bytes(x))

    def test_tree_update_id(self):
        x = Tree()
        x[b"a.c"] = (0o100755, b"d80c186a03f423a81b39df39dc87fd269736ca86")
        self.assertEqual(b"0c5c6bc2c081accfbc250331b19e43b904ab9cdd", x.id)
        x[b"a.b"] = (stat.S_IFDIR, b"d80c186a03f423a81b39df39dc87fd269736ca86")
        self.assertEqual(b"07bfcb5f3ada15bbebdfa3bbb8fd858a363925c8", x.id)

    def test_tree_iteritems_dir_sort(self):
        x = Tree()
        for name, item in _TREE_ITEMS.items():
            x[name] = item
        self.assertEqual(_SORTED_TREE_ITEMS, x.items())

    def test_tree_items_dir_sort(self):
        x = Tree()
        for name, item in _TREE_ITEMS.items():
            x[name] = item
        self.assertEqual(_SORTED_TREE_ITEMS, x.items())

    def _do_test_parse_tree(self, parse_tree):
        dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "trees")
        o = Tree.from_path(hex_to_filename(dir, tree_sha))
        self.assertEqual(
            [(b"a", 0o100644, a_sha), (b"b", 0o100644, b_sha)],
            list(parse_tree(o.as_raw_string())),
        )
        # test a broken tree that has a leading 0 on the file mode
        broken_tree = b"0100644 foo\0" + hex_to_sha(a_sha)

        def eval_parse_tree(*args, **kwargs):
            return list(parse_tree(*args, **kwargs))

        self.assertEqual([(b"foo", 0o100644, a_sha)], eval_parse_tree(broken_tree))
        self.assertRaises(
            ObjectFormatException, eval_parse_tree, broken_tree, strict=True
        )

    test_parse_tree = functest_builder(_do_test_parse_tree, _parse_tree_py)
    test_parse_tree_extension = ext_functest_builder(_do_test_parse_tree, parse_tree)

    def _do_test_sorted_tree_items(self, sorted_tree_items):
        def do_sort(entries):
            return list(sorted_tree_items(entries, False))

        actual = do_sort(_TREE_ITEMS)
        self.assertEqual(_SORTED_TREE_ITEMS, actual)
        self.assertIsInstance(actual[0], TreeEntry)

        # C/Python implementations may differ in specific error types, but
        # should all error on invalid inputs.
        # For example, the C implementation has stricter type checks, so may
        # raise TypeError where the Python implementation raises
        # AttributeError.
        errors = (TypeError, ValueError, AttributeError)
        self.assertRaises(errors, do_sort, b"foo")
        self.assertRaises(errors, do_sort, {b"foo": (1, 2, 3)})

        myhexsha = b"d80c186a03f423a81b39df39dc87fd269736ca86"
        self.assertRaises(errors, do_sort, {b"foo": (b"xxx", myhexsha)})
        self.assertRaises(errors, do_sort, {b"foo": (0o100755, 12345)})

    test_sorted_tree_items = functest_builder(
        _do_test_sorted_tree_items, _sorted_tree_items_py
    )
    test_sorted_tree_items_extension = ext_functest_builder(
        _do_test_sorted_tree_items, sorted_tree_items
    )

    def _do_test_sorted_tree_items_name_order(self, sorted_tree_items):
        self.assertEqual(
            [
                TreeEntry(
                    b"a",
                    stat.S_IFDIR,
                    b"d80c186a03f423a81b39df39dc87fd269736ca86",
                ),
                TreeEntry(
                    b"a.c",
                    0o100755,
                    b"d80c186a03f423a81b39df39dc87fd269736ca86",
                ),
                TreeEntry(
                    b"a/c",
                    stat.S_IFDIR,
                    b"d80c186a03f423a81b39df39dc87fd269736ca86",
                ),
            ],
            list(sorted_tree_items(_TREE_ITEMS, True)),
        )

    test_sorted_tree_items_name_order = functest_builder(
        _do_test_sorted_tree_items_name_order, _sorted_tree_items_py
    )
    test_sorted_tree_items_name_order_extension = ext_functest_builder(
        _do_test_sorted_tree_items_name_order, sorted_tree_items
    )

    def test_check(self):
        t = Tree
        sha = hex_to_sha(a_sha)

        # filenames
        self.assertCheckSucceeds(t, b"100644 .a\0" + sha)
        self.assertCheckFails(t, b"100644 \0" + sha)
        self.assertCheckFails(t, b"100644 .\0" + sha)
        self.assertCheckFails(t, b"100644 a/a\0" + sha)
        self.assertCheckFails(t, b"100644 ..\0" + sha)
        self.assertCheckFails(t, b"100644 .git\0" + sha)

        # modes
        self.assertCheckSucceeds(t, b"100644 a\0" + sha)
        self.assertCheckSucceeds(t, b"100755 a\0" + sha)
        self.assertCheckSucceeds(t, b"160000 a\0" + sha)
        # TODO more whitelisted modes
        self.assertCheckFails(t, b"123456 a\0" + sha)
        self.assertCheckFails(t, b"123abc a\0" + sha)
        # should fail check, but parses ok
        self.assertCheckFails(t, b"0100644 foo\0" + sha)

        # shas
        self.assertCheckFails(t, b"100644 a\0" + (b"x" * 5))
        self.assertCheckFails(t, b"100644 a\0" + (b"x" * 18) + b"\0")
        self.assertCheckFails(t, b"100644 a\0" + (b"x" * 21) + b"\n100644 b\0" + sha)

        # ordering
        sha2 = hex_to_sha(b_sha)
        self.assertCheckSucceeds(t, b"100644 a\0" + sha + b"\n100644 b\0" + sha)
        self.assertCheckSucceeds(t, b"100644 a\0" + sha + b"\n100644 b\0" + sha2)
        self.assertCheckFails(t, b"100644 a\0" + sha + b"\n100755 a\0" + sha2)
        self.assertCheckFails(t, b"100644 b\0" + sha2 + b"\n100644 a\0" + sha)

    def test_iter(self):
        t = Tree()
        t[b"foo"] = (0o100644, a_sha)
        self.assertEqual({b"foo"}, set(t))


class TagSerializeTests(TestCase):
    def test_serialize_simple(self):
        x = make_object(
            Tag,
            tagger=b"Jelmer Vernooij <jelmer@samba.org>",
            name=b"0.1",
            message=b"Tag 0.1",
            object=(Blob, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
            tag_time=423423423,
            tag_timezone=0,
        )
        self.assertEqual(
            (
                b"object d80c186a03f423a81b39df39dc87fd269736ca86\n"
                b"type blob\n"
                b"tag 0.1\n"
                b"tagger Jelmer Vernooij <jelmer@samba.org> "
                b"423423423 +0000\n"
                b"\n"
                b"Tag 0.1"
            ),
            x.as_raw_string(),
        )

    def test_serialize_none_message(self):
        x = make_object(
            Tag,
            tagger=b"Jelmer Vernooij <jelmer@samba.org>",
            name=b"0.1",
            message=None,
            object=(Blob, b"d80c186a03f423a81b39df39dc87fd269736ca86"),
            tag_time=423423423,
            tag_timezone=0,
        )
        self.assertEqual(
            (
                b"object d80c186a03f423a81b39df39dc87fd269736ca86\n"
                b"type blob\n"
                b"tag 0.1\n"
                b"tagger Jelmer Vernooij <jelmer@samba.org> "
                b"423423423 +0000\n"
            ),
            x.as_raw_string(),
        )


default_tagger = (
    b"Linus Torvalds <torvalds@woody.linux-foundation.org> " b"1183319674 -0700"
)
default_message = b"""Linux 2.6.22-rc7
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1.4.7 (GNU/Linux)

iD8DBQBGiAaAF3YsRnbiHLsRAitMAKCiLboJkQECM/jpYsY3WPfvUgLXkACgg3ql
OK2XeQOiEeXtT76rV4t2WR4=
=ivrA
-----END PGP SIGNATURE-----
"""


class TagParseTests(ShaFileCheckTests):
    def make_tag_lines(
        self,
        object_sha=b"a38d6181ff27824c79fc7df825164a212eff6a3f",
        object_type_name=b"commit",
        name=b"v2.6.22-rc7",
        tagger=default_tagger,
        message=default_message,
    ):
        lines = []
        if object_sha is not None:
            lines.append(b"object " + object_sha)
        if object_type_name is not None:
            lines.append(b"type " + object_type_name)
        if name is not None:
            lines.append(b"tag " + name)
        if tagger is not None:
            lines.append(b"tagger " + tagger)
        if message is not None:
            lines.append(b"")
            lines.append(message)
        return lines

    def make_tag_text(self, **kwargs):
        return b"\n".join(self.make_tag_lines(**kwargs))

    def test_parse(self):
        x = Tag()
        x.set_raw_string(self.make_tag_text())
        self.assertEqual(
            b"Linus Torvalds <torvalds@woody.linux-foundation.org>", x.tagger
        )
        self.assertEqual(b"v2.6.22-rc7", x.name)
        object_type, object_sha = x.object
        self.assertEqual(b"a38d6181ff27824c79fc7df825164a212eff6a3f", object_sha)
        self.assertEqual(Commit, object_type)
        self.assertEqual(
            datetime.datetime.utcfromtimestamp(x.tag_time),
            datetime.datetime(2007, 7, 1, 19, 54, 34),
        )
        self.assertEqual(-25200, x.tag_timezone)

    def test_parse_no_tagger(self):
        x = Tag()
        x.set_raw_string(self.make_tag_text(tagger=None))
        self.assertEqual(None, x.tagger)
        self.assertEqual(b"v2.6.22-rc7", x.name)
        self.assertEqual(None, x.tag_time)

    def test_parse_no_message(self):
        x = Tag()
        x.set_raw_string(self.make_tag_text(message=None))
        self.assertEqual(None, x.message)
        self.assertEqual(
            b"Linus Torvalds <torvalds@woody.linux-foundation.org>", x.tagger
        )
        self.assertEqual(
            datetime.datetime.utcfromtimestamp(x.tag_time),
            datetime.datetime(2007, 7, 1, 19, 54, 34),
        )
        self.assertEqual(-25200, x.tag_timezone)
        self.assertEqual(b"v2.6.22-rc7", x.name)

    def test_check(self):
        self.assertCheckSucceeds(Tag, self.make_tag_text())
        self.assertCheckFails(Tag, self.make_tag_text(object_sha=None))
        self.assertCheckFails(Tag, self.make_tag_text(object_type_name=None))
        self.assertCheckFails(Tag, self.make_tag_text(name=None))
        self.assertCheckFails(Tag, self.make_tag_text(name=b""))
        self.assertCheckFails(Tag, self.make_tag_text(object_type_name=b"foobar"))
        self.assertCheckFails(
            Tag,
            self.make_tag_text(
                tagger=b"some guy without an email address 1183319674 -0700"
            ),
        )
        self.assertCheckFails(
            Tag,
            self.make_tag_text(
                tagger=(
                    b"Linus Torvalds <torvalds@woody.linux-foundation.org> "
                    b"Sun 7 Jul 2007 12:54:34 +0700"
                )
            ),
        )
        self.assertCheckFails(Tag, self.make_tag_text(object_sha=b"xxx"))

    def test_check_tag_with_unparseable_field(self):
        self.assertCheckFails(
            Tag,
            self.make_tag_text(
                tagger=(
                    b"Linus Torvalds <torvalds@woody.linux-foundation.org> "
                    b"423423+0000"
                )
            ),
        )

    def test_check_tag_with_overflow_time(self):
        """Date with overflow should raise an ObjectFormatException when checked"""
        author = "Some Dude <some@dude.org> {} +0000".format(MAX_TIME + 1)
        tag = Tag.from_string(self.make_tag_text(tagger=(author.encode())))
        with self.assertRaises(ObjectFormatException):
            tag.check()

    def test_check_duplicates(self):
        # duplicate each of the header fields
        for i in range(4):
            lines = self.make_tag_lines()
            lines.insert(i, lines[i])
            self.assertCheckFails(Tag, b"\n".join(lines))

    def test_check_order(self):
        lines = self.make_tag_lines()
        headers = lines[:4]
        rest = lines[4:]
        # of all possible permutations, ensure only the original succeeds
        for perm in permutations(headers):
            perm = list(perm)
            text = b"\n".join(perm + rest)
            if perm == headers:
                self.assertCheckSucceeds(Tag, text)
            else:
                self.assertCheckFails(Tag, text)

    def test_tree_copy_after_update(self):
        """Check Tree.id is correctly updated when the tree is copied after updated."""
        shas = []
        tree = Tree()
        shas.append(tree.id)
        tree.add(b"data", 0o644, Blob().id)
        copied = tree.copy()
        shas.append(tree.id)
        shas.append(copied.id)

        self.assertNotIn(shas[0], shas[1:])
        self.assertEqual(shas[1], shas[2])


class CheckTests(TestCase):
    def test_check_hexsha(self):
        check_hexsha(a_sha, "failed to check good sha")
        self.assertRaises(
            ObjectFormatException, check_hexsha, b"1" * 39, "sha too short"
        )
        self.assertRaises(
            ObjectFormatException, check_hexsha, b"1" * 41, "sha too long"
        )
        self.assertRaises(
            ObjectFormatException,
            check_hexsha,
            b"x" * 40,
            "invalid characters",
        )

    def test_check_identity(self):
        check_identity(
            b"Dave Borowitz <dborowitz@google.com>",
            "failed to check good identity",
        )
        check_identity(b" <dborowitz@google.com>", "failed to check good identity")
        self.assertRaises(
            ObjectFormatException, check_identity, b'<dborowitz@google.com>', 'no space before email'
        )
        self.assertRaises(
            ObjectFormatException, check_identity, b"Dave Borowitz", "no email"
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"Dave Borowitz <dborowitz",
            "incomplete email",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"dborowitz@google.com>",
            "incomplete email",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"Dave Borowitz <<dborowitz@google.com>",
            "typo",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"Dave Borowitz <dborowitz@google.com>>",
            "typo",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"Dave Borowitz <dborowitz@google.com>xxx",
            "trailing characters",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b"Dave Borowitz <dborowitz@google.com>xxx",
            "trailing characters",
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b'Dave<Borowitz <dborowitz@google.com>',
            'reserved byte in name',
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b'Dave>Borowitz <dborowitz@google.com>',
            'reserved byte in name',
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b'Dave\0Borowitz <dborowitz@google.com>',
            'null byte',
        )
        self.assertRaises(
            ObjectFormatException,
            check_identity,
            b'Dave\nBorowitz <dborowitz@google.com>',
            'newline byte',
        )


class TimezoneTests(TestCase):
    def test_parse_timezone_utc(self):
        self.assertEqual((0, False), parse_timezone(b"+0000"))

    def test_parse_timezone_utc_negative(self):
        self.assertEqual((0, True), parse_timezone(b"-0000"))

    def test_generate_timezone_utc(self):
        self.assertEqual(b"+0000", format_timezone(0))

    def test_generate_timezone_utc_negative(self):
        self.assertEqual(b"-0000", format_timezone(0, True))

    def test_parse_timezone_cet(self):
        self.assertEqual((60 * 60, False), parse_timezone(b"+0100"))

    def test_format_timezone_cet(self):
        self.assertEqual(b"+0100", format_timezone(60 * 60))

    def test_format_timezone_pdt(self):
        self.assertEqual(b"-0400", format_timezone(-4 * 60 * 60))

    def test_parse_timezone_pdt(self):
        self.assertEqual((-4 * 60 * 60, False), parse_timezone(b"-0400"))

    def test_format_timezone_pdt_half(self):
        self.assertEqual(b"-0440", format_timezone(int(((-4 * 60) - 40) * 60)))

    def test_format_timezone_double_negative(self):
        self.assertEqual(b"--700", format_timezone(int((7 * 60) * 60), True))

    def test_parse_timezone_pdt_half(self):
        self.assertEqual((((-4 * 60) - 40) * 60, False), parse_timezone(b"-0440"))

    def test_parse_timezone_double_negative(self):
        self.assertEqual((int((7 * 60) * 60), False), parse_timezone(b"+700"))
        self.assertEqual((int((7 * 60) * 60), True), parse_timezone(b"--700"))


class ShaFileCopyTests(TestCase):
    def assert_copy(self, orig):
        oclass = object_class(orig.type_num)

        copy = orig.copy()
        self.assertIsInstance(copy, oclass)
        self.assertEqual(copy, orig)
        self.assertIsNot(copy, orig)

    def test_commit_copy(self):
        attrs = {
            "tree": b"d80c186a03f423a81b39df39dc87fd269736ca86",
            "parents": [
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
            ],
            "author": b"James Westby <jw+debian@jameswestby.net>",
            "committer": b"James Westby <jw+debian@jameswestby.net>",
            "commit_time": 1174773719,
            "author_time": 1174773719,
            "commit_timezone": 0,
            "author_timezone": 0,
            "message": b"Merge ../b\n",
        }
        commit = make_commit(**attrs)
        self.assert_copy(commit)

    def test_blob_copy(self):
        blob = make_object(Blob, data=b"i am a blob")
        self.assert_copy(blob)

    def test_tree_copy(self):
        blob = make_object(Blob, data=b"i am a blob")
        tree = Tree()
        tree[b"blob"] = (stat.S_IFREG, blob.id)
        self.assert_copy(tree)

    def test_tag_copy(self):
        tag = make_object(
            Tag,
            name=b"tag",
            message=b"",
            tagger=b"Tagger <test@example.com>",
            tag_time=12345,
            tag_timezone=0,
            object=(Commit, b"0" * 40),
        )
        self.assert_copy(tag)


class ShaFileSerializeTests(TestCase):
    """`ShaFile` objects only gets serialized once if they haven't changed."""

    @contextmanager
    def assert_serialization_on_change(
        self, obj, needs_serialization_after_change=True
    ):
        old_id = obj.id
        self.assertFalse(obj._needs_serialization)

        yield obj

        if needs_serialization_after_change:
            self.assertTrue(obj._needs_serialization)
        else:
            self.assertFalse(obj._needs_serialization)
        new_id = obj.id
        self.assertFalse(obj._needs_serialization)
        self.assertNotEqual(old_id, new_id)

    def test_commit_serialize(self):
        attrs = {
            "tree": b"d80c186a03f423a81b39df39dc87fd269736ca86",
            "parents": [
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
            ],
            "author": b"James Westby <jw+debian@jameswestby.net>",
            "committer": b"James Westby <jw+debian@jameswestby.net>",
            "commit_time": 1174773719,
            "author_time": 1174773719,
            "commit_timezone": 0,
            "author_timezone": 0,
            "message": b"Merge ../b\n",
        }
        commit = make_commit(**attrs)

        with self.assert_serialization_on_change(commit):
            commit.parents = [b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd"]

    def test_blob_serialize(self):
        blob = make_object(Blob, data=b"i am a blob")

        with self.assert_serialization_on_change(
            blob, needs_serialization_after_change=False
        ):
            blob.data = b"i am another blob"

    def test_tree_serialize(self):
        blob = make_object(Blob, data=b"i am a blob")
        tree = Tree()
        tree[b"blob"] = (stat.S_IFREG, blob.id)

        with self.assert_serialization_on_change(tree):
            tree[b"blob2"] = (stat.S_IFREG, blob.id)

    def test_tag_serialize(self):
        tag = make_object(
            Tag,
            name=b"tag",
            message=b"",
            tagger=b"Tagger <test@example.com>",
            tag_time=12345,
            tag_timezone=0,
            object=(Commit, b"0" * 40),
        )

        with self.assert_serialization_on_change(tag):
            tag.message = b"new message"

    def test_tag_serialize_time_error(self):
        with self.assertRaises(ObjectFormatException):
            tag = make_object(
                Tag,
                name=b"tag",
                message=b"some message",
                tagger=b"Tagger <test@example.com> 1174773719+0000",
                object=(Commit, b"0" * 40),
            )
            tag._deserialize(tag._serialize())


class PrettyFormatTreeEntryTests(TestCase):
    def test_format(self):
        self.assertEqual(
            "40000 tree 40820c38cfb182ce6c8b261555410d8382a5918b\tfoo\n",
            pretty_format_tree_entry(
                b"foo", 0o40000, b"40820c38cfb182ce6c8b261555410d8382a5918b"
            ),
        )
