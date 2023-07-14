# test_patch.py -- test patch compatibility with CGit
# Copyright (C) 2019 Boris Feld <boris@comet.ml>
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

"""Tests related to patch compatibility with CGit."""
import os
import shutil
import tempfile
from io import BytesIO

from dulwich import porcelain

from ...repo import Repo
from .utils import CompatTestCase, run_git_or_fail


class CompatPatchTestCase(CompatTestCase):
    def setUp(self):
        super().setUp()
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)
        self.repo_path = os.path.join(self.test_dir, "repo")
        self.repo = Repo.init(self.repo_path, mkdir=True)
        self.addCleanup(self.repo.close)

    def test_patch_apply(self):
        # Prepare the repository

        # Create some files and commit them
        file_list = ["to_exists", "to_modify", "to_delete"]
        for file in file_list:
            file_path = os.path.join(self.repo_path, file)

            # Touch the files
            with open(file_path, "w"):
                pass

        self.repo.stage(file_list)

        first_commit = self.repo.do_commit(b"The first commit")

        # Make a copy of the repository so we can apply the diff later
        copy_path = os.path.join(self.test_dir, "copy")
        shutil.copytree(self.repo_path, copy_path)

        # Do some changes
        with open(os.path.join(self.repo_path, "to_modify"), "w") as f:
            f.write("Modified!")

        os.remove(os.path.join(self.repo_path, "to_delete"))

        with open(os.path.join(self.repo_path, "to_add"), "w"):
            pass

        self.repo.stage(["to_modify", "to_delete", "to_add"])

        second_commit = self.repo.do_commit(b"The second commit")

        # Get the patch
        first_tree = self.repo[first_commit].tree
        second_tree = self.repo[second_commit].tree

        outstream = BytesIO()
        porcelain.diff_tree(
            self.repo.path, first_tree, second_tree, outstream=outstream
        )

        # Save it on disk
        patch_path = os.path.join(self.test_dir, "patch.patch")
        with open(patch_path, "wb") as patch:
            patch.write(outstream.getvalue())

        # And try to apply it to the copy directory
        git_command = ["-C", copy_path, "apply", patch_path]
        run_git_or_fail(git_command)

        # And now check that the files contents are exactly the same between
        # the two repositories
        original_files = set(os.listdir(self.repo_path))
        new_files = set(os.listdir(copy_path))

        # Check that we have the exact same files in both repositories
        self.assertEqual(original_files, new_files)

        for file in original_files:
            if file == ".git":
                continue

            original_file_path = os.path.join(self.repo_path, file)
            copy_file_path = os.path.join(copy_path, file)

            self.assertTrue(os.path.isfile(copy_file_path))

            with open(original_file_path, "rb") as original_file:
                original_content = original_file.read()

            with open(copy_file_path, "rb") as copy_file:
                copy_content = copy_file.read()

            self.assertEqual(original_content, copy_content)
