# utils.py -- Git compatibility utilities
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

"""Utilities for interacting with cgit."""

import errno
import functools
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Tuple

from dulwich.tests import SkipTest, TestCase

from ...protocol import TCP_GIT_PORT
from ...repo import Repo

_DEFAULT_GIT = "git"
_VERSION_LEN = 4
_REPOS_DATA_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), os.pardir, os.pardir, os.pardir,
        "testdata", "repos")
)


def git_version(git_path=_DEFAULT_GIT):
    """Attempt to determine the version of git currently installed.

    Args:
      git_path: Path to the git executable; defaults to the version in
        the system path.
    Returns: A tuple of ints of the form (major, minor, point, sub-point), or
        None if no git installation was found.
    """
    try:
        output = run_git_or_fail(["--version"], git_path=git_path)
    except OSError:
        return None
    version_prefix = b"git version "
    if not output.startswith(version_prefix):
        return None

    parts = output[len(version_prefix) :].split(b".")
    nums = []
    for part in parts:
        try:
            nums.append(int(part))
        except ValueError:
            break

    while len(nums) < _VERSION_LEN:
        nums.append(0)
    return tuple(nums[:_VERSION_LEN])


def require_git_version(required_version, git_path=_DEFAULT_GIT):
    """Require git version >= version, or skip the calling test.

    Args:
      required_version: A tuple of ints of the form (major, minor, point,
        sub-point); omitted components default to 0.
      git_path: Path to the git executable; defaults to the version in
        the system path.
    Raises:
      ValueError: if the required version tuple has too many parts.
      SkipTest: if no suitable git version was found at the given path.
    """
    found_version = git_version(git_path=git_path)
    if found_version is None:
        raise SkipTest(
            "Test requires git >= {}, but c git not found".format(required_version)
        )

    if len(required_version) > _VERSION_LEN:
        raise ValueError(
            "Invalid version tuple %s, expected %i parts"
            % (required_version, _VERSION_LEN)
        )

    required_version = list(required_version)
    while len(found_version) < len(required_version):
        required_version.append(0)
    required_version = tuple(required_version)

    if found_version < required_version:
        required_version = ".".join(map(str, required_version))
        found_version = ".".join(map(str, found_version))
        raise SkipTest(
            "Test requires git >= {}, found {}".format(required_version, found_version)
        )


def run_git(
    args, git_path=_DEFAULT_GIT, input=None, capture_stdout=False,
    capture_stderr=False, **popen_kwargs
):
    """Run a git command.

    Input is piped from the input parameter and output is sent to the standard
    streams, unless capture_stdout is set.

    Args:
      args: A list of args to the git command.
      git_path: Path to to the git executable.
      input: Input data to be sent to stdin.
      capture_stdout: Whether to capture and return stdout.
      popen_kwargs: Additional kwargs for subprocess.Popen;
        stdin/stdout args are ignored.
    Returns: A tuple of (returncode, stdout contents, stderr contents).
        If capture_stdout is False, None will be returned as stdout contents.
        If capture_stderr is False, None will be returned as stderr contents.
    Raises:
      OSError: if the git executable was not found.
    """

    env = popen_kwargs.pop("env", {})
    env["LC_ALL"] = env["LANG"] = "C"
    env["PATH"] = os.getenv("PATH")

    args = [git_path] + args
    popen_kwargs["stdin"] = subprocess.PIPE
    if capture_stdout:
        popen_kwargs["stdout"] = subprocess.PIPE
    else:
        popen_kwargs.pop("stdout", None)
    if capture_stderr:
        popen_kwargs["stderr"] = subprocess.PIPE
    else:
        popen_kwargs.pop("stderr", None)
    p = subprocess.Popen(args, env=env, **popen_kwargs)
    stdout, stderr = p.communicate(input=input)
    return (p.returncode, stdout, stderr)


