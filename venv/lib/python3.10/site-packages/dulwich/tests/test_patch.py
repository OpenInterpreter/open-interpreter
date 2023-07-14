# test_patch.py -- tests for patch.py
# Copyright (C) 2010 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for patch.py."""

from io import BytesIO, StringIO

from dulwich.tests import SkipTest, TestCase

from ..object_store import MemoryObjectStore
from ..objects import S_IFGITLINK, Blob, Commit, Tree
from ..patch import (get_summary, git_am_patch_split, write_blob_diff,
                     write_commit_patch, write_object_diff, write_tree_diff)


class WriteCommitPatchTests(TestCase):
    def test_simple_bytesio(self):
        f = BytesIO()
        c = Commit()
        c.committer = c.author = b"Jelmer <jelmer@samba.org>"
        c.commit_time = c.author_time = 1271350201
        c.commit_timezone = c.author_timezone = 0
        c.message = b"This is the first line\nAnd this is the second line.\n"
        c.tree = Tree().id
        write_commit_patch(f, c, b"CONTENTS", (1, 1), version="custom")
        f.seek(0)
        lines = f.readlines()
        self.assertTrue(
            lines[0].startswith(b"From 0b0d34d1b5b596c928adc9a727a4b9e03d025298")
        )
        self.assertEqual(lines[1], b"From: Jelmer <jelmer@samba.org>\n")
        self.assertTrue(lines[2].startswith(b"Date: "))
        self.assertEqual(
            [
                b"Subject: [PATCH 1/1] This is the first line\n",
                b"And this is the second line.\n",
                b"\n",
                b"\n",
                b"---\n",
            ],
            lines[3:8],
        )
        self.assertEqual([b"CONTENTS-- \n", b"custom\n"], lines[-2:])
        if len(lines) >= 12:
            # diffstat may not be present
            self.assertEqual(lines[8], b" 0 files changed\n")


