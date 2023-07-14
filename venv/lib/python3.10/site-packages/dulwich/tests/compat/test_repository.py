# test_repo.py -- Git repo compatibility tests
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

"""Compatibility tests for dulwich repositories."""


import os
import tempfile
from io import BytesIO
from itertools import chain

from ...objects import hex_to_sha
from ...repo import Repo, check_ref_format
from .utils import (CompatTestCase, require_git_version, rmtree_ro,
                    run_git_or_fail)


class ObjectStoreTestCase(CompatTestCase):
    """Tests for git repository compatibility."""

    def setUp(self):
        super().setUp()
        self._repo = self.import_repo("server_new.export")

    def _run_git(self, args):
        return run_git_or_fail(args, cwd=self._repo.path)

    def _parse_refs(self, output):
        refs = {}
        for line in BytesIO(output):
            fields = line.rstrip(b"\n").split(b" ")
            self.assertEqual(3, len(fields))
            refname, type_name, sha = fields
            check_ref_format(refname[5:])
            hex_to_sha(sha)
            refs[refname] = (type_name, sha)
        return refs

    def _parse_objects(self, output):
        return {s.rstrip(b"\n").split(b" ")[0] for s in BytesIO(output)}

    def test_bare(self):
        self.assertTrue(self._repo.bare)
        self.assertFalse(os.path.exists(os.path.join(self._repo.path, ".git")))

    def test_head(self):
        output = self._run_git(["rev-parse", "HEAD"])
        head_sha = output.rstrip(b"\n")
        hex_to_sha(head_sha)
        self.assertEqual(head_sha, self._repo.refs[b"HEAD"])

    def test_refs(self):
        output = self._run_git(
            ["for-each-ref", "--format=%(refname) %(objecttype) %(objectname)"]
        )
        expected_refs = self._parse_refs(output)

        actual_refs = {}
        for refname, sha in self._repo.refs.as_dict().items():
            if refname == b"HEAD":
                continue  # handled in test_head
            obj = self._repo[sha]
            self.assertEqual(sha, obj.id)
            actual_refs[refname] = (obj.type_name, obj.id)
        self.assertEqual(expected_refs, actual_refs)

    # TODO(dborowitz): peeled ref tests

    def _get_loose_shas(self):
        output = self._run_git(["rev-list", "--all", "--objects", "--unpacked"])
        return self._parse_objects(output)

    def _get_all_shas(self):
        output = self._run_git(["rev-list", "--all", "--objects"])
        return self._parse_objects(output)

    def assertShasMatch(self, expected_shas, actual_shas_iter):
        actual_shas = set()
        for sha in actual_shas_iter:
            obj = self._repo[sha]
            self.assertEqual(sha, obj.id)
            actual_shas.add(sha)
        self.assertEqual(expected_shas, actual_shas)

    def test_loose_objects(self):
        # TODO(dborowitz): This is currently not very useful since
        # fast-imported repos only contained packed objects.
        expected_shas = self._get_loose_shas()
        self.assertShasMatch(
            expected_shas, self._repo.object_store._iter_loose_objects()
        )

    def test_packed_objects(self):
        expected_shas = self._get_all_shas() - self._get_loose_shas()
        self.assertShasMatch(
            expected_shas, chain.from_iterable(self._repo.object_store.packs)
        )

    def test_all_objects(self):
        expected_shas = self._get_all_shas()
        self.assertShasMatch(expected_shas, iter(self._repo.object_store))


