# test_ignore.py -- Tests for ignore files.
# Copyright (C) 2017 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for ignore files."""

import os
import re
import shutil
import tempfile
from io import BytesIO

from dulwich.tests import TestCase

from ..ignore import (IgnoreFilter, IgnoreFilterManager, IgnoreFilterStack,
                      Pattern, match_pattern, read_ignore_patterns, translate)
from ..repo import Repo

POSITIVE_MATCH_TESTS = [
    (b"foo.c", b"*.c"),
    (b".c", b"*.c"),
    (b"foo/foo.c", b"*.c"),
    (b"foo/foo.c", b"foo.c"),
    (b"foo.c", b"/*.c"),
    (b"foo.c", b"/foo.c"),
    (b"foo.c", b"foo.c"),
    (b"foo.c", b"foo.[ch]"),
    (b"foo/bar/bla.c", b"foo/**"),
    (b"foo/bar/bla/blie.c", b"foo/**/blie.c"),
    (b"foo/bar/bla.c", b"**/bla.c"),
    (b"bla.c", b"**/bla.c"),
    (b"foo/bar", b"foo/**/bar"),
    (b"foo/bla/bar", b"foo/**/bar"),
    (b"foo/bar/", b"bar/"),
    (b"foo/bar/", b"bar"),
    (b"foo/bar/something", b"foo/bar/*"),
]

NEGATIVE_MATCH_TESTS = [
    (b"foo.c", b"foo.[dh]"),
    (b"foo/foo.c", b"/foo.c"),
    (b"foo/foo.c", b"/*.c"),
    (b"foo/bar/", b"/bar/"),
    (b"foo/bar/", b"foo/bar/*"),
    (b"foo/bar", b"foo?bar"),
]


TRANSLATE_TESTS = [
    (b"*.c", b"(?ms)(.*/)?[^/]*\\.c/?\\Z"),
    (b"foo.c", b"(?ms)(.*/)?foo\\.c/?\\Z"),
    (b"/*.c", b"(?ms)[^/]*\\.c/?\\Z"),
    (b"/foo.c", b"(?ms)foo\\.c/?\\Z"),
    (b"foo.c", b"(?ms)(.*/)?foo\\.c/?\\Z"),
    (b"foo.[ch]", b"(?ms)(.*/)?foo\\.[ch]/?\\Z"),
    (b"bar/", b"(?ms)(.*/)?bar\\/\\Z"),
    (b"foo/**", b"(?ms)foo(/.*)?/?\\Z"),
    (b"foo/**/blie.c", b"(?ms)foo(/.*)?\\/blie\\.c/?\\Z"),
    (b"**/bla.c", b"(?ms)(.*/)?bla\\.c/?\\Z"),
    (b"foo/**/bar", b"(?ms)foo(/.*)?\\/bar/?\\Z"),
    (b"foo/bar/*", b"(?ms)foo\\/bar\\/[^/]+/?\\Z"),
    (b"/foo\\[bar\\]", b"(?ms)foo\\[bar\\]/?\\Z"),
    (b"/foo[bar]", b"(?ms)foo[bar]/?\\Z"),
    (b"/foo[0-9]", b"(?ms)foo[0-9]/?\\Z"),
]


class TranslateTests(TestCase):
    def test_translate(self):
        for (pattern, regex) in TRANSLATE_TESTS:
            if re.escape(b"/") == b"/":
                # Slash is no longer escaped in Python3.7, so undo the escaping
                # in the expected return value..
                regex = regex.replace(b"\\/", b"/")
            self.assertEqual(
                regex,
                translate(pattern),
                "orig pattern: %r, regex: %r, expected: %r"
                % (pattern, translate(pattern), regex),
            )


class ReadIgnorePatterns(TestCase):
    def test_read_file(self):
        f = BytesIO(
            b"""
# a comment
\x20\x20
# and an empty line:

\\#not a comment
!negative
with trailing whitespace 
with escaped trailing whitespace\\ 
"""
        )
        self.assertEqual(
            list(read_ignore_patterns(f)),
            [
                b"\\#not a comment",
                b"!negative",
                b"with trailing whitespace",
                b"with escaped trailing whitespace ",
            ],
        )


class MatchPatternTests(TestCase):
    def test_matches(self):
        for (path, pattern) in POSITIVE_MATCH_TESTS:
            self.assertTrue(
                match_pattern(path, pattern),
                "path: {!r}, pattern: {!r}".format(path, pattern),
            )

    def test_no_matches(self):
        for (path, pattern) in NEGATIVE_MATCH_TESTS:
            self.assertFalse(
                match_pattern(path, pattern),
                "path: {!r}, pattern: {!r}".format(path, pattern),
            )


