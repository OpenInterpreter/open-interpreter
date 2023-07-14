# test_hooks.py -- Tests for executing hooks
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

"""Tests for executing hooks."""

import os
import shutil
import stat
import sys
import tempfile

from dulwich import errors
from dulwich.tests import TestCase

from ..hooks import CommitMsgShellHook, PostCommitShellHook, PreCommitShellHook


class ShellHookTests(TestCase):
    def setUp(self):
        super().setUp()
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")
        self.assertTrue(os.path.exists("/bin/sh"))

    def test_hook_pre_commit(self):
        repo_dir = os.path.join(tempfile.mkdtemp())
        os.mkdir(os.path.join(repo_dir, "hooks"))
        self.addCleanup(shutil.rmtree, repo_dir)

        pre_commit_fail = """#!/bin/sh
exit 1
"""

        pre_commit_success = """#!/bin/sh
exit 0
"""
        pre_commit_cwd = (
            """#!/bin/sh
if [ "$(pwd)" != '"""
            + repo_dir
            + """' ]; then
    echo "Expected path '"""
            + repo_dir
            + """', got '$(pwd)'"
    exit 1
fi

exit 0
"""
        )

        pre_commit = os.path.join(repo_dir, "hooks", "pre-commit")
        hook = PreCommitShellHook(repo_dir, repo_dir)

        with open(pre_commit, "w") as f:
            f.write(pre_commit_fail)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        self.assertRaises(errors.HookError, hook.execute)

        if sys.platform != "darwin":
            # Don't bother running this test on darwin since path
            # canonicalization messages with our simple string comparison.
            with open(pre_commit, "w") as f:
                f.write(pre_commit_cwd)
            os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

            hook.execute()

        with open(pre_commit, "w") as f:
            f.write(pre_commit_success)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        hook.execute()

    def test_hook_commit_msg(self):

        repo_dir = os.path.join(tempfile.mkdtemp())
        os.mkdir(os.path.join(repo_dir, "hooks"))
        self.addCleanup(shutil.rmtree, repo_dir)

        commit_msg_fail = """#!/bin/sh
exit 1
"""

        commit_msg_success = """#!/bin/sh
exit 0
"""

        commit_msg_cwd = (
            """#!/bin/sh
if [ "$(pwd)" = '"""
            + repo_dir
            + "' ]; then exit 0; else exit 1; fi\n"
        )

        commit_msg = os.path.join(repo_dir, "hooks", "commit-msg")
        hook = CommitMsgShellHook(repo_dir)

        with open(commit_msg, "w") as f:
            f.write(commit_msg_fail)
        os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        self.assertRaises(errors.HookError, hook.execute, b"failed commit")

        if sys.platform != "darwin":
            # Don't bother running this test on darwin since path
            # canonicalization messages with our simple string comparison.
            with open(commit_msg, "w") as f:
                f.write(commit_msg_cwd)
            os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

            hook.execute(b"cwd test commit")

        with open(commit_msg, "w") as f:
            f.write(commit_msg_success)
        os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        hook.execute(b"empty commit")

    def test_hook_post_commit(self):

        (fd, path) = tempfile.mkstemp()
        os.close(fd)

        repo_dir = os.path.join(tempfile.mkdtemp())
        os.mkdir(os.path.join(repo_dir, "hooks"))
        self.addCleanup(shutil.rmtree, repo_dir)

        post_commit_success = (
            """#!/bin/sh
rm """
            + path
            + "\n"
        )

        post_commit_fail = """#!/bin/sh
exit 1
"""

        post_commit_cwd = (
            """#!/bin/sh
if [ "$(pwd)" = '"""
            + repo_dir
            + "' ]; then exit 0; else exit 1; fi\n"
        )

        post_commit = os.path.join(repo_dir, "hooks", "post-commit")
        hook = PostCommitShellHook(repo_dir)

        with open(post_commit, "w") as f:
            f.write(post_commit_fail)
        os.chmod(post_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        self.assertRaises(errors.HookError, hook.execute)

        if sys.platform != "darwin":
            # Don't bother running this test on darwin since path
            # canonicalization messages with our simple string comparison.
            with open(post_commit, "w") as f:
                f.write(post_commit_cwd)
            os.chmod(post_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

            hook.execute()

        with open(post_commit, "w") as f:
            f.write(post_commit_success)
        os.chmod(post_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        hook.execute()
        self.assertFalse(os.path.exists(path))