class WorkingTreeTestCase(ObjectStoreTestCase):
    """Test for compatibility with git-worktree."""

    min_git_version = (2, 5, 0)

    def create_new_worktree(self, repo_dir, branch):
        """Create a new worktree using git-worktree.

        Args:
          repo_dir: The directory of the main working tree.
          branch: The branch or commit to checkout in the new worktree.

        Returns: The path to the new working tree.
        """
        temp_dir = tempfile.mkdtemp()
        run_git_or_fail(["worktree", "add", temp_dir, branch], cwd=repo_dir)
        self.addCleanup(rmtree_ro, temp_dir)
        return temp_dir

    def setUp(self):
        super().setUp()
        self._worktree_path = self.create_new_worktree(self._repo.path, "branch")
        self._worktree_repo = Repo(self._worktree_path)
        self.addCleanup(self._worktree_repo.close)
        self._mainworktree_repo = self._repo
        self._number_of_working_tree = 2
        self._repo = self._worktree_repo

    def test_refs(self):
        super().test_refs()
        self.assertEqual(
            self._mainworktree_repo.refs.allkeys(), self._repo.refs.allkeys()
        )

    def test_head_equality(self):
        self.assertNotEqual(
            self._repo.refs[b"HEAD"], self._mainworktree_repo.refs[b"HEAD"]
        )

    def test_bare(self):
        self.assertFalse(self._repo.bare)
        self.assertTrue(os.path.isfile(os.path.join(self._repo.path, ".git")))

    def _parse_worktree_list(self, output):
        worktrees = []
        for line in BytesIO(output):
            fields = line.rstrip(b"\n").split()
            worktrees.append(tuple(f.decode() for f in fields))
        return worktrees

    def test_git_worktree_list(self):
        # 'git worktree list' was introduced in 2.7.0
        require_git_version((2, 7, 0))
        output = run_git_or_fail(["worktree", "list"], cwd=self._repo.path)
        worktrees = self._parse_worktree_list(output)
        self.assertEqual(len(worktrees), self._number_of_working_tree)
        self.assertEqual(worktrees[0][1], "(bare)")
        self.assertTrue(os.path.samefile(worktrees[0][0], self._mainworktree_repo.path))

        output = run_git_or_fail(["worktree", "list"], cwd=self._mainworktree_repo.path)
        worktrees = self._parse_worktree_list(output)
        self.assertEqual(len(worktrees), self._number_of_working_tree)
        self.assertEqual(worktrees[0][1], "(bare)")
        self.assertTrue(os.path.samefile(worktrees[0][0], self._mainworktree_repo.path))

    def test_git_worktree_config(self):
        """Test that git worktree config parsing matches the git CLI's behavior."""
        # Set some config value in the main repo using the git CLI
        require_git_version((2, 7, 0))
        test_name = "Jelmer"
        test_email = "jelmer@apache.org"
        run_git_or_fail(["config", "user.name", test_name], cwd=self._repo.path)
        run_git_or_fail(["config", "user.email", test_email], cwd=self._repo.path)

        worktree_cfg = self._worktree_repo.get_config()
        main_cfg = self._repo.get_config()

        # Assert that both the worktree repo and main repo have the same view of the config,
        # and that the config matches what we set with the git cli
        self.assertEqual(worktree_cfg, main_cfg)
        for c in [worktree_cfg, main_cfg]:
            self.assertEqual(test_name.encode(), c.get((b"user",), b"name"))
            self.assertEqual(test_email.encode(), c.get((b"user",), b"email"))

        # Read the config values in the worktree with the git cli and assert they match
        # the dulwich-parsed configs
        output_name = run_git_or_fail(["config", "user.name"], cwd=self._mainworktree_repo.path).decode().rstrip("\n")
        output_email = run_git_or_fail(["config", "user.email"], cwd=self._mainworktree_repo.path).decode().rstrip("\n")
        self.assertEqual(test_name, output_name)
        self.assertEqual(test_email, output_email)


class InitNewWorkingDirectoryTestCase(WorkingTreeTestCase):
    """Test compatibility of Repo.init_new_working_directory."""

    min_git_version = (2, 5, 0)

    def setUp(self):
        super().setUp()
        self._other_worktree = self._repo
        worktree_repo_path = tempfile.mkdtemp()
        self.addCleanup(rmtree_ro, worktree_repo_path)
        self._repo = Repo._init_new_working_directory(
            worktree_repo_path, self._mainworktree_repo
        )
        self.addCleanup(self._repo.close)
        self._number_of_working_tree = 3

    def test_head_equality(self):
        self.assertEqual(
            self._repo.refs[b"HEAD"], self._mainworktree_repo.refs[b"HEAD"]
        )

    def test_bare(self):
        self.assertFalse(self._repo.bare)
        self.assertTrue(os.path.isfile(os.path.join(self._repo.path, ".git")))
