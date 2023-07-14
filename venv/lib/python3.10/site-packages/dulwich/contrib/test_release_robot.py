# release_robot.py
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

"""Tests for release_robot."""

import datetime
import os
import re
import shutil
import tempfile
import time
import unittest

from dulwich.contrib import release_robot

from ..repo import Repo
from ..tests.utils import make_commit, make_tag

BASEDIR = os.path.abspath(os.path.dirname(__file__))  # this directory


def gmtime_to_datetime(gmt):
    return datetime.datetime(*time.gmtime(gmt)[:6])


class TagPatternTests(unittest.TestCase):
    """test tag patterns"""

    def test_tag_pattern(self):
        """test tag patterns"""
        test_cases = {
            "0.3": "0.3",
            "v0.3": "0.3",
            "release0.3": "0.3",
            "Release-0.3": "0.3",
            "v0.3rc1": "0.3rc1",
            "v0.3-rc1": "0.3-rc1",
            "v0.3-rc.1": "0.3-rc.1",
            "version 0.3": "0.3",
            "version_0.3_rc_1": "0.3_rc_1",
            "v1": "1",
            "0.3rc1": "0.3rc1",
        }
        for testcase, version in test_cases.items():
            matches = re.match(release_robot.PATTERN, testcase)
            self.assertEqual(matches.group(1), version)


class GetRecentTagsTest(unittest.TestCase):
    """test get recent tags"""

    # Git repo for dulwich project
    test_repo = os.path.join(BASEDIR, "dulwich_test_repo.zip")
    committer = b"Mark Mikofski <mark.mikofski@sunpowercorp.com>"
    test_tags = [b"v0.1a", b"v0.1"]
    tag_test_data = {
        test_tags[0]: [1484788003, b"3" * 40, None],
        test_tags[1]: [1484788314, b"1" * 40, (1484788401, b"2" * 40)],
    }

    @classmethod
    def setUpClass(cls):
        cls.projdir = tempfile.mkdtemp()  # temporary project directory
        cls.repo = Repo.init(cls.projdir)  # test repo
        obj_store = cls.repo.object_store  # test repo object store
        # commit 1 ('2017-01-19T01:06:43')
        cls.c1 = make_commit(
            id=cls.tag_test_data[cls.test_tags[0]][1],
            commit_time=cls.tag_test_data[cls.test_tags[0]][0],
            message=b"unannotated tag",
            author=cls.committer,
        )
        obj_store.add_object(cls.c1)
        # tag 1: unannotated
        cls.t1 = cls.test_tags[0]
        cls.repo[b"refs/tags/" + cls.t1] = cls.c1.id  # add unannotated tag
        # commit 2 ('2017-01-19T01:11:54')
        cls.c2 = make_commit(
            id=cls.tag_test_data[cls.test_tags[1]][1],
            commit_time=cls.tag_test_data[cls.test_tags[1]][0],
            message=b"annotated tag",
            parents=[cls.c1.id],
            author=cls.committer,
        )
        obj_store.add_object(cls.c2)
        # tag 2: annotated ('2017-01-19T01:13:21')
        cls.t2 = make_tag(
            cls.c2,
            id=cls.tag_test_data[cls.test_tags[1]][2][1],
            name=cls.test_tags[1],
            tag_time=cls.tag_test_data[cls.test_tags[1]][2][0],
        )
        obj_store.add_object(cls.t2)
        cls.repo[b"refs/heads/master"] = cls.c2.id
        cls.repo[b"refs/tags/" + cls.t2.name] = cls.t2.id  # add annotated tag

    @classmethod
    def tearDownClass(cls):
        cls.repo.close()
        shutil.rmtree(cls.projdir)

    def test_get_recent_tags(self):
        """test get recent tags"""
        tags = release_robot.get_recent_tags(self.projdir)  # get test tags
        for tag, metadata in tags:
            tag = tag.encode("utf-8")
            test_data = self.tag_test_data[tag]  # test data tag
            # test commit date, id and author name
            self.assertEqual(metadata[0], gmtime_to_datetime(test_data[0]))
            self.assertEqual(metadata[1].encode("utf-8"), test_data[1])
            self.assertEqual(metadata[2].encode("utf-8"), self.committer)
            # skip unannotated tags
            tag_obj = test_data[2]
            if not tag_obj:
                continue
            # tag date, id and name
            self.assertEqual(metadata[3][0], gmtime_to_datetime(tag_obj[0]))
            self.assertEqual(metadata[3][1].encode("utf-8"), tag_obj[1])
            self.assertEqual(metadata[3][2].encode("utf-8"), tag)
