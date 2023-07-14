# test_web.py -- Compatibility tests for the git web server.
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

"""Compatibility tests between Dulwich and the cgit HTTP server.

warning: these tests should be fairly stable, but when writing/debugging new
    tests, deadlocks may freeze the test process such that it cannot be
    Ctrl-C'ed. On POSIX systems, you can kill the tests with Ctrl-Z, "kill %".
"""

import sys
import threading
from typing import Tuple
from wsgiref import simple_server

from dulwich.tests import SkipTest, skipIf

from ...server import DictBackend, ReceivePackHandler, UploadPackHandler
from ...web import (HTTPGitApplication, WSGIRequestHandlerLogger,
                    WSGIServerLogger, make_wsgi_chain)
from .server_utils import NoSideBand64kReceivePackHandler, ServerTests
from .utils import CompatTestCase


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class WebTests(ServerTests):
    """Base tests for web server tests.

    Contains utility and setUp/tearDown methods, but does non inherit from
    TestCase so tests are not automatically run.
    """

    protocol = "http"

    def _start_server(self, repo):
        backend = DictBackend({"/": repo})
        app = self._make_app(backend)
        dul_server = simple_server.make_server(
            "localhost",
            0,
            app,
            server_class=WSGIServerLogger,
            handler_class=WSGIRequestHandlerLogger,
        )
        self.addCleanup(dul_server.shutdown)
        self.addCleanup(dul_server.server_close)
        threading.Thread(target=dul_server.serve_forever).start()
        self._server = dul_server
        _, port = dul_server.socket.getsockname()
        return port


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class SmartWebTestCase(WebTests, CompatTestCase):
    """Test cases for smart HTTP server.

    This server test case does not use side-band-64k in git-receive-pack.
    """

    min_git_version: Tuple[int, ...] = (1, 6, 6)

    def _handlers(self):
        return {b"git-receive-pack": NoSideBand64kReceivePackHandler}

    def _check_app(self, app):
        receive_pack_handler_cls = app.handlers[b"git-receive-pack"]
        caps = receive_pack_handler_cls.capabilities()
        self.assertNotIn(b"side-band-64k", caps)

    def _make_app(self, backend):
        app = make_wsgi_chain(backend, handlers=self._handlers())
        to_check = app
        # peel back layers until we're at the base application
        while not issubclass(to_check.__class__, HTTPGitApplication):
            to_check = to_check.app
        self._check_app(to_check)
        return app


def patch_capabilities(handler, caps_removed):
    # Patch a handler's capabilities by specifying a list of them to be
    # removed, and return the original classmethod for restoration.
    original_capabilities = handler.capabilities
    filtered_capabilities = [
        i for i in original_capabilities() if i not in caps_removed
    ]

    def capabilities(cls):
        return filtered_capabilities

    handler.capabilities = classmethod(capabilities)
    return original_capabilities


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class SmartWebSideBand64kTestCase(SmartWebTestCase):
    """Test cases for smart HTTP server with side-band-64k support."""

    # side-band-64k in git-receive-pack was introduced in git 1.7.0.2
    min_git_version = (1, 7, 0, 2)

    def setUp(self):
        self.o_uph_cap = patch_capabilities(UploadPackHandler, (b"no-done",))
        self.o_rph_cap = patch_capabilities(ReceivePackHandler, (b"no-done",))
        super().setUp()

    def tearDown(self):
        super().tearDown()
        UploadPackHandler.capabilities = self.o_uph_cap
        ReceivePackHandler.capabilities = self.o_rph_cap

    def _handlers(self):
        return None  # default handlers include side-band-64k

    def _check_app(self, app):
        receive_pack_handler_cls = app.handlers[b"git-receive-pack"]
        caps = receive_pack_handler_cls.capabilities()
        self.assertIn(b"side-band-64k", caps)
        self.assertNotIn(b"no-done", caps)


class SmartWebSideBand64kNoDoneTestCase(SmartWebTestCase):
    """Test cases for smart HTTP server with side-band-64k and no-done
    support.
    """

    # no-done was introduced in git 1.7.4
    min_git_version = (1, 7, 4)

    def _handlers(self):
        return None  # default handlers include side-band-64k

    def _check_app(self, app):
        receive_pack_handler_cls = app.handlers[b"git-receive-pack"]
        caps = receive_pack_handler_cls.capabilities()
        self.assertIn(b"side-band-64k", caps)
        self.assertIn(b"no-done", caps)


@skipIf(sys.platform == "win32", "Broken on windows, with very long fail time.")
class DumbWebTestCase(WebTests, CompatTestCase):
    """Test cases for dumb HTTP server."""

    def _make_app(self, backend):
        return make_wsgi_chain(backend, dumb=True)

    def test_push_to_dulwich(self):
        # Note: remove this if dulwich implements dumb web pushing.
        raise SkipTest("Dumb web pushing not supported.")

    def test_push_to_dulwich_remove_branch(self):
        # Note: remove this if dumb pushing is supported
        raise SkipTest("Dumb web pushing not supported.")

    def test_new_shallow_clone_from_dulwich(self):
        # Note: remove this if C git and dulwich implement dumb web shallow
        # clones.
        raise SkipTest("Dumb web shallow cloning not supported.")

    def test_shallow_clone_from_git_is_identical(self):
        # Note: remove this if C git and dulwich implement dumb web shallow
        # clones.
        raise SkipTest("Dumb web shallow cloning not supported.")

    def test_fetch_same_depth_into_shallow_clone_from_dulwich(self):
        # Note: remove this if C git and dulwich implement dumb web shallow
        # clones.
        raise SkipTest("Dumb web shallow cloning not supported.")

    def test_fetch_full_depth_into_shallow_clone_from_dulwich(self):
        # Note: remove this if C git and dulwich implement dumb web shallow
        # clones.
        raise SkipTest("Dumb web shallow cloning not supported.")

    def test_push_to_dulwich_issue_88_standard(self):
        raise SkipTest("Dumb web pushing not supported.")
