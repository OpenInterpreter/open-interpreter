# test_porcelain .py -- Tests for dulwich.porcelain/CGit compatibility
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

"""Compatibility tests for dulwich.porcelain."""

import os
import platform
import sys
from unittest import skipIf

from dulwich import porcelain

from ..test_porcelain import PorcelainGpgTestCase
from ..utils import build_commit_graph
from .utils import CompatTestCase, run_git_or_fail


@skipIf(platform.python_implementation() == "PyPy" or sys.platform == "win32", "gpgme not easily available or supported on Windows and PyPy")
class TagCreateSignTestCase(PorcelainGpgTestCase, CompatTestCase):
    def setUp(self):
        super().setUp()

    def test_sign(self):
        # Test that dulwich signatures can be verified by CGit
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        cfg = self.repo.get_config()
        cfg.set(("user",), "signingKey", PorcelainGpgTestCase.DEFAULT_KEY_ID)
        self.import_default_key()

        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
            sign=True,
        )

        run_git_or_fail(
            [
                f"--git-dir={self.repo.controldir()}",
                "tag",
                "-v",
                "tryme"
            ],
            env={'GNUPGHOME': os.environ['GNUPGHOME']},
        )

    def test_verify(self):
        # Test that CGit signatures can be verified by dulwich
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        self.import_default_key()

        run_git_or_fail(
            [
                f"--git-dir={self.repo.controldir()}",
                "tag",
                "-u",
                PorcelainGpgTestCase.DEFAULT_KEY_ID,
                "-m",
                "foo",
                "verifyme",
            ],
            env={
                'GNUPGHOME': os.environ['GNUPGHOME'],
                'GIT_COMMITTER_NAME': 'Joe Example',
                'GIT_COMMITTER_EMAIL': 'joe@example.com',
            },
        )
        tag = self.repo[b"refs/tags/verifyme"]
        self.assertNotEqual(tag.signature, None)
        tag.verify()
