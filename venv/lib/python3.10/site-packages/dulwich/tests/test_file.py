# test_file.py -- Test for git files
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

import io
import os
import shutil
import sys
import tempfile

from dulwich.tests import SkipTest, TestCase

from ..file import FileLocked, GitFile, _fancy_rename


class FancyRenameTests(TestCase):
    def setUp(self):
        super().setUp()
        self._tempdir = tempfile.mkdtemp()
        self.foo = self.path("foo")
        self.bar = self.path("bar")
        self.create(self.foo, b"foo contents")

    def tearDown(self):
        shutil.rmtree(self._tempdir)
        super().tearDown()

    def path(self, filename):
        return os.path.join(self._tempdir, filename)

    def create(self, path, contents):
        f = open(path, "wb")
        f.write(contents)
        f.close()

    def test_no_dest_exists(self):
        self.assertFalse(os.path.exists(self.bar))
        _fancy_rename(self.foo, self.bar)
        self.assertFalse(os.path.exists(self.foo))

        new_f = open(self.bar, "rb")
        self.assertEqual(b"foo contents", new_f.read())
        new_f.close()

    def test_dest_exists(self):
        self.create(self.bar, b"bar contents")
        _fancy_rename(self.foo, self.bar)
        self.assertFalse(os.path.exists(self.foo))

        new_f = open(self.bar, "rb")
        self.assertEqual(b"foo contents", new_f.read())
        new_f.close()

    def test_dest_opened(self):
        if sys.platform != "win32":
            raise SkipTest("platform allows overwriting open files")
        self.create(self.bar, b"bar contents")
        dest_f = open(self.bar, "rb")
        self.assertRaises(OSError, _fancy_rename, self.foo, self.bar)
        dest_f.close()
        self.assertTrue(os.path.exists(self.path("foo")))

        new_f = open(self.foo, "rb")
        self.assertEqual(b"foo contents", new_f.read())
        new_f.close()

        new_f = open(self.bar, "rb")
        self.assertEqual(b"bar contents", new_f.read())
        new_f.close()


class GitFileTests(TestCase):
    def setUp(self):
        super().setUp()
        self._tempdir = tempfile.mkdtemp()
        f = open(self.path("foo"), "wb")
        f.write(b"foo contents")
        f.close()

    def tearDown(self):
        shutil.rmtree(self._tempdir)
        super().tearDown()

    def path(self, filename):
        return os.path.join(self._tempdir, filename)

    def test_invalid(self):
        foo = self.path("foo")
        self.assertRaises(IOError, GitFile, foo, mode="r")
        self.assertRaises(IOError, GitFile, foo, mode="ab")
        self.assertRaises(IOError, GitFile, foo, mode="r+b")
        self.assertRaises(IOError, GitFile, foo, mode="w+b")
        self.assertRaises(IOError, GitFile, foo, mode="a+bU")

    def test_readonly(self):
        f = GitFile(self.path("foo"), "rb")
        self.assertIsInstance(f, io.IOBase)
        self.assertEqual(b"foo contents", f.read())
        self.assertEqual(b"", f.read())
        f.seek(4)
        self.assertEqual(b"contents", f.read())
        f.close()

    def test_default_mode(self):
        f = GitFile(self.path("foo"))
        self.assertEqual(b"foo contents", f.read())
        f.close()

    def test_write(self):
        foo = self.path("foo")
        foo_lock = "%s.lock" % foo

        orig_f = open(foo, "rb")
        self.assertEqual(orig_f.read(), b"foo contents")
        orig_f.close()

        self.assertFalse(os.path.exists(foo_lock))
        f = GitFile(foo, "wb")
        self.assertFalse(f.closed)
        self.assertRaises(AttributeError, getattr, f, "not_a_file_property")

        self.assertTrue(os.path.exists(foo_lock))
        f.write(b"new stuff")
        f.seek(4)
        f.write(b"contents")
        f.close()
        self.assertFalse(os.path.exists(foo_lock))

        new_f = open(foo, "rb")
        self.assertEqual(b"new contents", new_f.read())
        new_f.close()

    def test_open_twice(self):
        foo = self.path("foo")
        f1 = GitFile(foo, "wb")
        f1.write(b"new")
        try:
            f2 = GitFile(foo, "wb")
            self.fail()
        except FileLocked:
            pass
        else:
            f2.close()
        f1.write(b" contents")
        f1.close()

        # Ensure trying to open twice doesn't affect original.
        f = open(foo, "rb")
        self.assertEqual(b"new contents", f.read())
        f.close()

    def test_abort(self):
        foo = self.path("foo")
        foo_lock = "%s.lock" % foo

        orig_f = open(foo, "rb")
        self.assertEqual(orig_f.read(), b"foo contents")
        orig_f.close()

        f = GitFile(foo, "wb")
        f.write(b"new contents")
        f.abort()
        self.assertTrue(f.closed)
        self.assertFalse(os.path.exists(foo_lock))

        new_orig_f = open(foo, "rb")
        self.assertEqual(new_orig_f.read(), b"foo contents")
        new_orig_f.close()

    def test_abort_close(self):
        foo = self.path("foo")
        f = GitFile(foo, "wb")
        f.abort()
        try:
            f.close()
        except OSError:
            self.fail()

        f = GitFile(foo, "wb")
        f.close()
        try:
            f.abort()
        except OSError:
            self.fail()

    def test_abort_close_removed(self):
        foo = self.path("foo")
        f = GitFile(foo, "wb")

        f._file.close()
        os.remove(foo + ".lock")

        f.abort()
        self.assertTrue(f._closed)
