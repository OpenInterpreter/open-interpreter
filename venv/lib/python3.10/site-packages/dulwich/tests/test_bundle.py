# test_bundle.py -- tests for bundle
# Copyright (C) 2020 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for bundle support."""

import os
import tempfile
from io import BytesIO

from dulwich.tests import TestCase

from ..bundle import Bundle, read_bundle, write_bundle
from ..pack import PackData, write_pack_objects


class BundleTests(TestCase):
    def test_roundtrip_bundle(self):
        origbundle = Bundle()
        origbundle.version = 3
        origbundle.capabilities = {"foo": None}
        origbundle.references = {b"refs/heads/master": b"ab" * 20}
        origbundle.prerequisites = [(b"cc" * 20, "comment")]
        b = BytesIO()
        write_pack_objects(b.write, [])
        b.seek(0)
        origbundle.pack_data = PackData.from_file(b)
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "foo"), "wb") as f:
                write_bundle(f, origbundle)

            with open(os.path.join(td, "foo"), "rb") as f:
                newbundle = read_bundle(f)

                self.assertEqual(origbundle, newbundle)
