# test_blackbox.py -- blackbox tests
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

"""Blackbox tests for Dulwich commands."""

import shutil
import tempfile

from dulwich.tests import BlackboxTestCase

from ..repo import Repo


class GitReceivePackTests(BlackboxTestCase):
    """Blackbox tests for dul-receive-pack."""

    def setUp(self):
        super().setUp()
        self.path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.path)
        self.repo = Repo.init(self.path)

    def test_basic(self):
        process = self.run_command("dul-receive-pack", [self.path])
        (stdout, stderr) = process.communicate(b"0000")
        self.assertEqual(b"0000", stdout[-4:])
        self.assertEqual(0, process.returncode)

    def test_missing_arg(self):
        process = self.run_command("dul-receive-pack", [])
        (stdout, stderr) = process.communicate()
        self.assertEqual(
            [b"usage: dul-receive-pack <git-dir>"], stderr.splitlines()[-1:]
        )
        self.assertEqual(b"", stdout)
        self.assertEqual(1, process.returncode)


class GitUploadPackTests(BlackboxTestCase):
    """Blackbox tests for dul-upload-pack."""

    def setUp(self):
        super().setUp()
        self.path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.path)
        self.repo = Repo.init(self.path)

    def test_missing_arg(self):
        process = self.run_command("dul-upload-pack", [])
        (stdout, stderr) = process.communicate()
        self.assertEqual(
            [b"usage: dul-upload-pack <git-dir>"], stderr.splitlines()[-1:]
        )
        self.assertEqual(b"", stdout)
        self.assertEqual(1, process.returncode)
