# __init__.py -- The tests for dulwich
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

"""Tests for Dulwich."""

__all__ = [
    'SkipTest',
    'TestCase',
    'BlackboxTestCase',
    'skipIf',
    'expectedFailure',
]

import doctest
import os
import shutil
import subprocess
import sys
import tempfile
# If Python itself provides an exception, use that
import unittest
from unittest import SkipTest
from unittest import TestCase as _TestCase  # noqa: F401
from unittest import expectedFailure, skipIf


class TestCase(_TestCase):
    def setUp(self):
        super().setUp()
        self.overrideEnv("HOME", "/nonexistent")
        self.overrideEnv("GIT_CONFIG_NOSYSTEM", "1")

    def overrideEnv(self, name, value):
        def restore():
            if oldval is not None:
                os.environ[name] = oldval
            else:
                del os.environ[name]

        oldval = os.environ.get(name)
        if value is not None:
            os.environ[name] = value
        else:
            del os.environ[name]
        self.addCleanup(restore)


class BlackboxTestCase(TestCase):
    """Blackbox testing."""

    # TODO(jelmer): Include more possible binary paths.
    bin_directories = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bin")),
        "/usr/bin",
        "/usr/local/bin",
    ]

    def bin_path(self, name):
        """Determine the full path of a binary.

        Args:
          name: Name of the script
        Returns: Full path
        """
        for d in self.bin_directories:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
        else:
            raise SkipTest("Unable to find binary %s" % name)

    def run_command(self, name, args):
        """Run a Dulwich command.

        Args:
          name: Name of the command, as it exists in bin/
          args: Arguments to the command
        """
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        # Since they don't have any extensions, Windows can't recognize
        # executablility of the Python files in /bin. Even then, we'd have to
        # expect the user to set up file associations for .py files.
        #
        # Save us from all that headache and call python with the bin script.
        argv = [sys.executable, self.bin_path(name)] + args
        return subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )


def self_test_suite():
    names = [
        "archive",
        "blackbox",
        "bundle",
        "client",
        "config",
        "credentials",
        "diff_tree",
        "fastexport",
        "file",
        "grafts",
        "graph",
        "greenthreads",
        "hooks",
        "ignore",
        "index",
        "lfs",
        "line_ending",
        "lru_cache",
        "mailmap",
        "objects",
        "objectspec",
        "object_store",
        "missing_obj_finder",
        "pack",
        "patch",
        "porcelain",
        "protocol",
        "reflog",
        "refs",
        "repository",
        "server",
        "stash",
        "utils",
        "walk",
        "web",
    ]
    module_names = ["dulwich.tests.test_" + name for name in names]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)


def tutorial_test_suite():
    import dulwich.client
    import dulwich.config
    import dulwich.index
    import dulwich.patch  # noqa: F401

    tutorial = [
        "introduction",
        "file-format",
        "repo",
        "object-store",
        "remote",
        "conclusion",
    ]
    tutorial_files = [f"../../docs/tutorial/{name}.txt" for name in tutorial]

    to_restore = []

    def overrideEnv(name, value):
        oldval = os.environ.get(name)
        if value is not None:
            os.environ[name] = value
        else:
            del os.environ[name]
        to_restore.append((name, oldval))

    def setup(test):
        test.__old_cwd = os.getcwd()
        test.tempdir = tempfile.mkdtemp()
        test.globs.update({"tempdir": test.tempdir})
        os.chdir(test.tempdir)
        overrideEnv("HOME", "/nonexistent")
        overrideEnv("GIT_CONFIG_NOSYSTEM", "1")

    def teardown(test):
        os.chdir(test.__old_cwd)
        shutil.rmtree(test.tempdir)
        for name, oldval in to_restore:
            if oldval is not None:
                os.environ[name] = oldval
            else:
                del os.environ[name]
        to_restore.clear()

    return doctest.DocFileSuite(
        module_relative=True,
        package="dulwich.tests",
        setUp=setup,
        tearDown=teardown,
        *tutorial_files
    )


def nocompat_test_suite():
    result = unittest.TestSuite()
    result.addTests(self_test_suite())
    result.addTests(tutorial_test_suite())
    from dulwich.contrib import test_suite as contrib_test_suite

    result.addTests(contrib_test_suite())
    return result


def compat_test_suite():
    result = unittest.TestSuite()
    from dulwich.tests.compat import test_suite as compat_test_suite

    result.addTests(compat_test_suite())
    return result


def test_suite():
    result = unittest.TestSuite()
    result.addTests(self_test_suite())
    if sys.platform != "win32":
        result.addTests(tutorial_test_suite())
    from dulwich.tests.compat import test_suite as compat_test_suite

    result.addTests(compat_test_suite())
    from dulwich.contrib import test_suite as contrib_test_suite

    result.addTests(contrib_test_suite())
    return result
