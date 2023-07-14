# test_fastexport.py -- Fast export/import functionality
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

import stat
from io import BytesIO

from dulwich.tests import SkipTest, TestCase

from ..object_store import MemoryObjectStore
from ..objects import ZERO_SHA, Blob, Commit, Tree
from ..repo import MemoryRepo
from .utils import build_commit_graph


class GitFastExporterTests(TestCase):
    """Tests for the GitFastExporter tests."""

    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.stream = BytesIO()
        try:
            from ..fastexport import GitFastExporter
        except ImportError as exc:
            raise SkipTest("python-fastimport not available") from exc
        self.fastexporter = GitFastExporter(self.stream, self.store)

    def test_emit_blob(self):
        b = Blob()
        b.data = b"fooBAR"
        self.fastexporter.emit_blob(b)
        self.assertEqual(b"blob\nmark :1\ndata 6\nfooBAR\n", self.stream.getvalue())

    def test_emit_commit(self):
        b = Blob()
        b.data = b"FOO"
        t = Tree()
        t.add(b"foo", stat.S_IFREG | 0o644, b.id)
        c = Commit()
        c.committer = c.author = b"Jelmer <jelmer@host>"
        c.author_time = c.commit_time = 1271345553
        c.author_timezone = c.commit_timezone = 0
        c.message = b"msg"
        c.tree = t.id
        self.store.add_objects([(b, None), (t, None), (c, None)])
        self.fastexporter.emit_commit(c, b"refs/heads/master")
        self.assertEqual(
            b"""blob
mark :1
data 3
FOO
commit refs/heads/master
mark :2
author Jelmer <jelmer@host> 1271345553 +0000
committer Jelmer <jelmer@host> 1271345553 +0000
data 3
msg
M 644 :1 foo
""",
            self.stream.getvalue(),
        )