def run_git_or_fail(args, git_path=_DEFAULT_GIT, input=None, **popen_kwargs):
    """Run a git command, capture stdout/stderr, and fail if git fails."""
    if "stderr" not in popen_kwargs:
        popen_kwargs["stderr"] = subprocess.STDOUT
    returncode, stdout, stderr = run_git(
        args, git_path=git_path, input=input, capture_stdout=True,
        capture_stderr=True, **popen_kwargs
    )
    if returncode != 0:
        raise AssertionError(
            "git with args %r failed with %d: stdout=%r stderr=%r" % (args, returncode, stdout, stderr)
        )
    return stdout


def import_repo_to_dir(name):
    """Import a repo from a fast-export file in a temporary directory.

    These are used rather than binary repos for compat tests because they are
    more compact and human-editable, and we already depend on git.

    Args:
      name: The name of the repository export file, relative to
        dulwich/tests/data/repos.
    Returns: The path to the imported repository.
    """
    temp_dir = tempfile.mkdtemp()
    export_path = os.path.join(_REPOS_DATA_DIR, name)
    temp_repo_dir = os.path.join(temp_dir, name)
    export_file = open(export_path, "rb")
    run_git_or_fail(["init", "--quiet", "--bare", temp_repo_dir])
    run_git_or_fail(["fast-import"], input=export_file.read(), cwd=temp_repo_dir)
    export_file.close()
    return temp_repo_dir


def check_for_daemon(limit=10, delay=0.1, timeout=0.1, port=TCP_GIT_PORT):
    """Check for a running TCP daemon.

    Defaults to checking 10 times with a delay of 0.1 sec between tries.

    Args:
      limit: Number of attempts before deciding no daemon is running.
      delay: Delay between connection attempts.
      timeout: Socket timeout for connection attempts.
      port: Port on which we expect the daemon to appear.
    Returns: A boolean, true if a daemon is running on the specified port,
        false if not.
    """
    for _ in range(limit):
        time.sleep(delay)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(delay)
        try:
            s.connect(("localhost", port))
            return True
        except socket.timeout:
            pass
        except OSError as e:
            if getattr(e, "errno", False) and e.errno != errno.ECONNREFUSED:
                raise
            elif e.args[0] != errno.ECONNREFUSED:
                raise
        finally:
            s.close()
    return False


class CompatTestCase(TestCase):
    """Test case that requires git for compatibility checks.

    Subclasses can change the git version required by overriding
    min_git_version.
    """

    min_git_version: Tuple[int, ...] = (1, 5, 0)

    def setUp(self):
        super().setUp()
        require_git_version(self.min_git_version)

    def assertObjectStoreEqual(self, store1, store2):
        self.assertEqual(sorted(set(store1)), sorted(set(store2)))

    def assertReposEqual(self, repo1, repo2):
        self.assertEqual(repo1.get_refs(), repo2.get_refs())
        self.assertObjectStoreEqual(repo1.object_store, repo2.object_store)

    def assertReposNotEqual(self, repo1, repo2):
        refs1 = repo1.get_refs()
        objs1 = set(repo1.object_store)
        refs2 = repo2.get_refs()
        objs2 = set(repo2.object_store)
        self.assertFalse(refs1 == refs2 and objs1 == objs2)

    def import_repo(self, name):
        """Import a repo from a fast-export file in a temporary directory.

        Args:
          name: The name of the repository export file, relative to
            dulwich/tests/data/repos.
        Returns: An initialized Repo object that lives in a temporary
            directory.
        """
        path = import_repo_to_dir(name)
        repo = Repo(path)

        def cleanup():
            repo.close()
            rmtree_ro(os.path.dirname(path.rstrip(os.sep)))

        self.addCleanup(cleanup)
        return repo


if sys.platform == "win32":

    def remove_ro(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    rmtree_ro = functools.partial(shutil.rmtree, onerror=remove_ro)
else:
    rmtree_ro = shutil.rmtree