class ReadGitAmPatch(TestCase):
    def test_extract_string(self):
        text = b"""\
From ff643aae102d8870cac88e8f007e70f58f3a7363 Mon Sep 17 00:00:00 2001
From: Jelmer Vernooij <jelmer@samba.org>
Date: Thu, 15 Apr 2010 15:40:28 +0200
Subject: [PATCH 1/2] Remove executable bit from prey.ico (triggers a warning).

---
 pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

-- 
1.7.0.4
"""
        c, diff, version = git_am_patch_split(StringIO(text.decode("utf-8")), "utf-8")
        self.assertEqual(b"Jelmer Vernooij <jelmer@samba.org>", c.committer)
        self.assertEqual(b"Jelmer Vernooij <jelmer@samba.org>", c.author)
        self.assertEqual(
            b"Remove executable bit from prey.ico " b"(triggers a warning).\n",
            c.message,
        )
        self.assertEqual(
            b""" pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

""",
            diff,
        )
        self.assertEqual(b"1.7.0.4", version)

    def test_extract_bytes(self):
        text = b"""\
From ff643aae102d8870cac88e8f007e70f58f3a7363 Mon Sep 17 00:00:00 2001
From: Jelmer Vernooij <jelmer@samba.org>
Date: Thu, 15 Apr 2010 15:40:28 +0200
Subject: [PATCH 1/2] Remove executable bit from prey.ico (triggers a warning).

---
 pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

-- 
1.7.0.4
"""
        c, diff, version = git_am_patch_split(BytesIO(text))
        self.assertEqual(b"Jelmer Vernooij <jelmer@samba.org>", c.committer)
        self.assertEqual(b"Jelmer Vernooij <jelmer@samba.org>", c.author)
        self.assertEqual(
            b"Remove executable bit from prey.ico " b"(triggers a warning).\n",
            c.message,
        )
        self.assertEqual(
            b""" pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

""",
            diff,
        )
        self.assertEqual(b"1.7.0.4", version)

    def test_extract_spaces(self):
        text = b"""From ff643aae102d8870cac88e8f007e70f58f3a7363 Mon Sep 17 00:00:00 2001
From: Jelmer Vernooij <jelmer@samba.org>
Date: Thu, 15 Apr 2010 15:40:28 +0200
Subject:  [Dulwich-users] [PATCH] Added unit tests for
 dulwich.object_store.tree_lookup_path.

* dulwich/tests/test_object_store.py
  (TreeLookupPathTests): This test case contains a few tests that ensure the
   tree_lookup_path function works as expected.
---
 pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

-- 
1.7.0.4
"""
        c, diff, version = git_am_patch_split(BytesIO(text), "utf-8")
        self.assertEqual(
            b"""\
Added unit tests for dulwich.object_store.tree_lookup_path.

* dulwich/tests/test_object_store.py
  (TreeLookupPathTests): This test case contains a few tests that ensure the
   tree_lookup_path function works as expected.
""",
            c.message,
        )

    def test_extract_pseudo_from_header(self):
        text = b"""From ff643aae102d8870cac88e8f007e70f58f3a7363 Mon Sep 17 00:00:00 2001
From: Jelmer Vernooij <jelmer@samba.org>
Date: Thu, 15 Apr 2010 15:40:28 +0200
Subject:  [Dulwich-users] [PATCH] Added unit tests for
 dulwich.object_store.tree_lookup_path.

From: Jelmer Vernooij <jelmer@debian.org>

* dulwich/tests/test_object_store.py
  (TreeLookupPathTests): This test case contains a few tests that ensure the
   tree_lookup_path function works as expected.
---
 pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

-- 
1.7.0.4
"""
        c, diff, version = git_am_patch_split(BytesIO(text), "utf-8")
        self.assertEqual(b"Jelmer Vernooij <jelmer@debian.org>", c.author)
        self.assertEqual(
            b"""\
Added unit tests for dulwich.object_store.tree_lookup_path.

* dulwich/tests/test_object_store.py
  (TreeLookupPathTests): This test case contains a few tests that ensure the
   tree_lookup_path function works as expected.
""",
            c.message,
        )

    def test_extract_no_version_tail(self):
        text = b"""\
From ff643aae102d8870cac88e8f007e70f58f3a7363 Mon Sep 17 00:00:00 2001
From: Jelmer Vernooij <jelmer@samba.org>
Date: Thu, 15 Apr 2010 15:40:28 +0200
Subject:  [Dulwich-users] [PATCH] Added unit tests for
 dulwich.object_store.tree_lookup_path.

From: Jelmer Vernooij <jelmer@debian.org>

---
 pixmaps/prey.ico |  Bin 9662 -> 9662 bytes
 1 files changed, 0 insertions(+), 0 deletions(-)
 mode change 100755 => 100644 pixmaps/prey.ico

"""
        c, diff, version = git_am_patch_split(BytesIO(text), "utf-8")
        self.assertEqual(None, version)

    def test_extract_mercurial(self):
        raise SkipTest(
            "git_am_patch_split doesn't handle Mercurial patches " "properly yet"
        )
        expected_diff = """\
diff --git a/dulwich/tests/test_patch.py b/dulwich/tests/test_patch.py
--- a/dulwich/tests/test_patch.py
+++ b/dulwich/tests/test_patch.py
@@ -158,7 +158,7 @@
 
 '''
         c, diff, version = git_am_patch_split(BytesIO(text))
-        self.assertIs(None, version)
+        self.assertEqual(None, version)
 
 
 class DiffTests(TestCase):
"""
        text = (
            """\
From dulwich-users-bounces+jelmer=samba.org@lists.launchpad.net \
Mon Nov 29 00:58:18 2010
Date: Sun, 28 Nov 2010 17:57:27 -0600
From: Augie Fackler <durin42@gmail.com>
To: dulwich-users <dulwich-users@lists.launchpad.net>
Subject: [Dulwich-users] [PATCH] test_patch: fix tests on Python 2.6
Content-Transfer-Encoding: 8bit

Change-Id: I5e51313d4ae3a65c3f00c665002a7489121bb0d6

%s

_______________________________________________
Mailing list: https://launchpad.net/~dulwich-users
Post to     : dulwich-users@lists.launchpad.net
Unsubscribe : https://launchpad.net/~dulwich-users
More help   : https://help.launchpad.net/ListHelp

"""
            % expected_diff
        )
        c, diff, version = git_am_patch_split(BytesIO(text))
        self.assertEqual(expected_diff, diff)
        self.assertEqual(None, version)