class GitImportProcessorTests(TestCase):
    """Tests for the GitImportProcessor tests."""

    def setUp(self):
        super().setUp()
        self.repo = MemoryRepo()
        try:
            from ..fastexport import GitImportProcessor
        except ImportError as exc:
            raise SkipTest("python-fastimport not available") from exc
        self.processor = GitImportProcessor(self.repo)

    def test_reset_handler(self):
        from fastimport import commands

        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        cmd = commands.ResetCommand(b"refs/heads/foo", c1.id)
        self.processor.reset_handler(cmd)
        self.assertEqual(c1.id, self.repo.get_refs()[b"refs/heads/foo"])
        self.assertEqual(c1.id, self.processor.last_commit)

    def test_reset_handler_marker(self):
        from fastimport import commands

        [c1, c2] = build_commit_graph(self.repo.object_store, [[1], [2]])
        self.processor.markers[b"10"] = c1.id
        cmd = commands.ResetCommand(b"refs/heads/foo", b":10")
        self.processor.reset_handler(cmd)
        self.assertEqual(c1.id, self.repo.get_refs()[b"refs/heads/foo"])

    def test_reset_handler_default(self):
        from fastimport import commands

        [c1, c2] = build_commit_graph(self.repo.object_store, [[1], [2]])
        cmd = commands.ResetCommand(b"refs/heads/foo", None)
        self.processor.reset_handler(cmd)
        self.assertEqual(ZERO_SHA, self.repo.get_refs()[b"refs/heads/foo"])

    def test_commit_handler(self):
        from fastimport import commands

        cmd = commands.CommitCommand(
            b"refs/heads/foo",
            b"mrkr",
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            b"FOO",
            None,
            [],
            [],
        )
        self.processor.commit_handler(cmd)
        commit = self.repo[self.processor.last_commit]
        self.assertEqual(b"Jelmer <jelmer@samba.org>", commit.author)
        self.assertEqual(b"Jelmer <jelmer@samba.org>", commit.committer)
        self.assertEqual(b"FOO", commit.message)
        self.assertEqual([], commit.parents)
        self.assertEqual(432432432.0, commit.commit_time)
        self.assertEqual(432432432.0, commit.author_time)
        self.assertEqual(3600, commit.commit_timezone)
        self.assertEqual(3600, commit.author_timezone)
        self.assertEqual(commit, self.repo[b"refs/heads/foo"])

    def test_commit_handler_markers(self):
        from fastimport import commands

        [c1, c2, c3] = build_commit_graph(self.repo.object_store, [[1], [2], [3]])
        self.processor.markers[b"10"] = c1.id
        self.processor.markers[b"42"] = c2.id
        self.processor.markers[b"98"] = c3.id
        cmd = commands.CommitCommand(
            b"refs/heads/foo",
            b"mrkr",
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            b"FOO",
            b":10",
            [b":42", b":98"],
            [],
        )
        self.processor.commit_handler(cmd)
        commit = self.repo[self.processor.last_commit]
        self.assertEqual(c1.id, commit.parents[0])
        self.assertEqual(c2.id, commit.parents[1])
        self.assertEqual(c3.id, commit.parents[2])

    def test_import_stream(self):
        markers = self.processor.import_stream(
            BytesIO(
                b"""blob
mark :1
data 11
text for a

commit refs/heads/master
mark :2
committer Joe Foo <joe@foo.com> 1288287382 +0000
data 20
<The commit message>
M 100644 :1 a

"""
            )
        )
        self.assertEqual(2, len(markers))
        self.assertIsInstance(self.repo[markers[b"1"]], Blob)
        self.assertIsInstance(self.repo[markers[b"2"]], Commit)

    def test_file_add(self):
        from fastimport import commands

        cmd = commands.BlobCommand(b"23", b"data")
        self.processor.blob_handler(cmd)
        cmd = commands.CommitCommand(
            b"refs/heads/foo",
            b"mrkr",
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            b"FOO",
            None,
            [],
            [commands.FileModifyCommand(b"path", 0o100644, b":23", None)],
        )
        self.processor.commit_handler(cmd)
        commit = self.repo[self.processor.last_commit]
        self.assertEqual(
            [(b"path", 0o100644, b"6320cd248dd8aeaab759d5871f8781b5c0505172")],
            self.repo[commit.tree].items(),
        )

    def simple_commit(self):
        from fastimport import commands

        cmd = commands.BlobCommand(b"23", b"data")
        self.processor.blob_handler(cmd)
        cmd = commands.CommitCommand(
            b"refs/heads/foo",
            b"mrkr",
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            b"FOO",
            None,
            [],
            [commands.FileModifyCommand(b"path", 0o100644, b":23", None)],
        )
        self.processor.commit_handler(cmd)
        commit = self.repo[self.processor.last_commit]
        return commit

    def make_file_commit(self, file_cmds):
        """Create a trivial commit with the specified file commands.

        Args:
          file_cmds: File commands to run.
        Returns: The created commit object
        """
        from fastimport import commands

        cmd = commands.CommitCommand(
            b"refs/heads/foo",
            b"mrkr",
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            (b"Jelmer", b"jelmer@samba.org", 432432432.0, 3600),
            b"FOO",
            None,
            [],
            file_cmds,
        )
        self.processor.commit_handler(cmd)
        return self.repo[self.processor.last_commit]

    def test_file_copy(self):
        from fastimport import commands

        self.simple_commit()
        commit = self.make_file_commit([commands.FileCopyCommand(b"path", b"new_path")])
        self.assertEqual(
            [
                (
                    b"new_path",
                    0o100644,
                    b"6320cd248dd8aeaab759d5871f8781b5c0505172",
                ),
                (
                    b"path",
                    0o100644,
                    b"6320cd248dd8aeaab759d5871f8781b5c0505172",
                ),
            ],
            self.repo[commit.tree].items(),
        )

    def test_file_move(self):
        from fastimport import commands

        self.simple_commit()
        commit = self.make_file_commit(
            [commands.FileRenameCommand(b"path", b"new_path")]
        )
        self.assertEqual(
            [
                (
                    b"new_path",
                    0o100644,
                    b"6320cd248dd8aeaab759d5871f8781b5c0505172",
                ),
            ],
            self.repo[commit.tree].items(),
        )

    def test_file_delete(self):
        from fastimport import commands

        self.simple_commit()
        commit = self.make_file_commit([commands.FileDeleteCommand(b"path")])
        self.assertEqual([], self.repo[commit.tree].items())

    def test_file_deleteall(self):
        from fastimport import commands

        self.simple_commit()
        commit = self.make_file_commit([commands.FileDeleteAllCommand()])
        self.assertEqual([], self.repo[commit.tree].items())
