# test_repository.py -- tests for repository.py
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

"""Tests for the repository."""

import glob
import locale
import os
import shutil
import stat
import sys
import tempfile
import warnings

from dulwich import errors, objects, porcelain
from dulwich.tests import TestCase, skipIf

from ..config import Config
from ..errors import NotGitRepository
from ..object_store import tree_lookup_path
from ..repo import (InvalidUserIdentity, MemoryRepo, Repo,
                    UnsupportedExtension, UnsupportedVersion,
                    check_user_identity)
from .utils import open_repo, setup_warning_catcher, tear_down_repo

missing_sha = b"b91fa4d900e17e99b433218e988c4eb4a3e9a097"


class CreateRepositoryTests(TestCase):
    def assertFileContentsEqual(self, expected, repo, path):
        f = repo.get_named_file(path)
        if not f:
            self.assertEqual(expected, None)
        else:
            with f:
                self.assertEqual(expected, f.read())

    def _check_repo_contents(self, repo, expect_bare):
        self.assertEqual(expect_bare, repo.bare)
        self.assertFileContentsEqual(b"Unnamed repository", repo, "description")
        self.assertFileContentsEqual(b"", repo, os.path.join("info", "exclude"))
        self.assertFileContentsEqual(None, repo, "nonexistent file")
        barestr = b"bare = " + str(expect_bare).lower().encode("ascii")
        with repo.get_named_file("config") as f:
            config_text = f.read()
            self.assertIn(barestr, config_text, "%r" % config_text)
        expect_filemode = sys.platform != "win32"
        barestr = b"filemode = " + str(expect_filemode).lower().encode("ascii")
        with repo.get_named_file("config") as f:
            config_text = f.read()
            self.assertIn(barestr, config_text, "%r" % config_text)

        if isinstance(repo, Repo):
            expected_mode = '0o100644' if expect_filemode else '0o100666'
            expected = {
                'HEAD': expected_mode,
                'config': expected_mode,
                'description': expected_mode,
            }
            actual = {
                f[len(repo._controldir) + 1:]: oct(os.stat(f).st_mode)
                for f in glob.glob(os.path.join(repo._controldir, '*'))
                if os.path.isfile(f)
            }

            self.assertEqual(expected, actual)

    def test_create_memory(self):
        repo = MemoryRepo.init_bare([], {})
        self._check_repo_contents(repo, True)

    def test_create_disk_bare(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init_bare(tmp_dir)
        self.assertEqual(tmp_dir, repo._controldir)
        self._check_repo_contents(repo, True)

    def test_create_disk_non_bare(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(tmp_dir)
        self.assertEqual(os.path.join(tmp_dir, ".git"), repo._controldir)
        self._check_repo_contents(repo, False)

    def test_create_disk_non_bare_mkdir(self):
        tmp_dir = tempfile.mkdtemp()
        target_dir = os.path.join(tmp_dir, "target")
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(target_dir, mkdir=True)
        self.assertEqual(os.path.join(target_dir, ".git"), repo._controldir)
        self._check_repo_contents(repo, False)

    def test_create_disk_bare_mkdir(self):
        tmp_dir = tempfile.mkdtemp()
        target_dir = os.path.join(tmp_dir, "target")
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init_bare(target_dir, mkdir=True)
        self.assertEqual(target_dir, repo._controldir)
        self._check_repo_contents(repo, True)


class MemoryRepoTests(TestCase):
    def test_set_description(self):
        r = MemoryRepo.init_bare([], {})
        description = b"Some description"
        r.set_description(description)
        self.assertEqual(description, r.get_description())

    def test_pull_into(self):
        r = MemoryRepo.init_bare([], {})
        repo = open_repo("a.git")
        self.addCleanup(tear_down_repo, repo)
        repo.fetch(r)


class RepositoryRootTests(TestCase):
    def mkdtemp(self):
        return tempfile.mkdtemp()

    def open_repo(self, name):
        temp_dir = self.mkdtemp()
        repo = open_repo(name, temp_dir)
        self.addCleanup(tear_down_repo, repo)
        return repo

    def test_simple_props(self):
        r = self.open_repo("a.git")
        self.assertEqual(r.controldir(), r.path)

    def test_setitem(self):
        r = self.open_repo("a.git")
        r[b"refs/tags/foo"] = b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"
        self.assertEqual(
            b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", r[b"refs/tags/foo"].id
        )

    def test_getitem_unicode(self):
        r = self.open_repo("a.git")

        test_keys = [
            (b"refs/heads/master", True),
            (b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", True),
            (b"11" * 19 + b"--", False),
        ]

        for k, contained in test_keys:
            self.assertEqual(k in r, contained)

        # Avoid deprecation warning under Py3.2+
        if getattr(self, "assertRaisesRegex", None):
            assertRaisesRegexp = self.assertRaisesRegex
        else:
            assertRaisesRegexp = self.assertRaisesRegexp
        for k, _ in test_keys:
            assertRaisesRegexp(
                TypeError,
                "'name' must be bytestring, not int",
                r.__getitem__,
                12,
            )

    def test_delitem(self):
        r = self.open_repo("a.git")

        del r[b"refs/heads/master"]
        self.assertRaises(KeyError, lambda: r[b"refs/heads/master"])

        del r[b"HEAD"]
        self.assertRaises(KeyError, lambda: r[b"HEAD"])

        self.assertRaises(ValueError, r.__delitem__, b"notrefs/foo")

    def test_get_refs(self):
        r = self.open_repo("a.git")
        self.assertEqual(
            {
                b"HEAD": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/heads/master": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/tags/mytag": b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
                b"refs/tags/mytag-packed": b"b0931cadc54336e78a1d980420e3268903b57a50",
            },
            r.get_refs(),
        )

    def test_head(self):
        r = self.open_repo("a.git")
        self.assertEqual(r.head(), b"a90fa2d900a17e99b433217e988c4eb4a2e9a097")

    def test_get_object(self):
        r = self.open_repo("a.git")
        obj = r.get_object(r.head())
        self.assertEqual(obj.type_name, b"commit")

    def test_get_object_non_existant(self):
        r = self.open_repo("a.git")
        self.assertRaises(KeyError, r.get_object, missing_sha)

    def test_contains_object(self):
        r = self.open_repo("a.git")
        self.assertIn(r.head(), r)
        self.assertNotIn(b"z" * 40, r)

    def test_contains_ref(self):
        r = self.open_repo("a.git")
        self.assertIn(b"HEAD", r)

    def test_get_no_description(self):
        r = self.open_repo("a.git")
        self.assertIs(None, r.get_description())

    def test_get_description(self):
        r = self.open_repo("a.git")
        with open(os.path.join(r.path, "description"), "wb") as f:
            f.write(b"Some description")
        self.assertEqual(b"Some description", r.get_description())

    def test_set_description(self):
        r = self.open_repo("a.git")
        description = b"Some description"
        r.set_description(description)
        self.assertEqual(description, r.get_description())

    def test_contains_missing(self):
        r = self.open_repo("a.git")
        self.assertNotIn(b"bar", r)

    def test_get_peeled(self):
        # unpacked ref
        r = self.open_repo("a.git")
        tag_sha = b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a"
        self.assertNotEqual(r[tag_sha].sha().hexdigest(), r.head())
        self.assertEqual(r.get_peeled(b"refs/tags/mytag"), r.head())

        # packed ref with cached peeled value
        packed_tag_sha = b"b0931cadc54336e78a1d980420e3268903b57a50"
        parent_sha = r[r.head()].parents[0]
        self.assertNotEqual(r[packed_tag_sha].sha().hexdigest(), parent_sha)
        self.assertEqual(r.get_peeled(b"refs/tags/mytag-packed"), parent_sha)

        # TODO: add more corner cases to test repo

    def test_get_peeled_not_tag(self):
        r = self.open_repo("a.git")
        self.assertEqual(r.get_peeled(b"HEAD"), r.head())

    def test_get_parents(self):
        r = self.open_repo("a.git")
        self.assertEqual(
            [b"2a72d929692c41d8554c07f6301757ba18a65d91"],
            r.get_parents(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"),
        )
        r.update_shallow([b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"], None)
        self.assertEqual([], r.get_parents(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"))

    def test_get_walker(self):
        r = self.open_repo("a.git")
        # include defaults to [r.head()]
        self.assertEqual(
            [e.commit.id for e in r.get_walker()],
            [r.head(), b"2a72d929692c41d8554c07f6301757ba18a65d91"],
        )
        self.assertEqual(
            [
                e.commit.id
                for e in r.get_walker([b"2a72d929692c41d8554c07f6301757ba18a65d91"])
            ],
            [b"2a72d929692c41d8554c07f6301757ba18a65d91"],
        )
        self.assertEqual(
            [
                e.commit.id
                for e in r.get_walker(b"2a72d929692c41d8554c07f6301757ba18a65d91")
            ],
            [b"2a72d929692c41d8554c07f6301757ba18a65d91"],
        )

    def assertFilesystemHidden(self, path):
        if sys.platform != "win32":
            return
        import ctypes
        from ctypes.wintypes import DWORD, LPCWSTR

        GetFileAttributesW = ctypes.WINFUNCTYPE(DWORD, LPCWSTR)(
            ("GetFileAttributesW", ctypes.windll.kernel32)
        )
        self.assertTrue(2 & GetFileAttributesW(path))

    def test_init_existing(self):
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        t = Repo.init(tmp_dir)
        self.addCleanup(t.close)
        self.assertEqual(os.listdir(tmp_dir), [".git"])
        self.assertFilesystemHidden(os.path.join(tmp_dir, ".git"))

    def test_init_mkdir(self):
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo_dir = os.path.join(tmp_dir, "a-repo")

        t = Repo.init(repo_dir, mkdir=True)
        self.addCleanup(t.close)
        self.assertEqual(os.listdir(repo_dir), [".git"])
        self.assertFilesystemHidden(os.path.join(repo_dir, ".git"))

    def test_init_mkdir_unicode(self):
        repo_name = "\xa7"
        try:
            os.fsencode(repo_name)
        except UnicodeEncodeError:
            self.skipTest("filesystem lacks unicode support")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo_dir = os.path.join(tmp_dir, repo_name)

        t = Repo.init(repo_dir, mkdir=True)
        self.addCleanup(t.close)
        self.assertEqual(os.listdir(repo_dir), [".git"])
        self.assertFilesystemHidden(os.path.join(repo_dir, ".git"))

    @skipIf(sys.platform == "win32", "fails on Windows")
    def test_fetch(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        t = Repo.init(tmp_dir)
        self.addCleanup(t.close)
        r.fetch(t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a", t)
        self.assertIn(b"b0931cadc54336e78a1d980420e3268903b57a50", t)

    @skipIf(sys.platform == "win32", "fails on Windows")
    def test_fetch_ignores_missing_refs(self):
        r = self.open_repo("a.git")
        missing = b"1234566789123456789123567891234657373833"
        r.refs[b"refs/heads/blah"] = missing
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        t = Repo.init(tmp_dir)
        self.addCleanup(t.close)
        r.fetch(t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097", t)
        self.assertIn(b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a", t)
        self.assertIn(b"b0931cadc54336e78a1d980420e3268903b57a50", t)
        self.assertNotIn(missing, t)

    def test_clone(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with r.clone(tmp_dir, mkdir=False) as t:
            self.assertEqual(
                {
                    b"HEAD": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                    b"refs/remotes/origin/master": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                    b"refs/remotes/origin/HEAD": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                    b"refs/heads/master": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                    b"refs/tags/mytag": b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
                    b"refs/tags/mytag-packed": b"b0931cadc54336e78a1d980420e3268903b57a50",
                },
                t.refs.as_dict(),
            )
            shas = [e.commit.id for e in r.get_walker()]
            self.assertEqual(
                shas, [t.head(), b"2a72d929692c41d8554c07f6301757ba18a65d91"]
            )
            c = t.get_config()
            encoded_path = r.path
            if not isinstance(encoded_path, bytes):
                encoded_path = os.fsencode(encoded_path)
            self.assertEqual(encoded_path, c.get((b"remote", b"origin"), b"url"))
            self.assertEqual(
                b"+refs/heads/*:refs/remotes/origin/*",
                c.get((b"remote", b"origin"), b"fetch"),
            )

    def test_clone_no_head(self):
        temp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)
        repo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "repos")
        dest_dir = os.path.join(temp_dir, "a.git")
        shutil.copytree(os.path.join(repo_dir, "a.git"), dest_dir, symlinks=True)
        r = Repo(dest_dir)
        self.addCleanup(r.close)
        del r.refs[b"refs/heads/master"]
        del r.refs[b"HEAD"]
        t = r.clone(os.path.join(temp_dir, "b.git"), mkdir=True)
        self.addCleanup(t.close)
        self.assertEqual(
            {
                b"refs/tags/mytag": b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
                b"refs/tags/mytag-packed": b"b0931cadc54336e78a1d980420e3268903b57a50",
            },
            t.refs.as_dict(),
        )

    def test_clone_empty(self):
        """Test clone() doesn't crash if HEAD points to a non-existing ref.

        This simulates cloning server-side bare repository either when it is
        still empty or if user renames master branch and pushes private repo
        to the server.
        Non-bare repo HEAD always points to an existing ref.
        """
        r = self.open_repo("empty.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        r.clone(tmp_dir, mkdir=False, bare=True)

    def test_reset_index_symlink_enabled(self):
        if sys.platform == 'win32':
            self.skipTest("symlinks are not supported on Windows")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)

        o = Repo.init(os.path.join(tmp_dir, "s"), mkdir=True)
        os.symlink("foo", os.path.join(tmp_dir, "s", "bar"))
        o.stage("bar")
        o.do_commit(b"add symlink")

        t = o.clone(os.path.join(tmp_dir, "t"), symlinks=True)
        o.close()
        bar_path = os.path.join(tmp_dir, 't', 'bar')
        if sys.platform == 'win32':
            with open(bar_path, 'r') as f:
                self.assertEqual('foo', f.read())
        else:
            self.assertEqual('foo', os.readlink(bar_path))
        t.close()

    def test_reset_index_symlink_disabled(self):
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)

        o = Repo.init(os.path.join(tmp_dir, "s"), mkdir=True)
        o.close()
        os.symlink("foo", os.path.join(tmp_dir, "s", "bar"))
        o.stage("bar")
        o.do_commit(b"add symlink")

        t = o.clone(os.path.join(tmp_dir, "t"), symlinks=False)
        with open(os.path.join(tmp_dir, "t", 'bar'), 'r') as f:
            self.assertEqual('foo', f.read())

        t.close()

    def test_clone_bare(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        t = r.clone(tmp_dir, mkdir=False)
        t.close()

    def test_clone_checkout_and_bare(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        self.assertRaises(
            ValueError, r.clone, tmp_dir, mkdir=False, checkout=True, bare=True
        )

    def test_clone_branch(self):
        r = self.open_repo("a.git")
        r.refs[b"refs/heads/mybranch"] = b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a"
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with r.clone(tmp_dir, mkdir=False, branch=b"mybranch") as t:
            # HEAD should point to specified branch and not origin HEAD
            chain, sha = t.refs.follow(b"HEAD")
            self.assertEqual(chain[-1], b"refs/heads/mybranch")
            self.assertEqual(sha, b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a")
            self.assertEqual(
                t.refs[b"refs/remotes/origin/HEAD"],
                b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
            )

    def test_clone_tag(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with r.clone(tmp_dir, mkdir=False, branch=b"mytag") as t:
            # HEAD should be detached (and not a symbolic ref) at tag
            self.assertEqual(
                t.refs.read_ref(b"HEAD"),
                b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
            )
            self.assertEqual(
                t.refs[b"refs/remotes/origin/HEAD"],
                b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
            )

    def test_clone_invalid_branch(self):
        r = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        self.assertRaises(
            ValueError,
            r.clone,
            tmp_dir,
            mkdir=False,
            branch=b"mybranch",
        )

    def test_merge_history(self):
        r = self.open_repo("simple_merge.git")
        shas = [e.commit.id for e in r.get_walker()]
        self.assertEqual(
            shas,
            [
                b"5dac377bdded4c9aeb8dff595f0faeebcc8498cc",
                b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",
                b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",
                b"60dacdc733de308bb77bb76ce0fb0f9b44c9769e",
                b"0d89f20333fbb1d2f3a94da77f4981373d8f4310",
            ],
        )

    def test_out_of_order_merge(self):
        """Test that revision history is ordered by date, not parent order."""
        r = self.open_repo("ooo_merge.git")
        shas = [e.commit.id for e in r.get_walker()]
        self.assertEqual(
            shas,
            [
                b"7601d7f6231db6a57f7bbb79ee52e4d462fd44d1",
                b"f507291b64138b875c28e03469025b1ea20bc614",
                b"fb5b0425c7ce46959bec94d54b9a157645e114f5",
                b"f9e39b120c68182a4ba35349f832d0e4e61f485c",
            ],
        )

    def test_get_tags_empty(self):
        r = self.open_repo("ooo_merge.git")
        self.assertEqual({}, r.refs.as_dict(b"refs/tags"))

    def test_get_config(self):
        r = self.open_repo("ooo_merge.git")
        self.assertIsInstance(r.get_config(), Config)

    def test_get_config_stack(self):
        r = self.open_repo("ooo_merge.git")
        self.assertIsInstance(r.get_config_stack(), Config)

    def test_common_revisions(self):
        """
        This test demonstrates that ``find_common_revisions()`` actually
        returns common heads, not revisions; dulwich already uses
        ``find_common_revisions()`` in such a manner (see
        ``Repo.find_objects()``).
        """

        expected_shas = {b"60dacdc733de308bb77bb76ce0fb0f9b44c9769e"}

        # Source for objects.
        r_base = self.open_repo("simple_merge.git")

        # Re-create each-side of the merge in simple_merge.git.
        #
        # Since the trees and blobs are missing, the repository created is
        # corrupted, but we're only checking for commits for the purpose of
        # this test, so it's immaterial.
        r1_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, r1_dir)
        r1_commits = [
            b"ab64bbdcc51b170d21588e5c5d391ee5c0c96dfd",  # HEAD
            b"60dacdc733de308bb77bb76ce0fb0f9b44c9769e",
            b"0d89f20333fbb1d2f3a94da77f4981373d8f4310",
        ]

        r2_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, r2_dir)
        r2_commits = [
            b"4cffe90e0a41ad3f5190079d7c8f036bde29cbe6",  # HEAD
            b"60dacdc733de308bb77bb76ce0fb0f9b44c9769e",
            b"0d89f20333fbb1d2f3a94da77f4981373d8f4310",
        ]

        r1 = Repo.init_bare(r1_dir)
        for c in r1_commits:
            r1.object_store.add_object(r_base.get_object(c))
        r1.refs[b"HEAD"] = r1_commits[0]

        r2 = Repo.init_bare(r2_dir)
        for c in r2_commits:
            r2.object_store.add_object(r_base.get_object(c))
        r2.refs[b"HEAD"] = r2_commits[0]

        # Finally, the 'real' testing!
        shas = r2.object_store.find_common_revisions(r1.get_graph_walker())
        self.assertEqual(set(shas), expected_shas)

        shas = r1.object_store.find_common_revisions(r2.get_graph_walker())
        self.assertEqual(set(shas), expected_shas)

    def test_shell_hook_pre_commit(self):
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")

        pre_commit_fail = """#!/bin/sh
exit 1
"""

        pre_commit_success = """#!/bin/sh
exit 0
"""

        repo_dir = os.path.join(self.mkdtemp())
        self.addCleanup(shutil.rmtree, repo_dir)
        r = Repo.init(repo_dir)
        self.addCleanup(r.close)

        pre_commit = os.path.join(r.controldir(), "hooks", "pre-commit")

        with open(pre_commit, "w") as f:
            f.write(pre_commit_fail)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        self.assertRaises(
            errors.CommitError,
            r.do_commit,
            b"failed commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )

        with open(pre_commit, "w") as f:
            f.write(pre_commit_success)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        commit_sha = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([], r[commit_sha].parents)

    def test_shell_hook_commit_msg(self):
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")

        commit_msg_fail = """#!/bin/sh
exit 1
"""

        commit_msg_success = """#!/bin/sh
exit 0
"""

        repo_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, repo_dir)
        r = Repo.init(repo_dir)
        self.addCleanup(r.close)

        commit_msg = os.path.join(r.controldir(), "hooks", "commit-msg")

        with open(commit_msg, "w") as f:
            f.write(commit_msg_fail)
        os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        self.assertRaises(
            errors.CommitError,
            r.do_commit,
            b"failed commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )

        with open(commit_msg, "w") as f:
            f.write(commit_msg_success)
        os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        commit_sha = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([], r[commit_sha].parents)

    def test_shell_hook_pre_commit_add_files(self):
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")

        pre_commit_contents = """#!{executable}
import sys
sys.path.extend({path!r})
from dulwich.repo import Repo

with open('foo', 'w') as f:
    f.write('newfile')

r = Repo('.')
r.stage(['foo'])
""".format(
            executable=sys.executable,
            path=[os.path.join(os.path.dirname(__file__), '..', '..')] + sys.path)

        repo_dir = os.path.join(self.mkdtemp())
        self.addCleanup(shutil.rmtree, repo_dir)
        r = Repo.init(repo_dir)
        self.addCleanup(r.close)

        with open(os.path.join(repo_dir, 'blah'), 'w') as f:
            f.write('blah')

        r.stage(['blah'])

        pre_commit = os.path.join(r.controldir(), "hooks", "pre-commit")

        with open(pre_commit, "w") as f:
            f.write(pre_commit_contents)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        commit_sha = r.do_commit(
            b"new commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([], r[commit_sha].parents)

        tree = r[r[commit_sha].tree]
        self.assertEqual({b'blah', b'foo'}, set(tree))

    def test_shell_hook_post_commit(self):
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")

        repo_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, repo_dir)

        r = Repo.init(repo_dir)
        self.addCleanup(r.close)

        (fd, path) = tempfile.mkstemp(dir=repo_dir)
        os.close(fd)
        post_commit_msg = (
            """#!/bin/sh
rm """
            + path
            + """
"""
        )

        root_sha = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        self.assertEqual([], r[root_sha].parents)

        post_commit = os.path.join(r.controldir(), "hooks", "post-commit")

        with open(post_commit, "wb") as f:
            f.write(post_commit_msg.encode(locale.getpreferredencoding()))
        os.chmod(post_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        commit_sha = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        self.assertEqual([root_sha], r[commit_sha].parents)

        self.assertFalse(os.path.exists(path))

        post_commit_msg_fail = """#!/bin/sh
exit 1
"""
        with open(post_commit, "w") as f:
            f.write(post_commit_msg_fail)
        os.chmod(post_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        warnings.simplefilter("always", UserWarning)
        self.addCleanup(warnings.resetwarnings)
        warnings_list, restore_warnings = setup_warning_catcher()
        self.addCleanup(restore_warnings)

        commit_sha2 = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        expected_warning = UserWarning(
            "post-commit hook failed: Hook post-commit exited with "
            "non-zero status 1",
        )
        for w in warnings_list:
            if type(w) == type(expected_warning) and w.args == expected_warning.args:
                break
        else:
            raise AssertionError(
                "Expected warning {!r} not in {!r}".format(expected_warning, warnings_list)
            )
        self.assertEqual([commit_sha], r[commit_sha2].parents)

    def test_as_dict(self):
        def check(repo):
            self.assertEqual(
                repo.refs.subkeys(b"refs/tags"),
                repo.refs.subkeys(b"refs/tags/"),
            )
            self.assertEqual(
                repo.refs.as_dict(b"refs/tags"),
                repo.refs.as_dict(b"refs/tags/"),
            )
            self.assertEqual(
                repo.refs.as_dict(b"refs/heads"),
                repo.refs.as_dict(b"refs/heads/"),
            )

        bare = self.open_repo("a.git")
        tmp_dir = self.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with bare.clone(tmp_dir, mkdir=False) as nonbare:
            check(nonbare)
            check(bare)

    def test_working_tree(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)
        worktree_temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, worktree_temp_dir)
        r = Repo.init(temp_dir)
        self.addCleanup(r.close)
        root_sha = r.do_commit(
            b"empty commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        r.refs[b"refs/heads/master"] = root_sha
        w = Repo._init_new_working_directory(worktree_temp_dir, r)
        self.addCleanup(w.close)
        new_sha = w.do_commit(
            b"new commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        w.refs[b"HEAD"] = new_sha
        self.assertEqual(
            os.path.abspath(r.controldir()), os.path.abspath(w.commondir())
        )
        self.assertEqual(r.refs.keys(), w.refs.keys())
        self.assertNotEqual(r.head(), w.head())


class BuildRepoRootTests(TestCase):
    """Tests that build on-disk repos from scratch.

    Repos live in a temp dir and are torn down after each test. They start with
    a single commit in master having single file named 'a'.
    """

    def get_repo_dir(self):
        return os.path.join(tempfile.mkdtemp(), "test")

    def setUp(self):
        super().setUp()
        self._repo_dir = self.get_repo_dir()
        os.makedirs(self._repo_dir)
        r = self._repo = Repo.init(self._repo_dir)
        self.addCleanup(tear_down_repo, r)
        self.assertFalse(r.bare)
        self.assertEqual(b"ref: refs/heads/master", r.refs.read_ref(b"HEAD"))
        self.assertRaises(KeyError, lambda: r.refs[b"refs/heads/master"])

        with open(os.path.join(r.path, "a"), "wb") as f:
            f.write(b"file contents")
        r.stage(["a"])
        commit_sha = r.do_commit(
            b"msg",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        self.assertEqual([], r[commit_sha].parents)
        self._root_commit = commit_sha

    def test_get_shallow(self):
        self.assertEqual(set(), self._repo.get_shallow())
        with open(os.path.join(self._repo.path, ".git", "shallow"), "wb") as f:
            f.write(b"a90fa2d900a17e99b433217e988c4eb4a2e9a097\n")
        self.assertEqual(
            {b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"},
            self._repo.get_shallow(),
        )

    def test_update_shallow(self):
        self._repo.update_shallow(None, None)  # no op
        self.assertEqual(set(), self._repo.get_shallow())
        self._repo.update_shallow([b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"], None)
        self.assertEqual(
            {b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"},
            self._repo.get_shallow(),
        )
        self._repo.update_shallow(
            [b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"],
            [b"f9e39b120c68182a4ba35349f832d0e4e61f485c"],
        )
        self.assertEqual(
            {b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"},
            self._repo.get_shallow(),
        )
        self._repo.update_shallow(
            None, [b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"]
        )
        self.assertEqual(set(), self._repo.get_shallow())
        self.assertEqual(
            False,
            os.path.exists(os.path.join(self._repo.controldir(), "shallow")),
        )

    def test_build_repo(self):
        r = self._repo
        self.assertEqual(b"ref: refs/heads/master", r.refs.read_ref(b"HEAD"))
        self.assertEqual(self._root_commit, r.refs[b"refs/heads/master"])
        expected_blob = objects.Blob.from_string(b"file contents")
        self.assertEqual(expected_blob.data, r[expected_blob.id].data)
        actual_commit = r[self._root_commit]
        self.assertEqual(b"msg", actual_commit.message)

    def test_commit_modified(self):
        r = self._repo
        with open(os.path.join(r.path, "a"), "wb") as f:
            f.write(b"new contents")
        r.stage(["a"])
        commit_sha = r.do_commit(
            b"modified a",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([self._root_commit], r[commit_sha].parents)
        a_mode, a_id = tree_lookup_path(r.get_object, r[commit_sha].tree, b"a")
        self.assertEqual(stat.S_IFREG | 0o644, a_mode)
        self.assertEqual(b"new contents", r[a_id].data)

    @skipIf(not getattr(os, "symlink", None), "Requires symlink support")
    def test_commit_symlink(self):
        r = self._repo
        os.symlink("a", os.path.join(r.path, "b"))
        r.stage(["a", "b"])
        commit_sha = r.do_commit(
            b"Symlink b",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([self._root_commit], r[commit_sha].parents)
        b_mode, b_id = tree_lookup_path(r.get_object, r[commit_sha].tree, b"b")
        self.assertTrue(stat.S_ISLNK(b_mode))
        self.assertEqual(b"a", r[b_id].data)

    def test_commit_merge_heads_file(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        r = Repo.init(tmp_dir)
        with open(os.path.join(r.path, "a"), "w") as f:
            f.write("initial text")
        c1 = r.do_commit(
            b"initial commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        with open(os.path.join(r.path, "a"), "w") as f:
            f.write("merged text")
        with open(os.path.join(r.path, ".git", "MERGE_HEAD"), "w") as f:
            f.write("c27a2d21dd136312d7fa9e8baabb82561a1727d0\n")
        r.stage(["a"])
        commit_sha = r.do_commit(
            b"deleted a",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual(
            [c1, b"c27a2d21dd136312d7fa9e8baabb82561a1727d0"],
            r[commit_sha].parents,
        )

    def test_commit_deleted(self):
        r = self._repo
        os.remove(os.path.join(r.path, "a"))
        r.stage(["a"])
        commit_sha = r.do_commit(
            b"deleted a",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual([self._root_commit], r[commit_sha].parents)
        self.assertEqual([], list(r.open_index()))
        tree = r[r[commit_sha].tree]
        self.assertEqual([], list(tree.iteritems()))

    def test_commit_follows(self):
        r = self._repo
        r.refs.set_symbolic_ref(b"HEAD", b"refs/heads/bla")
        commit_sha = r.do_commit(
            b"commit with strange character",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=b"HEAD",
        )
        self.assertEqual(commit_sha, r[b"refs/heads/bla"].id)

    def test_commit_encoding(self):
        r = self._repo
        commit_sha = r.do_commit(
            b"commit with strange character \xee",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            encoding=b"iso8859-1",
        )
        self.assertEqual(b"iso8859-1", r[commit_sha].encoding)

    def test_compression_level(self):
        r = self._repo
        c = r.get_config()
        c.set(("core",), "compression", "3")
        c.set(("core",), "looseCompression", "4")
        c.write_to_path()
        r = Repo(self._repo_dir)
        self.assertEqual(r.object_store.loose_compression_level, 4)

    def test_repositoryformatversion_unsupported(self):
        r = self._repo
        c = r.get_config()
        c.set(("core",), "repositoryformatversion", "2")
        c.write_to_path()
        self.assertRaises(UnsupportedVersion, Repo, self._repo_dir)

    def test_repositoryformatversion_1(self):
        r = self._repo
        c = r.get_config()
        c.set(("core",), "repositoryformatversion", "1")
        c.write_to_path()
        Repo(self._repo_dir)

    def test_worktreeconfig_extension(self):
        r = self._repo
        c = r.get_config()
        c.set(("core",), "repositoryformatversion", "1")
        c.set(("extensions", ), "worktreeconfig", True)
        c.write_to_path()
        c = r.get_worktree_config()
        c.set(("user",), "repositoryformatversion", "1")
        c.set((b"user",), b"name", b"Jelmer")
        c.write_to_path()
        cs = r.get_config_stack()
        self.assertEqual(cs.get(("user", ), "name"), b"Jelmer")

    def test_repositoryformatversion_1_extension(self):
        r = self._repo
        c = r.get_config()
        c.set(("core",), "repositoryformatversion", "1")
        c.set(("extensions", ), "unknownextension", True)
        c.write_to_path()
        self.assertRaises(UnsupportedExtension, Repo, self._repo_dir)

    def test_commit_encoding_from_config(self):
        r = self._repo
        c = r.get_config()
        c.set(("i18n",), "commitEncoding", "iso8859-1")
        c.write_to_path()
        commit_sha = r.do_commit(
            b"commit with strange character \xee",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
        )
        self.assertEqual(b"iso8859-1", r[commit_sha].encoding)

    def test_commit_config_identity(self):
        # commit falls back to the users' identity if it wasn't specified
        r = self._repo
        c = r.get_config()
        c.set((b"user",), b"name", b"Jelmer")
        c.set((b"user",), b"email", b"jelmer@apache.org")
        c.write_to_path()
        commit_sha = r.do_commit(b"message")
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].author)
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].committer)

    def test_commit_config_identity_strips_than(self):
        # commit falls back to the users' identity if it wasn't specified,
        # and strips superfluous <>
        r = self._repo
        c = r.get_config()
        c.set((b"user",), b"name", b"Jelmer")
        c.set((b"user",), b"email", b"<jelmer@apache.org>")
        c.write_to_path()
        commit_sha = r.do_commit(b"message")
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].author)
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].committer)

    def test_commit_config_identity_in_memoryrepo(self):
        # commit falls back to the users' identity if it wasn't specified
        r = MemoryRepo.init_bare([], {})
        c = r.get_config()
        c.set((b"user",), b"name", b"Jelmer")
        c.set((b"user",), b"email", b"jelmer@apache.org")

        commit_sha = r.do_commit(b"message", tree=objects.Tree().id)
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].author)
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].committer)

    def test_commit_config_identity_from_env(self):
        # commit falls back to the users' identity if it wasn't specified
        self.overrideEnv("GIT_COMMITTER_NAME", "joe")
        self.overrideEnv("GIT_COMMITTER_EMAIL", "joe@example.com")
        r = self._repo
        c = r.get_config()
        c.set((b"user",), b"name", b"Jelmer")
        c.set((b"user",), b"email", b"jelmer@apache.org")
        c.write_to_path()
        commit_sha = r.do_commit(b"message")
        self.assertEqual(b"Jelmer <jelmer@apache.org>", r[commit_sha].author)
        self.assertEqual(b"joe <joe@example.com>", r[commit_sha].committer)

    def test_commit_fail_ref(self):
        r = self._repo

        def set_if_equals(name, old_ref, new_ref, **kwargs):
            return False

        r.refs.set_if_equals = set_if_equals

        def add_if_new(name, new_ref, **kwargs):
            self.fail("Unexpected call to add_if_new")

        r.refs.add_if_new = add_if_new

        old_shas = set(r.object_store)
        self.assertRaises(
            errors.CommitError,
            r.do_commit,
            b"failed commit",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12345,
            commit_timezone=0,
            author_timestamp=12345,
            author_timezone=0,
        )
        new_shas = set(r.object_store) - old_shas
        self.assertEqual(1, len(new_shas))
        # Check that the new commit (now garbage) was added.
        new_commit = r[new_shas.pop()]
        self.assertEqual(r[self._root_commit].tree, new_commit.tree)
        self.assertEqual(b"failed commit", new_commit.message)

    def test_commit_branch(self):
        r = self._repo

        commit_sha = r.do_commit(
            b"commit to branch",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=b"refs/heads/new_branch",
        )
        self.assertEqual(self._root_commit, r[b"HEAD"].id)
        self.assertEqual(commit_sha, r[b"refs/heads/new_branch"].id)
        self.assertEqual([], r[commit_sha].parents)
        self.assertIn(b"refs/heads/new_branch", r)

        new_branch_head = commit_sha

        commit_sha = r.do_commit(
            b"commit to branch 2",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=b"refs/heads/new_branch",
        )
        self.assertEqual(self._root_commit, r[b"HEAD"].id)
        self.assertEqual(commit_sha, r[b"refs/heads/new_branch"].id)
        self.assertEqual([new_branch_head], r[commit_sha].parents)

    def test_commit_merge_heads(self):
        r = self._repo
        merge_1 = r.do_commit(
            b"commit to branch 2",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=b"refs/heads/new_branch",
        )
        commit_sha = r.do_commit(
            b"commit with merge",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            merge_heads=[merge_1],
        )
        self.assertEqual([self._root_commit, merge_1], r[commit_sha].parents)

    def test_commit_dangling_commit(self):
        r = self._repo

        old_shas = set(r.object_store)
        old_refs = r.get_refs()
        commit_sha = r.do_commit(
            b"commit with no ref",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=None,
        )
        new_shas = set(r.object_store) - old_shas

        # New sha is added, but no new refs
        self.assertEqual(1, len(new_shas))
        new_commit = r[new_shas.pop()]
        self.assertEqual(r[self._root_commit].tree, new_commit.tree)
        self.assertEqual([], r[commit_sha].parents)
        self.assertEqual(old_refs, r.get_refs())

    def test_commit_dangling_commit_with_parents(self):
        r = self._repo

        old_shas = set(r.object_store)
        old_refs = r.get_refs()
        commit_sha = r.do_commit(
            b"commit with no ref",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=None,
            merge_heads=[self._root_commit],
        )
        new_shas = set(r.object_store) - old_shas

        # New sha is added, but no new refs
        self.assertEqual(1, len(new_shas))
        new_commit = r[new_shas.pop()]
        self.assertEqual(r[self._root_commit].tree, new_commit.tree)
        self.assertEqual([self._root_commit], r[commit_sha].parents)
        self.assertEqual(old_refs, r.get_refs())

    def test_stage_absolute(self):
        r = self._repo
        os.remove(os.path.join(r.path, "a"))
        self.assertRaises(ValueError, r.stage, [os.path.join(r.path, "a")])

    def test_stage_deleted(self):
        r = self._repo
        os.remove(os.path.join(r.path, "a"))
        r.stage(["a"])
        r.stage(["a"])  # double-stage a deleted path
        self.assertEqual([], list(r.open_index()))

    def test_stage_directory(self):
        r = self._repo
        os.mkdir(os.path.join(r.path, "c"))
        r.stage(["c"])
        self.assertEqual([b"a"], list(r.open_index()))

    def test_stage_submodule(self):
        r = self._repo
        s = Repo.init(os.path.join(r.path, "sub"), mkdir=True)
        s.do_commit(b'message')
        r.stage(["sub"])
        self.assertEqual([b"a", b"sub"], list(r.open_index()))

    def test_unstage_midify_file_with_dir(self):
        os.mkdir(os.path.join(self._repo.path, 'new_dir'))
        full_path = os.path.join(self._repo.path, 'new_dir', 'foo')

        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self._repo, paths=[full_path])
        porcelain.commit(
            self._repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        with open(full_path, 'a') as f:
            f.write('something new')
        self._repo.unstage(['new_dir/foo'])
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [b'new_dir/foo'], []], status)

    def test_unstage_while_no_commit(self):
        file = 'foo'
        full_path = os.path.join(self._repo.path, file)
        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self._repo, paths=[full_path])
        self._repo.unstage([file])
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], ['foo']], status)

    def test_unstage_add_file(self):
        file = 'foo'
        full_path = os.path.join(self._repo.path, file)
        porcelain.commit(
            self._repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self._repo, paths=[full_path])
        self._repo.unstage([file])
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], ['foo']], status)

    def test_unstage_modify_file(self):
        file = 'foo'
        full_path = os.path.join(self._repo.path, file)
        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self._repo, paths=[full_path])
        porcelain.commit(
            self._repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        with open(full_path, 'a') as f:
            f.write('broken')
        porcelain.add(self._repo, paths=[full_path])
        self._repo.unstage([file])
        status = list(porcelain.status(self._repo))

        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [b'foo'], []], status)

    def test_unstage_remove_file(self):
        file = 'foo'
        full_path = os.path.join(self._repo.path, file)
        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self._repo, paths=[full_path])
        porcelain.commit(
            self._repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        os.remove(full_path)
        self._repo.unstage([file])
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [b'foo'], []], status)

    def test_reset_index(self):
        r = self._repo
        with open(os.path.join(r.path, 'a'), 'wb') as f:
            f.write(b'changed')
        with open(os.path.join(r.path, 'b'), 'wb') as f:
            f.write(b'added')
        r.stage(['a', 'b'])
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [b'b'], 'delete': [], 'modify': [b'a']}, [], []], status)
        r.reset_index()
        status = list(porcelain.status(self._repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], ['b']], status)

    @skipIf(
        sys.platform in ("win32", "darwin"),
        "tries to implicitly decode as utf8",
    )
    def test_commit_no_encode_decode(self):
        r = self._repo
        repo_path_bytes = os.fsencode(r.path)
        encodings = ("utf8", "latin1")
        names = ["À".encode(encoding) for encoding in encodings]
        for name, encoding in zip(names, encodings):
            full_path = os.path.join(repo_path_bytes, name)
            with open(full_path, "wb") as f:
                f.write(encoding.encode("ascii"))
            # These files are break tear_down_repo, so cleanup these files
            # ourselves.
            self.addCleanup(os.remove, full_path)

        r.stage(names)
        commit_sha = r.do_commit(
            b"Files with different encodings",
            committer=b"Test Committer <test@nodomain.com>",
            author=b"Test Author <test@nodomain.com>",
            commit_timestamp=12395,
            commit_timezone=0,
            author_timestamp=12395,
            author_timezone=0,
            ref=None,
            merge_heads=[self._root_commit],
        )

        for name, encoding in zip(names, encodings):
            mode, id = tree_lookup_path(r.get_object, r[commit_sha].tree, name)
            self.assertEqual(stat.S_IFREG | 0o644, mode)
            self.assertEqual(encoding.encode("ascii"), r[id].data)

    def test_discover_intended(self):
        path = os.path.join(self._repo_dir, "b/c")
        r = Repo.discover(path)
        self.assertEqual(r.head(), self._repo.head())

    def test_discover_isrepo(self):
        r = Repo.discover(self._repo_dir)
        self.assertEqual(r.head(), self._repo.head())

    def test_discover_notrepo(self):
        with self.assertRaises(NotGitRepository):
            Repo.discover("/")


class CheckUserIdentityTests(TestCase):
    def test_valid(self):
        check_user_identity(b"Me <me@example.com>")

    def test_invalid(self):
        self.assertRaises(InvalidUserIdentity, check_user_identity, b"No Email")
        self.assertRaises(
            InvalidUserIdentity, check_user_identity, b"Fullname <missing"
        )
        self.assertRaises(
            InvalidUserIdentity, check_user_identity, b"Fullname missing>"
        )
        self.assertRaises(
            InvalidUserIdentity, check_user_identity, b"Fullname >order<>"
        )
        self.assertRaises(
            InvalidUserIdentity, check_user_identity, b'Contains\0null byte <>'
        )
        self.assertRaises(
            InvalidUserIdentity, check_user_identity, b'Contains\nnewline byte <>'
        )