class DiffTests(TestCase):
    """Tests for write_blob_diff and write_tree_diff."""

    def test_blob_diff(self):
        f = BytesIO()
        write_blob_diff(
            f,
            (b"foo.txt", 0o644, Blob.from_string(b"old\nsame\n")),
            (b"bar.txt", 0o644, Blob.from_string(b"new\nsame\n")),
        )
        self.assertEqual(
            [
                b"diff --git a/foo.txt b/bar.txt",
                b"index 3b0f961..a116b51 644",
                b"--- a/foo.txt",
                b"+++ b/bar.txt",
                b"@@ -1,2 +1,2 @@",
                b"-old",
                b"+new",
                b" same",
            ],
            f.getvalue().splitlines(),
        )

    def test_blob_add(self):
        f = BytesIO()
        write_blob_diff(
            f,
            (None, None, None),
            (b"bar.txt", 0o644, Blob.from_string(b"new\nsame\n")),
        )
        self.assertEqual(
            [
                b"diff --git a/bar.txt b/bar.txt",
                b"new file mode 644",
                b"index 0000000..a116b51",
                b"--- /dev/null",
                b"+++ b/bar.txt",
                b"@@ -0,0 +1,2 @@",
                b"+new",
                b"+same",
            ],
            f.getvalue().splitlines(),
        )

    def test_blob_remove(self):
        f = BytesIO()
        write_blob_diff(
            f,
            (b"bar.txt", 0o644, Blob.from_string(b"new\nsame\n")),
            (None, None, None),
        )
        self.assertEqual(
            [
                b"diff --git a/bar.txt b/bar.txt",
                b"deleted file mode 644",
                b"index a116b51..0000000",
                b"--- a/bar.txt",
                b"+++ /dev/null",
                b"@@ -1,2 +0,0 @@",
                b"-new",
                b"-same",
            ],
            f.getvalue().splitlines(),
        )

    def test_tree_diff(self):
        f = BytesIO()
        store = MemoryObjectStore()
        added = Blob.from_string(b"add\n")
        removed = Blob.from_string(b"removed\n")
        changed1 = Blob.from_string(b"unchanged\nremoved\n")
        changed2 = Blob.from_string(b"unchanged\nadded\n")
        unchanged = Blob.from_string(b"unchanged\n")
        tree1 = Tree()
        tree1.add(b"removed.txt", 0o644, removed.id)
        tree1.add(b"changed.txt", 0o644, changed1.id)
        tree1.add(b"unchanged.txt", 0o644, changed1.id)
        tree2 = Tree()
        tree2.add(b"added.txt", 0o644, added.id)
        tree2.add(b"changed.txt", 0o644, changed2.id)
        tree2.add(b"unchanged.txt", 0o644, changed1.id)
        store.add_objects(
            [
                (o, None)
                for o in [
                    tree1,
                    tree2,
                    added,
                    removed,
                    changed1,
                    changed2,
                    unchanged,
                ]
            ]
        )
        write_tree_diff(f, store, tree1.id, tree2.id)
        self.assertEqual(
            [
                b"diff --git a/added.txt b/added.txt",
                b"new file mode 644",
                b"index 0000000..76d4bb8",
                b"--- /dev/null",
                b"+++ b/added.txt",
                b"@@ -0,0 +1 @@",
                b"+add",
                b"diff --git a/changed.txt b/changed.txt",
                b"index bf84e48..1be2436 644",
                b"--- a/changed.txt",
                b"+++ b/changed.txt",
                b"@@ -1,2 +1,2 @@",
                b" unchanged",
                b"-removed",
                b"+added",
                b"diff --git a/removed.txt b/removed.txt",
                b"deleted file mode 644",
                b"index 2c3f0b3..0000000",
                b"--- a/removed.txt",
                b"+++ /dev/null",
                b"@@ -1 +0,0 @@",
                b"-removed",
            ],
            f.getvalue().splitlines(),
        )

    def test_tree_diff_submodule(self):
        f = BytesIO()
        store = MemoryObjectStore()
        tree1 = Tree()
        tree1.add(
            b"asubmodule",
            S_IFGITLINK,
            b"06d0bdd9e2e20377b3180e4986b14c8549b393e4",
        )
        tree2 = Tree()
        tree2.add(
            b"asubmodule",
            S_IFGITLINK,
            b"cc975646af69f279396d4d5e1379ac6af80ee637",
        )
        store.add_objects([(o, None) for o in [tree1, tree2]])
        write_tree_diff(f, store, tree1.id, tree2.id)
        self.assertEqual(
            [
                b"diff --git a/asubmodule b/asubmodule",
                b"index 06d0bdd..cc97564 160000",
                b"--- a/asubmodule",
                b"+++ b/asubmodule",
                b"@@ -1 +1 @@",
                b"-Subproject commit 06d0bdd9e2e20377b3180e4986b14c8549b393e4",
                b"+Subproject commit cc975646af69f279396d4d5e1379ac6af80ee637",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_blob(self):
        f = BytesIO()
        b1 = Blob.from_string(b"old\nsame\n")
        b2 = Blob.from_string(b"new\nsame\n")
        store = MemoryObjectStore()
        store.add_objects([(b1, None), (b2, None)])
        write_object_diff(
            f, store, (b"foo.txt", 0o644, b1.id), (b"bar.txt", 0o644, b2.id)
        )
        self.assertEqual(
            [
                b"diff --git a/foo.txt b/bar.txt",
                b"index 3b0f961..a116b51 644",
                b"--- a/foo.txt",
                b"+++ b/bar.txt",
                b"@@ -1,2 +1,2 @@",
                b"-old",
                b"+new",
                b" same",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_add_blob(self):
        f = BytesIO()
        store = MemoryObjectStore()
        b2 = Blob.from_string(b"new\nsame\n")
        store.add_object(b2)
        write_object_diff(f, store, (None, None, None), (b"bar.txt", 0o644, b2.id))
        self.assertEqual(
            [
                b"diff --git a/bar.txt b/bar.txt",
                b"new file mode 644",
                b"index 0000000..a116b51",
                b"--- /dev/null",
                b"+++ b/bar.txt",
                b"@@ -0,0 +1,2 @@",
                b"+new",
                b"+same",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_remove_blob(self):
        f = BytesIO()
        b1 = Blob.from_string(b"new\nsame\n")
        store = MemoryObjectStore()
        store.add_object(b1)
        write_object_diff(f, store, (b"bar.txt", 0o644, b1.id), (None, None, None))
        self.assertEqual(
            [
                b"diff --git a/bar.txt b/bar.txt",
                b"deleted file mode 644",
                b"index a116b51..0000000",
                b"--- a/bar.txt",
                b"+++ /dev/null",
                b"@@ -1,2 +0,0 @@",
                b"-new",
                b"-same",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_bin_blob_force(self):
        f = BytesIO()
        # Prepare two slightly different PNG headers
        b1 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x04\x00\x00\x00\x05\x04\x8b"
        )
        b2 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x03\x00\x00\x00\x98\xd3\xb3"
        )
        store = MemoryObjectStore()
        store.add_objects([(b1, None), (b2, None)])
        write_object_diff(
            f,
            store,
            (b"foo.png", 0o644, b1.id),
            (b"bar.png", 0o644, b2.id),
            diff_binary=True,
        )
        self.assertEqual(
            [
                b"diff --git a/foo.png b/bar.png",
                b"index f73e47d..06364b7 644",
                b"--- a/foo.png",
                b"+++ b/bar.png",
                b"@@ -1,4 +1,4 @@",
                b" \x89PNG",
                b" \x1a",
                b" \x00\x00\x00",
                b"-IHDR\x00\x00\x01\xd5\x00\x00\x00"
                b"\x9f\x08\x04\x00\x00\x00\x05\x04\x8b",
                b"\\ No newline at end of file",
                b"+IHDR\x00\x00\x01\xd5\x00\x00\x00\x9f"
                b"\x08\x03\x00\x00\x00\x98\xd3\xb3",
                b"\\ No newline at end of file",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_bin_blob(self):
        f = BytesIO()
        # Prepare two slightly different PNG headers
        b1 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x04\x00\x00\x00\x05\x04\x8b"
        )
        b2 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x03\x00\x00\x00\x98\xd3\xb3"
        )
        store = MemoryObjectStore()
        store.add_objects([(b1, None), (b2, None)])
        write_object_diff(
            f, store, (b"foo.png", 0o644, b1.id), (b"bar.png", 0o644, b2.id)
        )
        self.assertEqual(
            [
                b"diff --git a/foo.png b/bar.png",
                b"index f73e47d..06364b7 644",
                b"Binary files a/foo.png and b/bar.png differ",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_add_bin_blob(self):
        f = BytesIO()
        b2 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x03\x00\x00\x00\x98\xd3\xb3"
        )
        store = MemoryObjectStore()
        store.add_object(b2)
        write_object_diff(f, store, (None, None, None), (b"bar.png", 0o644, b2.id))
        self.assertEqual(
            [
                b"diff --git a/bar.png b/bar.png",
                b"new file mode 644",
                b"index 0000000..06364b7",
                b"Binary files /dev/null and b/bar.png differ",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_remove_bin_blob(self):
        f = BytesIO()
        b1 = Blob.from_string(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
            b"\x00\x00\x00\x0d\x49\x48\x44\x52"
            b"\x00\x00\x01\xd5\x00\x00\x00\x9f"
            b"\x08\x04\x00\x00\x00\x05\x04\x8b"
        )
        store = MemoryObjectStore()
        store.add_object(b1)
        write_object_diff(f, store, (b"foo.png", 0o644, b1.id), (None, None, None))
        self.assertEqual(
            [
                b"diff --git a/foo.png b/foo.png",
                b"deleted file mode 644",
                b"index f73e47d..0000000",
                b"Binary files a/foo.png and /dev/null differ",
            ],
            f.getvalue().splitlines(),
        )

    def test_object_diff_kind_change(self):
        f = BytesIO()
        b1 = Blob.from_string(b"new\nsame\n")
        store = MemoryObjectStore()
        store.add_object(b1)
        write_object_diff(
            f,
            store,
            (b"bar.txt", 0o644, b1.id),
            (
                b"bar.txt",
                0o160000,
                b"06d0bdd9e2e20377b3180e4986b14c8549b393e4",
            ),
        )
        self.assertEqual(
            [
                b"diff --git a/bar.txt b/bar.txt",
                b"old file mode 644",
                b"new file mode 160000",
                b"index a116b51..06d0bdd 160000",
                b"--- a/bar.txt",
                b"+++ b/bar.txt",
                b"@@ -1,2 +1 @@",
                b"-new",
                b"-same",
                b"+Subproject commit 06d0bdd9e2e20377b3180e4986b14c8549b393e4",
            ],
            f.getvalue().splitlines(),
        )


class GetSummaryTests(TestCase):
    def test_simple(self):
        c = Commit()
        c.committer = c.author = b"Jelmer <jelmer@samba.org>"
        c.commit_time = c.author_time = 1271350201
        c.commit_timezone = c.author_timezone = 0
        c.message = b"This is the first line\nAnd this is the second line.\n"
        c.tree = Tree().id
        self.assertEqual("This-is-the-first-line", get_summary(c))
