# test_greenthreads.py -- Unittests for eventlet.
# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Fabien Boucher <fabien.boucher@enovance.com>
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

import time

from dulwich.tests import TestCase, skipIf

from ..object_store import MemoryObjectStore
from ..objects import Blob, Commit, Tree, parse_timezone

try:
    import gevent  # noqa: F401

    gevent_support = True
except ImportError:
    gevent_support = False

if gevent_support:
    from ..greenthreads import GreenThreadsMissingObjectFinder

skipmsg = "Gevent library is not installed"


def create_commit(marker=None):
    blob = Blob.from_string(b"The blob content " + marker)
    tree = Tree()
    tree.add(b"thefile " + marker, 0o100644, blob.id)
    cmt = Commit()
    cmt.tree = tree.id
    cmt.author = cmt.committer = b"John Doe <john@doe.net>"
    cmt.message = marker
    tz = parse_timezone(b"-0200")[0]
    cmt.commit_time = cmt.author_time = int(time.time())
    cmt.commit_timezone = cmt.author_timezone = tz
    return cmt, tree, blob


def init_store(store, count=1):
    ret = []
    for i in range(0, count):
        objs = create_commit(marker=("%d" % i).encode("ascii"))
        for obj in objs:
            ret.append(obj)
            store.add_object(obj)
    return ret


@skipIf(not gevent_support, skipmsg)
class TestGreenThreadsMissingObjectFinder(TestCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryObjectStore()
        self.cmt_amount = 10
        self.objs = init_store(self.store, self.cmt_amount)

    def test_finder(self):
        wants = [sha.id for sha in self.objs if isinstance(sha, Commit)]
        finder = GreenThreadsMissingObjectFinder(self.store, (), wants)
        self.assertEqual(len(finder.sha_done), 0)
        self.assertEqual(len(finder.objects_to_send), self.cmt_amount)

        finder = GreenThreadsMissingObjectFinder(
            self.store, wants[0 : int(self.cmt_amount / 2)], wants
        )
        # sha_done will contains commit id and sha of blob referred in tree
        self.assertEqual(len(finder.sha_done), (self.cmt_amount / 2) * 2)
        self.assertEqual(len(finder.objects_to_send), self.cmt_amount / 2)
