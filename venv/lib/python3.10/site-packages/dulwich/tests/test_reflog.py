# test_reflog.py -- tests for reflog.py
# Copyright (C) 2015 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for dulwich.reflog."""

from io import BytesIO

from dulwich.tests import TestCase

from ..objects import ZERO_SHA
from ..reflog import (drop_reflog_entry, format_reflog_line, parse_reflog_line,
                      read_reflog)


class ReflogLineTests(TestCase):
    def test_format(self):
        self.assertEqual(
            b"0000000000000000000000000000000000000000 "
            b"49030649db3dfec5a9bc03e5dde4255a14499f16 Jelmer Vernooij "
            b"<jelmer@jelmer.uk> 1446552482 +0000	"
            b"clone: from git://jelmer.uk/samba",
            format_reflog_line(
                b"0000000000000000000000000000000000000000",
                b"49030649db3dfec5a9bc03e5dde4255a14499f16",
                b"Jelmer Vernooij <jelmer@jelmer.uk>",
                1446552482,
                0,
                b"clone: from git://jelmer.uk/samba",
            ),
        )

        self.assertEqual(
            b"0000000000000000000000000000000000000000 "
            b"49030649db3dfec5a9bc03e5dde4255a14499f16 Jelmer Vernooij "
            b"<jelmer@jelmer.uk> 1446552482 +0000	"
            b"clone: from git://jelmer.uk/samba",
            format_reflog_line(
                None,
                b"49030649db3dfec5a9bc03e5dde4255a14499f16",
                b"Jelmer Vernooij <jelmer@jelmer.uk>",
                1446552482,
                0,
                b"clone: from git://jelmer.uk/samba",
            ),
        )

    def test_parse(self):
        reflog_line = (
            b"0000000000000000000000000000000000000000 "
            b"49030649db3dfec5a9bc03e5dde4255a14499f16 Jelmer Vernooij "
            b"<jelmer@jelmer.uk> 1446552482 +0000	"
            b"clone: from git://jelmer.uk/samba"
        )
        self.assertEqual(
            (
                b"0000000000000000000000000000000000000000",
                b"49030649db3dfec5a9bc03e5dde4255a14499f16",
                b"Jelmer Vernooij <jelmer@jelmer.uk>",
                1446552482,
                0,
                b"clone: from git://jelmer.uk/samba",
            ),
            parse_reflog_line(reflog_line),
        )


_TEST_REFLOG = (
    b"0000000000000000000000000000000000000000 "
    b"49030649db3dfec5a9bc03e5dde4255a14499f16 Jelmer Vernooij "
    b"<jelmer@jelmer.uk> 1446552482 +0000	"
    b"clone: from git://jelmer.uk/samba\n"
    b"49030649db3dfec5a9bc03e5dde4255a14499f16 "
    b"42d06bd4b77fed026b154d16493e5deab78f02ec Jelmer Vernooij "
    b"<jelmer@jelmer.uk> 1446552483 +0000	"
    b"clone: from git://jelmer.uk/samba\n"
    b"42d06bd4b77fed026b154d16493e5deab78f02ec "
    b"df6800012397fb85c56e7418dd4eb9405dee075c Jelmer Vernooij "
    b"<jelmer@jelmer.uk> 1446552484 +0000	"
    b"clone: from git://jelmer.uk/samba\n"
)


class ReflogDropTests(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.f = BytesIO(_TEST_REFLOG)
        self.original_log = list(read_reflog(self.f))
        self.f.seek(0)

    def _read_log(self):
        self.f.seek(0)
        return list(read_reflog(self.f))

    def test_invalid(self):
        self.assertRaises(ValueError, drop_reflog_entry, self.f, -1)

    def test_drop_entry(self):
        drop_reflog_entry(self.f, 0)
        log = self._read_log()
        self.assertEqual(len(log), 2)
        self.assertEqual(self.original_log[0:2], log)

        self.f.seek(0)
        drop_reflog_entry(self.f, 1)
        log = self._read_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(self.original_log[1], log[0])

    def test_drop_entry_with_rewrite(self):
        drop_reflog_entry(self.f, 1, True)
        log = self._read_log()
        self.assertEqual(len(log), 2)
        self.assertEqual(self.original_log[0], log[0])
        self.assertEqual(self.original_log[0].new_sha, log[1].old_sha)
        self.assertEqual(self.original_log[2].new_sha, log[1].new_sha)

        self.f.seek(0)
        drop_reflog_entry(self.f, 1, True)
        log = self._read_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(ZERO_SHA, log[0].old_sha)
        self.assertEqual(self.original_log[2].new_sha, log[0].new_sha)
