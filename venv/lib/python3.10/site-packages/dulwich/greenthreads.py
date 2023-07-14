# greenthreads.py -- Utility module for querying an ObjectStore with gevent
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

"""Utility module for querying an ObjectStore with gevent."""

import gevent
from gevent import pool

from .object_store import (MissingObjectFinder, _collect_ancestors,
                           _collect_filetree_revs)
from .objects import Commit, Tag


def _split_commits_and_tags(obj_store, lst, *, ignore_unknown=False, pool=None):
    """Split object id list into two list with commit SHA1s and tag SHA1s.

    Same implementation as object_store._split_commits_and_tags
    except we use gevent to parallelize object retrieval.
    """
    commits = set()
    tags = set()

    def find_commit_type(sha):
        try:
            o = obj_store[sha]
        except KeyError:
            if not ignore_unknown:
                raise
        else:
            if isinstance(o, Commit):
                commits.add(sha)
            elif isinstance(o, Tag):
                tags.add(sha)
                commits.add(o.object[1])
            else:
                raise KeyError("Not a commit or a tag: %s" % sha)

    jobs = [pool.spawn(find_commit_type, s) for s in lst]
    gevent.joinall(jobs)
    return (commits, tags)


class GreenThreadsMissingObjectFinder(MissingObjectFinder):
    """Find the objects missing from another object store.

    Same implementation as object_store.MissingObjectFinder
    except we use gevent to parallelize object retrieval.
    """

    def __init__(
        self,
        object_store,
        haves,
        wants,
        progress=None,
        get_tagged=None,
        concurrency=1,
        get_parents=None,
    ):
        def collect_tree_sha(sha):
            self.sha_done.add(sha)
            cmt = object_store[sha]
            _collect_filetree_revs(object_store, cmt.tree, self.sha_done)

        self.object_store = object_store
        p = pool.Pool(size=concurrency)

        have_commits, have_tags = _split_commits_and_tags(object_store, haves, ignore_unknown=True, pool=p)
        want_commits, want_tags = _split_commits_and_tags(object_store, wants, ignore_unknown=False, pool=p)
        all_ancestors = _collect_ancestors(object_store, have_commits)[0]
        missing_commits, common_commits = _collect_ancestors(
            object_store, want_commits, all_ancestors
        )

        self.sha_done = set()
        jobs = [p.spawn(collect_tree_sha, c) for c in common_commits]
        gevent.joinall(jobs)
        for t in have_tags:
            self.sha_done.add(t)
        missing_tags = want_tags.difference(have_tags)
        wants = missing_commits.union(missing_tags)
        self.objects_to_send = {(w, None, False) for w in wants}
        if progress is None:
            self.progress = lambda x: None
        else:
            self.progress = progress
        self._tagged = get_tagged and get_tagged() or {}
