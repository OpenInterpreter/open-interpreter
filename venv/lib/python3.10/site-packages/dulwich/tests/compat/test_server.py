# test_server.py -- Compatibility tests for git server.
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

"""Compatibility tests between Dulwich and the cgit server.

Warning: these tests should be fairly stable, but when writing/debugging new
    tests, deadlocks may freeze the test process such that it cannot be
    Ctrl-C'ed. On POSIX systems, you can kill the tests with Ctrl-Z, "kill %".
"""

import os
import sys
import threading

from dulwich.tests import skipIf

from ...server import DictBackend, TCPGitServer
from .server_utils import NoSideBand64kReceivePackHandler, ServerTests
from .utils import CompatTestCase, require_git_version


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class GitServerTestCase(ServerTests, CompatTestCase):
    """Tests for client/server compatibility.

    This server test case does not use side-band-64k in git-receive-pack.
    """

    protocol = "git"

    def _handlers(self):
        return {b"git-receive-pack": NoSideBand64kReceivePackHandler}

    def _check_server(self, dul_server):
        receive_pack_handler_cls = dul_server.handlers[b"git-receive-pack"]
        caps = receive_pack_handler_cls.capabilities()
        self.assertNotIn(b"side-band-64k", caps)

    def _start_server(self, repo):
        backend = DictBackend({b"/": repo})
        dul_server = TCPGitServer(backend, b"localhost", 0, handlers=self._handlers())
        self._check_server(dul_server)
        self.addCleanup(dul_server.shutdown)
        self.addCleanup(dul_server.server_close)
        threading.Thread(target=dul_server.serve).start()
        self._server = dul_server
        _, port = self._server.socket.getsockname()
        return port


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class GitServerSideBand64kTestCase(GitServerTestCase):
    """Tests for client/server compatibility with side-band-64k support."""

    # side-band-64k in git-receive-pack was introduced in git 1.7.0.2
    min_git_version = (1, 7, 0, 2)

    def setUp(self):
        super().setUp()
        # side-band-64k is broken in the windows client.
        # https://github.com/msysgit/git/issues/101
        # Fix has landed for the 1.9.3 release.
        if os.name == "nt":
            require_git_version((1, 9, 3))

    def _handlers(self):
        return None  # default handlers include side-band-64k

    def _check_server(self, server):
        receive_pack_handler_cls = server.handlers[b"git-receive-pack"]
        caps = receive_pack_handler_cls.capabilities()
        self.assertIn(b"side-band-64k", caps)
