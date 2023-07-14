# __init__.py -- Fast export/import functionality
# Copyright (C) 2010-2013 Jelmer Vernooij <jelmer@jelmer.uk>
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


"""Fast export/import functionality."""

import stat

from fastimport import commands
from fastimport import errors as fastimport_errors
from fastimport import parser, processor

from .index import commit_tree
from .object_store import iter_tree_contents
from .objects import ZERO_SHA, Blob, Commit, Tag


def split_email(text):
    (name, email) = text.rsplit(b" <", 1)
    return (name, email.rstrip(b">"))


class GitFastExporter:
    """Generate a fast-export output stream for Git objects."""

    def __init__(self, outf, store):
        self.outf = outf
        self.store = store
        self.markers = {}
        self._marker_idx = 0

    def print_cmd(self, cmd):
        self.outf.write(getattr(cmd, "__bytes__", cmd.__repr__)() + b"\n")

    def _allocate_marker(self):
        self._marker_idx += 1
        return ("%d" % (self._marker_idx,)).encode("ascii")

    def _export_blob(self, blob):
        marker = self._allocate_marker()
        self.markers[marker] = blob.id
        return (commands.BlobCommand(marker, blob.data), marker)

    def emit_blob(self, blob):
        (cmd, marker) = self._export_blob(blob)
        self.print_cmd(cmd)
        return marker

    def _iter_files(self, base_tree, new_tree):
        for (
            (old_path, new_path),
            (old_mode, new_mode),
            (old_hexsha, new_hexsha),
        ) in self.store.tree_changes(base_tree, new_tree):
            if new_path is None:
                yield commands.FileDeleteCommand(old_path)
                continue
            if not stat.S_ISDIR(new_mode):
                blob = self.store[new_hexsha]
                marker = self.emit_blob(blob)
            if old_path != new_path and old_path is not None:
                yield commands.FileRenameCommand(old_path, new_path)
            if old_mode != new_mode or old_hexsha != new_hexsha:
                prefixed_marker = b":" + marker
                yield commands.FileModifyCommand(
                    new_path, new_mode, prefixed_marker, None
                )

    def _export_commit(self, commit, ref, base_tree=None):
        file_cmds = list(self._iter_files(base_tree, commit.tree))
        marker = self._allocate_marker()
        if commit.parents:
            from_ = commit.parents[0]
            merges = commit.parents[1:]
        else:
            from_ = None
            merges = []
        author, author_email = split_email(commit.author)
        committer, committer_email = split_email(commit.committer)
        cmd = commands.CommitCommand(
            ref,
            marker,
            (author, author_email, commit.author_time, commit.author_timezone),
            (
                committer,
                committer_email,
                commit.commit_time,
                commit.commit_timezone,
            ),
            commit.message,
            from_,
            merges,
            file_cmds,
        )
        return (cmd, marker)

    def emit_commit(self, commit, ref, base_tree=None):
        cmd, marker = self._export_commit(commit, ref, base_tree)
        self.print_cmd(cmd)
        return marker


class GitImportProcessor(processor.ImportProcessor):
    """An import processor that imports into a Git repository using Dulwich."""

    # FIXME: Batch creation of objects?

    def __init__(self, repo, params=None, verbose=False, outf=None):
        processor.ImportProcessor.__init__(self, params, verbose)
        self.repo = repo
        self.last_commit = ZERO_SHA
        self.markers = {}
        self._contents = {}

    def lookup_object(self, objectish):
        if objectish.startswith(b":"):
            return self.markers[objectish[1:]]
        return objectish

    def import_stream(self, stream):
        p = parser.ImportParser(stream)
        self.process(p.iter_commands)
        return self.markers

    def blob_handler(self, cmd):
        """Process a BlobCommand."""
        blob = Blob.from_string(cmd.data)
        self.repo.object_store.add_object(blob)
        if cmd.mark:
            self.markers[cmd.mark] = blob.id

    def checkpoint_handler(self, cmd):
        """Process a CheckpointCommand."""
        pass

    def commit_handler(self, cmd):
        """Process a CommitCommand."""
        commit = Commit()
        if cmd.author is not None:
            author = cmd.author
        else:
            author = cmd.committer
        (author_name, author_email, author_timestamp, author_timezone) = author
        (
            committer_name,
            committer_email,
            commit_timestamp,
            commit_timezone,
        ) = cmd.committer
        commit.author = author_name + b" <" + author_email + b">"
        commit.author_timezone = author_timezone
        commit.author_time = int(author_timestamp)
        commit.committer = committer_name + b" <" + committer_email + b">"
        commit.commit_timezone = commit_timezone
        commit.commit_time = int(commit_timestamp)
        commit.message = cmd.message
        commit.parents = []
        if cmd.from_:
            cmd.from_ = self.lookup_object(cmd.from_)
            self._reset_base(cmd.from_)
        for filecmd in cmd.iter_files():
            if filecmd.name == b"filemodify":
                if filecmd.data is not None:
                    blob = Blob.from_string(filecmd.data)
                    self.repo.object_store.add(blob)
                    blob_id = blob.id
                else:
                    blob_id = self.lookup_object(filecmd.dataref)
                self._contents[filecmd.path] = (filecmd.mode, blob_id)
            elif filecmd.name == b"filedelete":
                del self._contents[filecmd.path]
            elif filecmd.name == b"filecopy":
                self._contents[filecmd.dest_path] = self._contents[filecmd.src_path]
            elif filecmd.name == b"filerename":
                self._contents[filecmd.new_path] = self._contents[filecmd.old_path]
                del self._contents[filecmd.old_path]
            elif filecmd.name == b"filedeleteall":
                self._contents = {}
            else:
                raise Exception("Command %s not supported" % filecmd.name)
        commit.tree = commit_tree(
            self.repo.object_store,
            ((path, hexsha, mode) for (path, (mode, hexsha)) in self._contents.items()),
        )
        if self.last_commit != ZERO_SHA:
            commit.parents.append(self.last_commit)
        for merge in cmd.merges:
            commit.parents.append(self.lookup_object(merge))
        self.repo.object_store.add_object(commit)
        self.repo[cmd.ref] = commit.id
        self.last_commit = commit.id
        if cmd.mark:
            self.markers[cmd.mark] = commit.id

    def progress_handler(self, cmd):
        """Process a ProgressCommand."""
        pass

    def _reset_base(self, commit_id):
        if self.last_commit == commit_id:
            return
        self._contents = {}
        self.last_commit = commit_id
        if commit_id != ZERO_SHA:
            tree_id = self.repo[commit_id].tree
            for (
                path,
                mode,
                hexsha,
            ) in iter_tree_contents(self.repo.object_store, tree_id):
                self._contents[path] = (mode, hexsha)

    def reset_handler(self, cmd):
        """Process a ResetCommand."""
        if cmd.from_ is None:
            from_ = ZERO_SHA
        else:
            from_ = self.lookup_object(cmd.from_)
        self._reset_base(from_)
        self.repo.refs[cmd.ref] = from_

    def tag_handler(self, cmd):
        """Process a TagCommand."""
        tag = Tag()
        tag.tagger = cmd.tagger
        tag.message = cmd.message
        tag.name = cmd.tag
        self.repo.add_object(tag)
        self.repo.refs["refs/tags/" + tag.name] = tag.id

    def feature_handler(self, cmd):
        """Process a FeatureCommand."""
        raise fastimport_errors.UnknownFeature(cmd.feature_name)