class IgnoreFilterTests(TestCase):
    def test_included(self):
        filter = IgnoreFilter([b"a.c", b"b.c"])
        self.assertTrue(filter.is_ignored(b"a.c"))
        self.assertIs(None, filter.is_ignored(b"c.c"))
        self.assertEqual([Pattern(b"a.c")], list(filter.find_matching(b"a.c")))
        self.assertEqual([], list(filter.find_matching(b"c.c")))

    def test_included_ignorecase(self):
        filter = IgnoreFilter([b"a.c", b"b.c"], ignorecase=False)
        self.assertTrue(filter.is_ignored(b"a.c"))
        self.assertFalse(filter.is_ignored(b"A.c"))
        filter = IgnoreFilter([b"a.c", b"b.c"], ignorecase=True)
        self.assertTrue(filter.is_ignored(b"a.c"))
        self.assertTrue(filter.is_ignored(b"A.c"))
        self.assertTrue(filter.is_ignored(b"A.C"))

    def test_excluded(self):
        filter = IgnoreFilter([b"a.c", b"b.c", b"!c.c"])
        self.assertFalse(filter.is_ignored(b"c.c"))
        self.assertIs(None, filter.is_ignored(b"d.c"))
        self.assertEqual([Pattern(b"!c.c")], list(filter.find_matching(b"c.c")))
        self.assertEqual([], list(filter.find_matching(b"d.c")))

    def test_include_exclude_include(self):
        filter = IgnoreFilter([b"a.c", b"!a.c", b"a.c"])
        self.assertTrue(filter.is_ignored(b"a.c"))
        self.assertEqual(
            [Pattern(b"a.c"), Pattern(b"!a.c"), Pattern(b"a.c")],
            list(filter.find_matching(b"a.c")),
        )

    def test_manpage(self):
        # A specific example from the gitignore manpage
        filter = IgnoreFilter([b"/*", b"!/foo", b"/foo/*", b"!/foo/bar"])
        self.assertTrue(filter.is_ignored(b"a.c"))
        self.assertTrue(filter.is_ignored(b"foo/blie"))
        self.assertFalse(filter.is_ignored(b"foo"))
        self.assertFalse(filter.is_ignored(b"foo/bar"))
        self.assertFalse(filter.is_ignored(b"foo/bar/"))
        self.assertFalse(filter.is_ignored(b"foo/bar/bloe"))

    def test_regex_special(self):
        # See https://github.com/dulwich/dulwich/issues/930#issuecomment-1026166429
        filter = IgnoreFilter([b"/foo\\[bar\\]", b"/foo"])
        self.assertTrue(filter.is_ignored("foo"))
        self.assertTrue(filter.is_ignored("foo[bar]"))


class IgnoreFilterStackTests(TestCase):
    def test_stack_first(self):
        filter1 = IgnoreFilter([b"[a].c", b"[b].c", b"![d].c"])
        filter2 = IgnoreFilter([b"[a].c", b"![b],c", b"[c].c", b"[d].c"])
        stack = IgnoreFilterStack([filter1, filter2])
        self.assertIs(True, stack.is_ignored(b"a.c"))
        self.assertIs(True, stack.is_ignored(b"b.c"))
        self.assertIs(True, stack.is_ignored(b"c.c"))
        self.assertIs(False, stack.is_ignored(b"d.c"))
        self.assertIs(None, stack.is_ignored(b"e.c"))


class IgnoreFilterManagerTests(TestCase):
    def test_load_ignore(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(tmp_dir)
        with open(os.path.join(repo.path, ".gitignore"), "wb") as f:
            f.write(b"/foo/bar\n")
            f.write(b"/dir2\n")
            f.write(b"/dir3/\n")
        os.mkdir(os.path.join(repo.path, "dir"))
        with open(os.path.join(repo.path, "dir", ".gitignore"), "wb") as f:
            f.write(b"/blie\n")
        with open(os.path.join(repo.path, "dir", "blie"), "wb") as f:
            f.write(b"IGNORED")
        p = os.path.join(repo.controldir(), "info", "exclude")
        with open(p, "wb") as f:
            f.write(b"/excluded\n")
        m = IgnoreFilterManager.from_repo(repo)
        self.assertTrue(m.is_ignored("dir/blie"))
        self.assertIs(None, m.is_ignored(os.path.join("dir", "bloe")))
        self.assertIs(None, m.is_ignored("dir"))
        self.assertTrue(m.is_ignored(os.path.join("foo", "bar")))
        self.assertTrue(m.is_ignored(os.path.join("excluded")))
        self.assertTrue(m.is_ignored(os.path.join("dir2", "fileinignoreddir")))
        self.assertFalse(m.is_ignored("dir3"))
        self.assertTrue(m.is_ignored("dir3/"))
        self.assertTrue(m.is_ignored("dir3/bla"))

    def test_nested_gitignores(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(tmp_dir)

        with open(os.path.join(repo.path, '.gitignore'), 'wb') as f:
            f.write(b'/*\n')
            f.write(b'!/foo\n')

        os.mkdir(os.path.join(repo.path, 'foo'))
        with open(os.path.join(repo.path, 'foo', '.gitignore'), 'wb') as f:
            f.write(b'/bar\n')

        with open(os.path.join(repo.path, 'foo', 'bar'), 'wb') as f:
            f.write(b'IGNORED')

        m = IgnoreFilterManager.from_repo(repo)
        self.assertTrue(m.is_ignored('foo/bar'))

    def test_load_ignore_ignorecase(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(tmp_dir)
        config = repo.get_config()
        config.set(b"core", b"ignorecase", True)
        config.write_to_path()
        with open(os.path.join(repo.path, ".gitignore"), "wb") as f:
            f.write(b"/foo/bar\n")
            f.write(b"/dir\n")
        m = IgnoreFilterManager.from_repo(repo)
        self.assertTrue(m.is_ignored(os.path.join("dir", "blie")))
        self.assertTrue(m.is_ignored(os.path.join("DIR", "blie")))

    def test_ignored_contents(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        repo = Repo.init(tmp_dir)
        with open(os.path.join(repo.path, ".gitignore"), "wb") as f:
            f.write(b"a/*\n")
            f.write(b"!a/*.txt\n")
        m = IgnoreFilterManager.from_repo(repo)
        os.mkdir(os.path.join(repo.path, "a"))
        self.assertIs(None, m.is_ignored("a"))
        self.assertIs(None, m.is_ignored("a/"))
        self.assertFalse(m.is_ignored("a/b.txt"))
        self.assertTrue(m.is_ignored("a/c.dat"))
