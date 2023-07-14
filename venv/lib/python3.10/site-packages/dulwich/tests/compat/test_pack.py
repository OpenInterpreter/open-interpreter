# test_pack.py -- Compatibility tests for git packs.
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

"""Compatibility tests for git packs."""


import binascii
import os
import re
import shutil
import tempfile

from dulwich.tests import SkipTest

from ...objects import Blob
from ...pack import write_pack
from ..test_pack import PackTests, a_sha, pack1_sha
from .utils import require_git_version, run_git_or_fail

_NON_DELTA_RE = re.compile(b"non delta: (?P<non_delta>\\d+) objects")


def _git_verify_pack_object_list(output):
    pack_shas = set()
    for line in output.splitlines():
        sha = line[:40]
        try:
            binascii.unhexlify(sha)
        except (TypeError, binascii.Error):
            continue  # non-sha line
        pack_shas.add(sha)
    return pack_shas


class TestPack(PackTests):
    """Compatibility tests for reading and writing pack files."""

    def setUp(self):
        require_git_version((1, 5, 0))
        super().setUp()
        self._tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tempdir)

    def test_copy(self):
        with self.get_pack(pack1_sha) as origpack:
            self.assertSucceeds(origpack.index.check)
            pack_path = os.path.join(self._tempdir, "Elch")
            write_pack(pack_path, origpack.pack_tuples())
            output = run_git_or_fail(["verify-pack", "-v", pack_path])
            orig_shas = {o.id for o in origpack.iterobjects()}
            self.assertEqual(orig_shas, _git_verify_pack_object_list(output))

    def test_deltas_work(self):
        with self.get_pack(pack1_sha) as orig_pack:
            orig_blob = orig_pack[a_sha]
            new_blob = Blob()
            new_blob.data = orig_blob.data + b"x"
            all_to_pack = [(o, None) for o in orig_pack.iterobjects()] + [(new_blob, None)]
        pack_path = os.path.join(self._tempdir, "pack_with_deltas")
        write_pack(pack_path, all_to_pack, deltify=True)
        output = run_git_or_fail(["verify-pack", "-v", pack_path])
        self.assertEqual(
            {x[0].id for x in all_to_pack},
            _git_verify_pack_object_list(output),
        )
        # We specifically made a new blob that should be a delta
        # against the blob a_sha, so make sure we really got only 3
        # non-delta objects:
        got_non_delta = int(_NON_DELTA_RE.search(output).group("non_delta"))
        self.assertEqual(
            3,
            got_non_delta,
            "Expected 3 non-delta objects, got %d" % got_non_delta,
        )

    def test_delta_medium_object(self):
        # This tests an object set that will have a copy operation
        # 2**20 in size.
        with self.get_pack(pack1_sha) as orig_pack:
            orig_blob = orig_pack[a_sha]
            new_blob = Blob()
            new_blob.data = orig_blob.data + (b"x" * 2 ** 20)
            new_blob_2 = Blob()
            new_blob_2.data = new_blob.data + b"y"
            all_to_pack = list(orig_pack.pack_tuples()) + [
                (new_blob, None),
                (new_blob_2, None),
            ]
            pack_path = os.path.join(self._tempdir, "pack_with_deltas")
            write_pack(pack_path, all_to_pack, deltify=True)
        output = run_git_or_fail(["verify-pack", "-v", pack_path])
        self.assertEqual(
            {x[0].id for x in all_to_pack},
            _git_verify_pack_object_list(output),
        )
        # We specifically made a new blob that should be a delta
        # against the blob a_sha, so make sure we really got only 3
        # non-delta objects:
        got_non_delta = int(_NON_DELTA_RE.search(output).group("non_delta"))
        self.assertEqual(
            3,
            got_non_delta,
            "Expected 3 non-delta objects, got %d" % got_non_delta,
        )
        # We expect one object to have a delta chain length of two
        # (new_blob_2), so let's verify that actually happens:
        self.assertIn(b"chain length = 2", output)

    # This test is SUPER slow: over 80 seconds on a 2012-era
    # laptop. This is because SequenceMatcher is worst-case quadratic
    # on the input size. It's impractical to produce deltas for
    # objects this large, but it's still worth doing the right thing
    # when it happens.
    def test_delta_large_object(self):
        # This tests an object set that will have a copy operation
        # 2**25 in size. This is a copy large enough that it requires
        # two copy operations in git's binary delta format.
        raise SkipTest("skipping slow, large test")
        with self.get_pack(pack1_sha) as orig_pack:
            new_blob = Blob()
            new_blob.data = "big blob" + ("x" * 2 ** 25)
            new_blob_2 = Blob()
            new_blob_2.data = new_blob.data + "y"
            all_to_pack = list(orig_pack.pack_tuples()) + [
                (new_blob, None),
                (new_blob_2, None),
            ]
            pack_path = os.path.join(self._tempdir, "pack_with_deltas")
            write_pack(pack_path, all_to_pack, deltify=True)
        output = run_git_or_fail(["verify-pack", "-v", pack_path])
        self.assertEqual(
            {x[0].id for x in all_to_pack},
            _git_verify_pack_object_list(output),
        )
        # We specifically made a new blob that should be a delta
        # against the blob a_sha, so make sure we really got only 4
        # non-delta objects:
        got_non_delta = int(_NON_DELTA_RE.search(output).group("non_delta"))
        self.assertEqual(
            4,
            got_non_delta,
            "Expected 4 non-delta objects, got %d" % got_non_delta,
        )
