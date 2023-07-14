# test_client.py -- Tests for the git protocol, client side
# Copyright (C) 2009 Jelmer Vernooij <jelmer@jelmer.uk>
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

import base64
import os
import shutil
import sys
import tempfile
import warnings
from io import BytesIO
from unittest.mock import patch
from urllib.parse import quote as urlquote
from urllib.parse import urlparse

import dulwich
from dulwich import client
from dulwich.tests import TestCase, skipIf

from ..client import (FetchPackResult, GitProtocolError, HangupException,
                      HttpGitClient, InvalidWants, LocalGitClient,
                      PLinkSSHVendor, ReportStatusParser, SendPackError,
                      SSHGitClient, StrangeHostname, SubprocessSSHVendor,
                      TCPGitClient, TraditionalGitClient,
                      _remote_error_from_stderr, check_wants,
                      default_urllib3_manager, get_credentials_from_store,
                      get_transport_and_path, get_transport_and_path_from_url,
                      parse_rsync_url)
from ..config import ConfigDict
from ..objects import Commit, Tree
from ..pack import pack_objects_to_data, write_pack_data, write_pack_objects
from ..protocol import TCP_GIT_PORT, Protocol
from ..repo import MemoryRepo, Repo
from .utils import open_repo, setup_warning_catcher, tear_down_repo


class DummyClient(TraditionalGitClient):
    def __init__(self, can_read, read, write):
        self.can_read = can_read
        self.read = read
        self.write = write
        TraditionalGitClient.__init__(self)

    def _connect(self, service, path):
        return Protocol(self.read, self.write), self.can_read, None


class DummyPopen:
    def __init__(self, *args, **kwards):
        self.stdin = BytesIO(b"stdin")
        self.stdout = BytesIO(b"stdout")
        self.stderr = BytesIO(b"stderr")
        self.returncode = 0
        self.args = args
        self.kwargs = kwards

    def communicate(self, *args, **kwards):
        return ("Running", "")

    def wait(self, *args, **kwards):
        return False


# TODO(durin42): add unit-level tests of GitClient
class GitClientTests(TestCase):
    def setUp(self):
        super().setUp()
        self.rout = BytesIO()
        self.rin = BytesIO()
        self.client = DummyClient(lambda x: True, self.rin.read, self.rout.write)

    def test_caps(self):
        agent_cap = ("agent=dulwich/%d.%d.%d" % dulwich.__version__).encode("ascii")
        self.assertEqual(
            {
                b"multi_ack",
                b"side-band-64k",
                b"ofs-delta",
                b"thin-pack",
                b"multi_ack_detailed",
                b"shallow",
                agent_cap,
            },
            set(self.client._fetch_capabilities),
        )
        self.assertEqual(
            {
                b"delete-refs",
                b"ofs-delta",
                b"report-status",
                b"side-band-64k",
                agent_cap,
            },
            set(self.client._send_capabilities),
        )

    def test_archive_ack(self):
        self.rin.write(b"0009NACK\n" b"0000")
        self.rin.seek(0)
        self.client.archive(b"bla", b"HEAD", None, None)
        self.assertEqual(self.rout.getvalue(), b"0011argument HEAD0000")

    def test_fetch_empty(self):
        self.rin.write(b"0000")
        self.rin.seek(0)

        def check_heads(heads, **kwargs):
            self.assertEqual(heads, {})
            return []

        ret = self.client.fetch_pack(b"/", check_heads, None, None)
        self.assertEqual({}, ret.refs)
        self.assertEqual({}, ret.symrefs)

    def test_fetch_pack_ignores_magic_ref(self):
        self.rin.write(
            b"00000000000000000000000000000000000000000000 capabilities^{}"
            b"\x00 multi_ack "
            b"thin-pack side-band side-band-64k ofs-delta shallow no-progress "
            b"include-tag\n"
            b"0000"
        )
        self.rin.seek(0)

        def check_heads(heads, **kwargs):
            self.assertEqual({}, heads)
            return []

        ret = self.client.fetch_pack(b"bla", check_heads, None, None, None)
        self.assertEqual({}, ret.refs)
        self.assertEqual({}, ret.symrefs)
        self.assertEqual(self.rout.getvalue(), b"0000")

    def test_fetch_pack_none(self):
        self.rin.write(
            b"008855dcc6bf963f922e1ed5c4bbaaefcfacef57b1d7 HEAD\x00multi_ack "
            b"thin-pack side-band side-band-64k ofs-delta shallow no-progress "
            b"include-tag\n"
            b"0000"
        )
        self.rin.seek(0)
        ret = self.client.fetch_pack(b"bla", lambda heads, **kwargs: [], None, None, None)
        self.assertEqual(
            {b"HEAD": b"55dcc6bf963f922e1ed5c4bbaaefcfacef57b1d7"}, ret.refs
        )
        self.assertEqual({}, ret.symrefs)
        self.assertEqual(self.rout.getvalue(), b"0000")

    def test_send_pack_no_sideband64k_with_update_ref_error(self) -> None:
        # No side-bank-64k reported by server shouldn't try to parse
        # side band data
        pkts = [
            b"55dcc6bf963f922e1ed5c4bbaaefcfacef57b1d7 capabilities^{}"
            b"\x00 report-status delete-refs ofs-delta\n",
            b"",
            b"unpack ok",
            b"ng refs/foo/bar pre-receive hook declined",
            b"",
        ]
        for pkt in pkts:
            if pkt == b"":
                self.rin.write(b"0000")
            else:
                self.rin.write(("%04x" % (len(pkt) + 4)).encode("ascii") + pkt)
        self.rin.seek(0)

        tree = Tree()
        commit = Commit()
        commit.tree = tree
        commit.parents = []
        commit.author = commit.committer = b"test user"
        commit.commit_time = commit.author_time = 1174773719
        commit.commit_timezone = commit.author_timezone = 0
        commit.encoding = b"UTF-8"
        commit.message = b"test message"

        def update_refs(refs):
            return {
                b"refs/foo/bar": commit.id,
            }

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return pack_objects_to_data(
                [
                    (commit, None),
                    (tree, b""),
                ]
            )

        result = self.client.send_pack("blah", update_refs, generate_pack_data)
        self.assertEqual(
            {b"refs/foo/bar": "pre-receive hook declined"}, result.ref_status
        )
        self.assertEqual({b"refs/foo/bar": commit.id}, result.refs)

    def test_send_pack_none(self):
        # Set ref to current value
        self.rin.write(
            b"0078310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/master\x00 report-status delete-refs "
            b"side-band-64k quiet ofs-delta\n"
            b"0000"
        )
        self.rin.seek(0)

        def update_refs(refs):
            return {b"refs/heads/master": b"310ca9477129b8586fa2afc779c1f57cf64bba6c"}

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return 0, []

        self.client.send_pack(b"/", update_refs, generate_pack_data)
        self.assertEqual(self.rout.getvalue(), b"0000")

    def test_send_pack_keep_and_delete(self):
        self.rin.write(
            b"0063310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/master\x00report-status delete-refs ofs-delta\n"
            b"003f310ca9477129b8586fa2afc779c1f57cf64bba6c refs/heads/keepme\n"
            b"0000000eunpack ok\n"
            b"0019ok refs/heads/master\n"
            b"0000"
        )
        self.rin.seek(0)

        def update_refs(refs):
            return {b"refs/heads/master": b"0" * 40}

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return 0, []

        self.client.send_pack(b"/", update_refs, generate_pack_data)
        self.assertEqual(
            self.rout.getvalue(),
            b"008b310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"0000000000000000000000000000000000000000 "
            b"refs/heads/master\x00delete-refs ofs-delta report-status0000",
        )

    def test_send_pack_delete_only(self):
        self.rin.write(
            b"0063310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/master\x00report-status delete-refs ofs-delta\n"
            b"0000000eunpack ok\n"
            b"0019ok refs/heads/master\n"
            b"0000"
        )
        self.rin.seek(0)

        def update_refs(refs):
            return {b"refs/heads/master": b"0" * 40}

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return 0, []

        self.client.send_pack(b"/", update_refs, generate_pack_data)
        self.assertEqual(
            self.rout.getvalue(),
            b"008b310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"0000000000000000000000000000000000000000 "
            b"refs/heads/master\x00delete-refs ofs-delta report-status0000",
        )

    def test_send_pack_new_ref_only(self):
        self.rin.write(
            b"0063310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/master\x00report-status delete-refs ofs-delta\n"
            b"0000000eunpack ok\n"
            b"0019ok refs/heads/blah12\n"
            b"0000"
        )
        self.rin.seek(0)

        def update_refs(refs):
            return {
                b"refs/heads/blah12": b"310ca9477129b8586fa2afc779c1f57cf64bba6c",
                b"refs/heads/master": b"310ca9477129b8586fa2afc779c1f57cf64bba6c",
            }

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return 0, []

        f = BytesIO()
        write_pack_objects(f.write, [])
        self.client.send_pack("/", update_refs, generate_pack_data)
        self.assertEqual(
            self.rout.getvalue(),
            b"008b0000000000000000000000000000000000000000 "
            b"310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/blah12\x00delete-refs ofs-delta report-status0000"
            + f.getvalue(),
        )

    def test_send_pack_new_ref(self):
        self.rin.write(
            b"0064310ca9477129b8586fa2afc779c1f57cf64bba6c "
            b"refs/heads/master\x00 report-status delete-refs ofs-delta\n"
            b"0000000eunpack ok\n"
            b"0019ok refs/heads/blah12\n"
            b"0000"
        )
        self.rin.seek(0)

        tree = Tree()
        commit = Commit()
        commit.tree = tree
        commit.parents = []
        commit.author = commit.committer = b"test user"
        commit.commit_time = commit.author_time = 1174773719
        commit.commit_timezone = commit.author_timezone = 0
        commit.encoding = b"UTF-8"
        commit.message = b"test message"

        def update_refs(refs):
            return {
                b"refs/heads/blah12": commit.id,
                b"refs/heads/master": b"310ca9477129b8586fa2afc779c1f57cf64bba6c",
            }

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return pack_objects_to_data(
                [
                    (commit, None),
                    (tree, b""),
                ]
            )

        f = BytesIO()
        count, records = generate_pack_data(None, None)
        write_pack_data(f.write, records, num_records=count)
        self.client.send_pack(b"/", update_refs, generate_pack_data)
        self.assertEqual(
            self.rout.getvalue(),
            b"008b0000000000000000000000000000000000000000 "
            + commit.id
            + b" refs/heads/blah12\x00delete-refs ofs-delta report-status0000"
            + f.getvalue(),
        )

    def test_send_pack_no_deleteref_delete_only(self):
        pkts = [
            b"310ca9477129b8586fa2afc779c1f57cf64bba6c refs/heads/master"
            b"\x00 report-status ofs-delta\n",
            b"",
            b"",
        ]
        for pkt in pkts:
            if pkt == b"":
                self.rin.write(b"0000")
            else:
                self.rin.write(("%04x" % (len(pkt) + 4)).encode("ascii") + pkt)
        self.rin.seek(0)

        def update_refs(refs):
            return {b"refs/heads/master": b"0" * 40}

        def generate_pack_data(have, want, ofs_delta=False, progress=None):
            return 0, []

        result = self.client.send_pack(b"/", update_refs, generate_pack_data)
        self.assertEqual(
            result.ref_status,
            {b"refs/heads/master": "remote does not support deleting refs"},
        )
        self.assertEqual(
            result.refs,
            {b"refs/heads/master": b"310ca9477129b8586fa2afc779c1f57cf64bba6c"},
        )
        self.assertEqual(self.rout.getvalue(), b"0000")


class TestGetTransportAndPath(TestCase):
    def test_tcp(self):
        c, path = get_transport_and_path("git://foo.com/bar/baz")
        self.assertIsInstance(c, TCPGitClient)
        self.assertEqual("foo.com", c._host)
        self.assertEqual(TCP_GIT_PORT, c._port)
        self.assertEqual("/bar/baz", path)

    def test_tcp_port(self):
        c, path = get_transport_and_path("git://foo.com:1234/bar/baz")
        self.assertIsInstance(c, TCPGitClient)
        self.assertEqual("foo.com", c._host)
        self.assertEqual(1234, c._port)
        self.assertEqual("/bar/baz", path)

    def test_git_ssh_explicit(self):
        c, path = get_transport_and_path("git+ssh://foo.com/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_explicit(self):
        c, path = get_transport_and_path("ssh://foo.com/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_port_explicit(self):
        c, path = get_transport_and_path("git+ssh://foo.com:1234/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(1234, c.port)
        self.assertEqual("/bar/baz", path)

    def test_username_and_port_explicit_unknown_scheme(self):
        c, path = get_transport_and_path("unknown://git@server:7999/dply/stuff.git")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("unknown", c.host)
        self.assertEqual("//git@server:7999/dply/stuff.git", path)

    def test_username_and_port_explicit(self):
        c, path = get_transport_and_path("ssh://git@server:7999/dply/stuff.git")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("git", c.username)
        self.assertEqual("server", c.host)
        self.assertEqual(7999, c.port)
        self.assertEqual("/dply/stuff.git", path)

    def test_ssh_abspath_doubleslash(self):
        c, path = get_transport_and_path("git+ssh://foo.com//bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("//bar/baz", path)

    def test_ssh_port(self):
        c, path = get_transport_and_path("git+ssh://foo.com:1234/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(1234, c.port)
        self.assertEqual("/bar/baz", path)

    def test_ssh_implicit(self):
        c, path = get_transport_and_path("foo:/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_host(self):
        c, path = get_transport_and_path("foo.com:/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_user_host(self):
        c, path = get_transport_and_path("user@foo.com:/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual("user", c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_relpath(self):
        c, path = get_transport_and_path("foo:bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("bar/baz", path)

    def test_ssh_host_relpath(self):
        c, path = get_transport_and_path("foo.com:bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("bar/baz", path)

    def test_ssh_user_host_relpath(self):
        c, path = get_transport_and_path("user@foo.com:bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual("user", c.username)
        self.assertEqual("bar/baz", path)

    def test_local(self):
        c, path = get_transport_and_path("foo.bar/baz")
        self.assertIsInstance(c, LocalGitClient)
        self.assertEqual("foo.bar/baz", path)

    @skipIf(sys.platform != "win32", "Behaviour only happens on windows.")
    def test_local_abs_windows_path(self):
        c, path = get_transport_and_path("C:\\foo.bar\\baz")
        self.assertIsInstance(c, LocalGitClient)
        self.assertEqual("C:\\foo.bar\\baz", path)

    def test_error(self):
        # Need to use a known urlparse.uses_netloc URL scheme to get the
        # expected parsing of the URL on Python versions less than 2.6.5
        c, path = get_transport_and_path("prospero://bar/baz")
        self.assertIsInstance(c, SSHGitClient)

    def test_http(self):
        url = "https://github.com/jelmer/dulwich"
        c, path = get_transport_and_path(url)
        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)

    def test_http_auth(self):
        url = "https://user:passwd@github.com/jelmer/dulwich"

        c, path = get_transport_and_path(url)

        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)
        self.assertEqual("user", c._username)
        self.assertEqual("passwd", c._password)

    def test_http_auth_with_username(self):
        url = "https://github.com/jelmer/dulwich"

        c, path = get_transport_and_path(url, username="user2", password="blah")

        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)
        self.assertEqual("user2", c._username)
        self.assertEqual("blah", c._password)

    def test_http_auth_with_username_and_in_url(self):
        url = "https://user:passwd@github.com/jelmer/dulwich"

        c, path = get_transport_and_path(url, username="user2", password="blah")

        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)
        self.assertEqual("user", c._username)
        self.assertEqual("passwd", c._password)

    def test_http_no_auth(self):
        url = "https://github.com/jelmer/dulwich"

        c, path = get_transport_and_path(url)

        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)
        self.assertIs(None, c._username)
        self.assertIs(None, c._password)


class TestGetTransportAndPathFromUrl(TestCase):
    def test_tcp(self):
        c, path = get_transport_and_path_from_url("git://foo.com/bar/baz")
        self.assertIsInstance(c, TCPGitClient)
        self.assertEqual("foo.com", c._host)
        self.assertEqual(TCP_GIT_PORT, c._port)
        self.assertEqual("/bar/baz", path)

    def test_tcp_port(self):
        c, path = get_transport_and_path_from_url("git://foo.com:1234/bar/baz")
        self.assertIsInstance(c, TCPGitClient)
        self.assertEqual("foo.com", c._host)
        self.assertEqual(1234, c._port)
        self.assertEqual("/bar/baz", path)

    def test_ssh_explicit(self):
        c, path = get_transport_and_path_from_url("git+ssh://foo.com/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/bar/baz", path)

    def test_ssh_port_explicit(self):
        c, path = get_transport_and_path_from_url("git+ssh://foo.com:1234/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(1234, c.port)
        self.assertEqual("/bar/baz", path)

    def test_ssh_homepath(self):
        c, path = get_transport_and_path_from_url("git+ssh://foo.com/~/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(None, c.port)
        self.assertEqual(None, c.username)
        self.assertEqual("/~/bar/baz", path)

    def test_ssh_port_homepath(self):
        c, path = get_transport_and_path_from_url("git+ssh://foo.com:1234/~/bar/baz")
        self.assertIsInstance(c, SSHGitClient)
        self.assertEqual("foo.com", c.host)
        self.assertEqual(1234, c.port)
        self.assertEqual("/~/bar/baz", path)

    def test_ssh_host_relpath(self):
        self.assertRaises(
            ValueError, get_transport_and_path_from_url, "foo.com:bar/baz"
        )

    def test_ssh_user_host_relpath(self):
        self.assertRaises(
            ValueError, get_transport_and_path_from_url, "user@foo.com:bar/baz"
        )

    def test_local_path(self):
        self.assertRaises(ValueError, get_transport_and_path_from_url, "foo.bar/baz")

    def test_error(self):
        # Need to use a known urlparse.uses_netloc URL scheme to get the
        # expected parsing of the URL on Python versions less than 2.6.5
        self.assertRaises(
            ValueError, get_transport_and_path_from_url, "prospero://bar/baz"
        )

    def test_http(self):
        url = "https://github.com/jelmer/dulwich"
        c, path = get_transport_and_path_from_url(url)
        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("https://github.com", c.get_url(b"/"))
        self.assertEqual("/jelmer/dulwich", path)

    def test_http_port(self):
        url = "https://github.com:9090/jelmer/dulwich"
        c, path = get_transport_and_path_from_url(url)
        self.assertEqual("https://github.com:9090", c.get_url(b"/"))
        self.assertIsInstance(c, HttpGitClient)
        self.assertEqual("/jelmer/dulwich", path)

    @patch("os.name", "posix")
    @patch("sys.platform", "linux")
    def test_file(self):
        c, path = get_transport_and_path_from_url("file:///home/jelmer/foo")
        self.assertIsInstance(c, LocalGitClient)
        self.assertEqual("/home/jelmer/foo", path)

    @patch("os.name", "nt")
    @patch("sys.platform", "win32")
    def test_file_win(self):
        # `_win32_url_to_path` uses urllib.request.url2pathname, which is set to
        # `ntutl2path.url2pathname`  when `os.name==nt`
        from nturl2path import url2pathname

        with patch("dulwich.client.url2pathname", url2pathname):
            expected = "C:\\foo.bar\\baz"
            for file_url in [
                "file:C:/foo.bar/baz",
                "file:/C:/foo.bar/baz",
                "file://C:/foo.bar/baz",
                "file://C://foo.bar//baz",
                "file:///C:/foo.bar/baz",
            ]:
                c, path = get_transport_and_path(file_url)
                self.assertIsInstance(c, LocalGitClient)
                self.assertEqual(path, expected)

            for remote_url in [
                "file://host.example.com/C:/foo.bar/baz"
                "file://host.example.com/C:/foo.bar/baz"
                "file:////host.example/foo.bar/baz",
            ]:
                with self.assertRaises(NotImplementedError):
                    c, path = get_transport_and_path(remote_url)


class TestSSHVendor:
    def __init__(self):
        self.host = None
        self.command = ""
        self.username = None
        self.port = None
        self.password = None
        self.key_filename = None

    def run_command(
        self,
        host,
        command,
        username=None,
        port=None,
        password=None,
        key_filename=None,
        ssh_command=None,
    ):
        self.host = host
        self.command = command
        self.username = username
        self.port = port
        self.password = password
        self.key_filename = key_filename
        self.ssh_command = ssh_command

        class Subprocess:
            pass

        setattr(Subprocess, "read", lambda: None)
        setattr(Subprocess, "write", lambda: None)
        setattr(Subprocess, "close", lambda: None)
        setattr(Subprocess, "can_read", lambda: None)
        return Subprocess()


class SSHGitClientTests(TestCase):
    def setUp(self):
        super().setUp()

        self.server = TestSSHVendor()
        self.real_vendor = client.get_ssh_vendor
        client.get_ssh_vendor = lambda: self.server

        self.client = SSHGitClient("git.samba.org")

    def tearDown(self):
        super().tearDown()
        client.get_ssh_vendor = self.real_vendor

    def test_get_url(self):
        path = "/tmp/repo.git"
        c = SSHGitClient("git.samba.org")

        url = c.get_url(path)
        self.assertEqual("ssh://git.samba.org/tmp/repo.git", url)

    def test_get_url_with_username_and_port(self):
        path = "/tmp/repo.git"
        c = SSHGitClient("git.samba.org", port=2222, username="user")

        url = c.get_url(path)
        self.assertEqual("ssh://user@git.samba.org:2222/tmp/repo.git", url)

    def test_default_command(self):
        self.assertEqual(b"git-upload-pack", self.client._get_cmd_path(b"upload-pack"))

    def test_alternative_command_path(self):
        self.client.alternative_paths[b"upload-pack"] = b"/usr/lib/git/git-upload-pack"
        self.assertEqual(
            b"/usr/lib/git/git-upload-pack",
            self.client._get_cmd_path(b"upload-pack"),
        )

    def test_alternative_command_path_spaces(self):
        self.client.alternative_paths[
            b"upload-pack"
        ] = b"/usr/lib/git/git-upload-pack -ibla"
        self.assertEqual(
            b"/usr/lib/git/git-upload-pack -ibla",
            self.client._get_cmd_path(b"upload-pack"),
        )

    def test_connect(self):
        server = self.server
        client = self.client

        client.username = b"username"
        client.port = 1337

        client._connect(b"command", b"/path/to/repo")
        self.assertEqual(b"username", server.username)
        self.assertEqual(1337, server.port)
        self.assertEqual("git-command '/path/to/repo'", server.command)

        client._connect(b"relative-command", b"/~/path/to/repo")
        self.assertEqual("git-relative-command '~/path/to/repo'", server.command)

    def test_ssh_command_precedence(self):
        self.overrideEnv("GIT_SSH", "/path/to/ssh")
        test_client = SSHGitClient("git.samba.org")
        self.assertEqual(test_client.ssh_command, "/path/to/ssh")

        self.overrideEnv("GIT_SSH_COMMAND", "/path/to/ssh -o Option=Value")
        test_client = SSHGitClient("git.samba.org")
        self.assertEqual(test_client.ssh_command, "/path/to/ssh -o Option=Value")

        test_client = SSHGitClient("git.samba.org", ssh_command="ssh -o Option1=Value1")
        self.assertEqual(test_client.ssh_command, "ssh -o Option1=Value1")


class ReportStatusParserTests(TestCase):
    def test_invalid_pack(self):
        parser = ReportStatusParser()
        parser.handle_packet(b"unpack error - foo bar")
        parser.handle_packet(b"ok refs/foo/bar")
        parser.handle_packet(None)
        self.assertRaises(SendPackError, list, parser.check())

    def test_update_refs_error(self):
        parser = ReportStatusParser()
        parser.handle_packet(b"unpack ok")
        parser.handle_packet(b"ng refs/foo/bar need to pull")
        parser.handle_packet(None)
        self.assertEqual([(b"refs/foo/bar", "need to pull")], list(parser.check()))

    def test_ok(self):
        parser = ReportStatusParser()
        parser.handle_packet(b"unpack ok")
        parser.handle_packet(b"ok refs/foo/bar")
        parser.handle_packet(None)
        self.assertEqual([(b"refs/foo/bar", None)], list(parser.check()))


class LocalGitClientTests(TestCase):
    def test_get_url(self):
        path = "/tmp/repo.git"
        c = LocalGitClient()

        url = c.get_url(path)
        self.assertEqual("file:///tmp/repo.git", url)

    def test_fetch_into_empty(self):
        c = LocalGitClient()
        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        t = Repo.init_bare(target)
        self.addCleanup(t.close)
        s = open_repo("a.git")
        self.addCleanup(tear_down_repo, s)
        self.assertEqual(s.get_refs(), c.fetch(s.path, t).refs)

    def test_clone(self):
        c = LocalGitClient()
        s = open_repo("a.git")
        self.addCleanup(tear_down_repo, s)
        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        result_repo = c.clone(s.path, target, mkdir=False)
        self.addCleanup(result_repo.close)
        expected = dict(s.get_refs())
        expected[b'refs/remotes/origin/HEAD'] = expected[b'HEAD']
        expected[b'refs/remotes/origin/master'] = expected[b'refs/heads/master']
        self.assertEqual(expected, result_repo.get_refs())

    def test_fetch_empty(self):
        c = LocalGitClient()
        s = open_repo("a.git")
        self.addCleanup(tear_down_repo, s)
        out = BytesIO()
        walker = {}
        ret = c.fetch_pack(
            s.path, lambda heads, **kwargs: [], graph_walker=walker, pack_data=out.write
        )
        self.assertEqual(
            {
                b"HEAD": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/heads/master": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/tags/mytag": b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
                b"refs/tags/mytag-packed": b"b0931cadc54336e78a1d980420e3268903b57a50",
            },
            ret.refs,
        )
        self.assertEqual({b"HEAD": b"refs/heads/master"}, ret.symrefs)
        self.assertEqual(
            b"PACK\x00\x00\x00\x02\x00\x00\x00\x00\x02\x9d\x08"
            b"\x82;\xd8\xa8\xea\xb5\x10\xadj\xc7\\\x82<\xfd>\xd3\x1e",
            out.getvalue(),
        )

    def test_fetch_pack_none(self):
        c = LocalGitClient()
        s = open_repo("a.git")
        self.addCleanup(tear_down_repo, s)
        out = BytesIO()
        walker = MemoryRepo().get_graph_walker()
        ret = c.fetch_pack(
            s.path,
            lambda heads, **kwargs: [b"a90fa2d900a17e99b433217e988c4eb4a2e9a097"],
            graph_walker=walker,
            pack_data=out.write,
        )
        self.assertEqual({b"HEAD": b"refs/heads/master"}, ret.symrefs)
        self.assertEqual(
            {
                b"HEAD": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/heads/master": b"a90fa2d900a17e99b433217e988c4eb4a2e9a097",
                b"refs/tags/mytag": b"28237f4dc30d0d462658d6b937b08a0f0b6ef55a",
                b"refs/tags/mytag-packed": b"b0931cadc54336e78a1d980420e3268903b57a50",
            },
            ret.refs,
        )
        # Hardcoding is not ideal, but we'll fix that some other day..
        self.assertTrue(
            out.getvalue().startswith(b"PACK\x00\x00\x00\x02\x00\x00\x00\x07")
        )

    def test_send_pack_without_changes(self):
        local = open_repo("a.git")
        self.addCleanup(tear_down_repo, local)

        target = open_repo("a.git")
        self.addCleanup(tear_down_repo, target)

        self.send_and_verify(b"master", local, target)

    def test_send_pack_with_changes(self):
        local = open_repo("a.git")
        self.addCleanup(tear_down_repo, local)

        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        with Repo.init_bare(target_path) as target:
            self.send_and_verify(b"master", local, target)

    def test_get_refs(self):
        local = open_repo("refs.git")
        self.addCleanup(tear_down_repo, local)

        client = LocalGitClient()
        refs = client.get_refs(local.path)
        self.assertDictEqual(local.refs.as_dict(), refs)

    def send_and_verify(self, branch, local, target):
        """Send branch from local to remote repository and verify it worked."""
        client = LocalGitClient()
        ref_name = b"refs/heads/" + branch
        result = client.send_pack(
            target.path,
            lambda _: {ref_name: local.refs[ref_name]},
            local.generate_pack_data,
        )

        self.assertEqual(local.refs[ref_name], result.refs[ref_name])
        self.assertIs(None, result.agent)
        self.assertEqual({}, result.ref_status)

        obj_local = local.get_object(result.refs[ref_name])
        obj_target = target.get_object(result.refs[ref_name])
        self.assertEqual(obj_local, obj_target)


class HttpGitClientTests(TestCase):
    def test_get_url(self):
        base_url = "https://github.com/jelmer/dulwich"
        path = "/jelmer/dulwich"
        c = HttpGitClient(base_url)

        url = c.get_url(path)
        self.assertEqual("https://github.com/jelmer/dulwich", url)

    def test_get_url_bytes_path(self):
        base_url = "https://github.com/jelmer/dulwich"
        path_bytes = b"/jelmer/dulwich"
        c = HttpGitClient(base_url)

        url = c.get_url(path_bytes)
        self.assertEqual("https://github.com/jelmer/dulwich", url)

    def test_get_url_with_username_and_passwd(self):
        base_url = "https://github.com/jelmer/dulwich"
        path = "/jelmer/dulwich"
        c = HttpGitClient(base_url, username="USERNAME", password="PASSWD")

        url = c.get_url(path)
        self.assertEqual("https://github.com/jelmer/dulwich", url)

    def test_init_username_passwd_set(self):
        url = "https://github.com/jelmer/dulwich"

        c = HttpGitClient(url, config=None, username="user", password="passwd")
        self.assertEqual("user", c._username)
        self.assertEqual("passwd", c._password)

        basic_auth = c.pool_manager.headers["authorization"]
        auth_string = "{}:{}".format("user", "passwd")
        b64_credentials = base64.b64encode(auth_string.encode("latin1"))
        expected_basic_auth = "Basic %s" % b64_credentials.decode("latin1")
        self.assertEqual(basic_auth, expected_basic_auth)

    def test_init_username_set_no_password(self):
        url = "https://github.com/jelmer/dulwich"

        c = HttpGitClient(url, config=None, username="user")
        self.assertEqual("user", c._username)
        self.assertIsNone(c._password)

        basic_auth = c.pool_manager.headers["authorization"]
        auth_string = b"user:"
        b64_credentials = base64.b64encode(auth_string)
        expected_basic_auth = f"Basic {b64_credentials.decode('ascii')}"
        self.assertEqual(basic_auth, expected_basic_auth)

    def test_init_no_username_passwd(self):
        url = "https://github.com/jelmer/dulwich"

        c = HttpGitClient(url, config=None)
        self.assertIs(None, c._username)
        self.assertIs(None, c._password)
        self.assertNotIn("authorization", c.pool_manager.headers)

    def test_from_parsedurl_username_only(self):
        username = "user"
        url = f"https://{username}@github.com/jelmer/dulwich"

        c = HttpGitClient.from_parsedurl(urlparse(url))
        self.assertEqual(c._username, username)
        self.assertEqual(c._password, None)

        basic_auth = c.pool_manager.headers["authorization"]
        auth_string = username.encode('ascii') + b":"
        b64_credentials = base64.b64encode(auth_string)
        expected_basic_auth = f"Basic {b64_credentials.decode('ascii')}"
        self.assertEqual(basic_auth, expected_basic_auth)

    def test_from_parsedurl_on_url_with_quoted_credentials(self):
        original_username = "john|the|first"
        quoted_username = urlquote(original_username)

        original_password = "Ya#1$2%3"
        quoted_password = urlquote(original_password)

        url = "https://{username}:{password}@github.com/jelmer/dulwich".format(
            username=quoted_username, password=quoted_password
        )

        c = HttpGitClient.from_parsedurl(urlparse(url))
        self.assertEqual(original_username, c._username)
        self.assertEqual(original_password, c._password)

        basic_auth = c.pool_manager.headers["authorization"]
        auth_string = "{}:{}".format(original_username, original_password)
        b64_credentials = base64.b64encode(auth_string.encode("latin1"))
        expected_basic_auth = "Basic %s" % b64_credentials.decode("latin1")
        self.assertEqual(basic_auth, expected_basic_auth)

    def test_url_redirect_location(self):
        from urllib3.response import HTTPResponse

        test_data = {
            "https://gitlab.com/inkscape/inkscape/": {
                "location": "https://gitlab.com/inkscape/inkscape.git/",
                "redirect_url": "https://gitlab.com/inkscape/inkscape.git/",
                "refs_data": (
                    b"001e# service=git-upload-pack\n00000032"
                    b"fb2bebf4919a011f0fd7cec085443d0031228e76 "
                    b"HEAD\n0000"
                ),
            },
            "https://github.com/jelmer/dulwich/": {
                "location": "https://github.com/jelmer/dulwich/",
                "redirect_url": "https://github.com/jelmer/dulwich/",
                "refs_data": (
                    b"001e# service=git-upload-pack\n00000032"
                    b"3ff25e09724aa4d86ea5bca7d5dd0399a3c8bfcf "
                    b"HEAD\n0000"
                ),
            },
            # check for absolute-path URI reference as location
            "https://codeberg.org/ashwinvis/radicale-sh.git/": {
                "location": "/ashwinvis/radicale-auth-sh/",
                "redirect_url": "https://codeberg.org/ashwinvis/radicale-auth-sh/",
                "refs_data": (
                    b"001e# service=git-upload-pack\n00000032"
                    b"470f8603768b608fc988675de2fae8f963c21158 "
                    b"HEAD\n0000"
                ),
            },
        }

        tail = "info/refs?service=git-upload-pack"

        # we need to mock urllib3.PoolManager as this test will fail
        # otherwise without an active internet connection
        class PoolManagerMock:
            def __init__(self):
                self.headers = {}

            def request(self, method, url, fields=None, headers=None, redirect=True, preload_content=True):
                base_url = url[: -len(tail)]
                redirect_base_url = test_data[base_url]["location"]
                redirect_url = redirect_base_url + tail
                headers = {
                    "Content-Type": "application/x-git-upload-pack-advertisement"
                }
                body = test_data[base_url]["refs_data"]
                # urllib3 handles automatic redirection by default
                status = 200
                request_url = redirect_url
                # simulate urllib3 behavior when redirect parameter is False
                if redirect is False:
                    request_url = url
                    if redirect_base_url != base_url:
                        body = b""
                        headers["location"] = test_data[base_url]["location"]
                        status = 301

                return HTTPResponse(
                    body=BytesIO(body),
                    headers=headers,
                    request_method=method,
                    request_url=request_url,
                    preload_content=preload_content,
                    status=status,
                )

        pool_manager = PoolManagerMock()

        for base_url in test_data.keys():
            # instantiate HttpGitClient with mocked pool manager
            c = HttpGitClient(base_url, pool_manager=pool_manager, config=None)
            # call method that detects url redirection
            _, _, processed_url = c._discover_references(b"git-upload-pack", base_url)

            # send the same request as the method above without redirection
            resp = c.pool_manager.request("GET", base_url + tail, redirect=False)

            # check expected behavior of urllib3
            redirect_location = resp.get_redirect_location()

            if resp.status == 200:
                self.assertFalse(redirect_location)

            if redirect_location:
                # check that url redirection has been correctly detected
                self.assertEqual(processed_url, test_data[base_url]["redirect_url"])
            else:
                # check also the no redirection case
                self.assertEqual(processed_url, base_url)


class TCPGitClientTests(TestCase):
    def test_get_url(self):
        host = "github.com"
        path = "/jelmer/dulwich"
        c = TCPGitClient(host)

        url = c.get_url(path)
        self.assertEqual("git://github.com/jelmer/dulwich", url)

    def test_get_url_with_port(self):
        host = "github.com"
        path = "/jelmer/dulwich"
        port = 9090
        c = TCPGitClient(host, port=port)

        url = c.get_url(path)
        self.assertEqual("git://github.com:9090/jelmer/dulwich", url)


class DefaultUrllib3ManagerTest(TestCase):
    def test_no_config(self):
        manager = default_urllib3_manager(config=None)
        self.assertEqual(manager.connection_pool_kw["cert_reqs"], "CERT_REQUIRED")

    def test_config_no_proxy(self):
        import urllib3

        manager = default_urllib3_manager(config=ConfigDict())
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_config_no_proxy_custom_cls(self):
        import urllib3

        class CustomPoolManager(urllib3.PoolManager):
            pass

        manager = default_urllib3_manager(
            config=ConfigDict(), pool_manager_cls=CustomPoolManager
        )
        self.assertIsInstance(manager, CustomPoolManager)

    def test_config_ssl(self):
        config = ConfigDict()
        config.set(b"http", b"sslVerify", b"true")
        manager = default_urllib3_manager(config=config)
        self.assertEqual(manager.connection_pool_kw["cert_reqs"], "CERT_REQUIRED")

    def test_config_no_ssl(self):
        config = ConfigDict()
        config.set(b"http", b"sslVerify", b"false")
        manager = default_urllib3_manager(config=config)
        self.assertEqual(manager.connection_pool_kw["cert_reqs"], "CERT_NONE")

    def test_config_proxy(self):
        import urllib3

        config = ConfigDict()
        config.set(b"http", b"proxy", b"http://localhost:3128/")
        manager = default_urllib3_manager(config=config)

        self.assertIsInstance(manager, urllib3.ProxyManager)
        self.assertTrue(hasattr(manager, "proxy"))
        self.assertEqual(manager.proxy.scheme, "http")
        self.assertEqual(manager.proxy.host, "localhost")
        self.assertEqual(manager.proxy.port, 3128)

    def test_environment_proxy(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        manager = default_urllib3_manager(config=config)
        self.assertIsInstance(manager, urllib3.ProxyManager)
        self.assertTrue(hasattr(manager, "proxy"))
        self.assertEqual(manager.proxy.scheme, "http")
        self.assertEqual(manager.proxy.host, "myproxy")
        self.assertEqual(manager.proxy.port, 8080)

    def test_environment_empty_proxy(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "")
        manager = default_urllib3_manager(config=config)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_1(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh")
        base_url = "http://xyz.abc.def.gh:8080/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_2(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh,ample.com")
        base_url = "http://ample.com/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_3(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh,ample.com")
        base_url = "http://ample.com:80/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_4(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh,ample.com")
        base_url = "http://www.ample.com/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_5(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh,ample.com")
        base_url = "http://www.example.com/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertIsInstance(manager, urllib3.ProxyManager)
        self.assertTrue(hasattr(manager, "proxy"))
        self.assertEqual(manager.proxy.scheme, "http")
        self.assertEqual(manager.proxy.host, "myproxy")
        self.assertEqual(manager.proxy.port, 8080)

    def test_environment_no_proxy_6(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,abc.gh,ample.com")
        base_url = "http://ample.com.org/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertIsInstance(manager, urllib3.ProxyManager)
        self.assertTrue(hasattr(manager, "proxy"))
        self.assertEqual(manager.proxy.scheme, "http")
        self.assertEqual(manager.proxy.host, "myproxy")
        self.assertEqual(manager.proxy.port, 8080)

    def test_environment_no_proxy_ipv4_address_1(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,192.168.0.10,ample.com")
        base_url = "http://192.168.0.10/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_ipv4_address_2(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,192.168.0.10,ample.com")
        base_url = "http://192.168.0.10:8888/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_ipv4_address_3(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,ff80:1::/64,192.168.0.0/24,ample.com")
        base_url = "http://192.168.0.10/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_ipv6_address_1(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,ff80:1::affe,ample.com")
        base_url = "http://[ff80:1::affe]/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_ipv6_address_2(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,ff80:1::affe,ample.com")
        base_url = "http://[ff80:1::affe]:1234/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_environment_no_proxy_ipv6_address_3(self):
        import urllib3

        config = ConfigDict()
        self.overrideEnv("http_proxy", "http://myproxy:8080")
        self.overrideEnv("no_proxy", "xyz,abc.def.gh,192.168.0.0/24,ff80:1::/64,ample.com")
        base_url = "http://[ff80:1::affe]/path/port"
        manager = default_urllib3_manager(config=config, base_url=base_url)
        self.assertNotIsInstance(manager, urllib3.ProxyManager)
        self.assertIsInstance(manager, urllib3.PoolManager)

    def test_config_proxy_custom_cls(self):
        import urllib3

        class CustomProxyManager(urllib3.ProxyManager):
            pass

        config = ConfigDict()
        config.set(b"http", b"proxy", b"http://localhost:3128/")
        manager = default_urllib3_manager(
            config=config, proxy_manager_cls=CustomProxyManager
        )
        self.assertIsInstance(manager, CustomProxyManager)

    def test_config_no_verify_ssl(self):
        manager = default_urllib3_manager(config=None, cert_reqs="CERT_NONE")
        self.assertEqual(manager.connection_pool_kw["cert_reqs"], "CERT_NONE")


class SubprocessSSHVendorTests(TestCase):
    def setUp(self):
        # Monkey Patch client subprocess popen
        self._orig_popen = dulwich.client.subprocess.Popen
        dulwich.client.subprocess.Popen = DummyPopen

    def tearDown(self):
        dulwich.client.subprocess.Popen = self._orig_popen

    def test_run_command_dashes(self):
        vendor = SubprocessSSHVendor()
        self.assertRaises(
            StrangeHostname,
            vendor.run_command,
            "--weird-host",
            "git-clone-url",
        )

    def test_run_command_password(self):
        vendor = SubprocessSSHVendor()
        self.assertRaises(
            NotImplementedError,
            vendor.run_command,
            "host",
            "git-clone-url",
            password="12345",
        )

    def test_run_command_password_and_privkey(self):
        vendor = SubprocessSSHVendor()
        self.assertRaises(
            NotImplementedError,
            vendor.run_command,
            "host",
            "git-clone-url",
            password="12345",
            key_filename="/tmp/id_rsa",
        )

    def test_run_command_with_port_username_and_privkey(self):
        expected = [
            "ssh",
            "-x",
            "-p",
            "2200",
            "-i",
            "/tmp/id_rsa",
            "user@host",
            "git-clone-url",
        ]

        vendor = SubprocessSSHVendor()
        command = vendor.run_command(
            "host",
            "git-clone-url",
            username="user",
            port="2200",
            key_filename="/tmp/id_rsa",
        )

        args = command.proc.args

        self.assertListEqual(expected, args[0])

    def test_run_with_ssh_command(self):
        expected = [
            "/path/to/ssh",
            "-o",
            "Option=Value",
            "-x",
            "host",
            "git-clone-url",
        ]

        vendor = SubprocessSSHVendor()
        command = vendor.run_command(
            "host",
            "git-clone-url",
            ssh_command="/path/to/ssh -o Option=Value",
        )

        args = command.proc.args
        self.assertListEqual(expected, args[0])


class PLinkSSHVendorTests(TestCase):
    def setUp(self):
        # Monkey Patch client subprocess popen
        self._orig_popen = dulwich.client.subprocess.Popen
        dulwich.client.subprocess.Popen = DummyPopen

    def tearDown(self):
        dulwich.client.subprocess.Popen = self._orig_popen

    def test_run_command_dashes(self):
        vendor = PLinkSSHVendor()
        self.assertRaises(
            StrangeHostname,
            vendor.run_command,
            "--weird-host",
            "git-clone-url",
        )

    def test_run_command_password_and_privkey(self):
        vendor = PLinkSSHVendor()

        warnings.simplefilter("always", UserWarning)
        self.addCleanup(warnings.resetwarnings)
        warnings_list, restore_warnings = setup_warning_catcher()
        self.addCleanup(restore_warnings)

        command = vendor.run_command(
            "host",
            "git-clone-url",
            password="12345",
            key_filename="/tmp/id_rsa",
        )

        expected_warning = UserWarning(
            "Invoking PLink with a password exposes the password in the "
            "process list."
        )

        for w in warnings_list:
            if type(w) == type(expected_warning) and w.args == expected_warning.args:
                break
        else:
            raise AssertionError(
                "Expected warning {!r} not in {!r}".format(expected_warning, warnings_list)
            )

        args = command.proc.args

        if sys.platform == "win32":
            binary = ["plink.exe", "-ssh"]
        else:
            binary = ["plink", "-ssh"]
        expected = binary + [
            "-pw",
            "12345",
            "-i",
            "/tmp/id_rsa",
            "host",
            "git-clone-url",
        ]
        self.assertListEqual(expected, args[0])

    def test_run_command_password(self):
        if sys.platform == "win32":
            binary = ["plink.exe", "-ssh"]
        else:
            binary = ["plink", "-ssh"]
        expected = binary + ["-pw", "12345", "host", "git-clone-url"]

        vendor = PLinkSSHVendor()

        warnings.simplefilter("always", UserWarning)
        self.addCleanup(warnings.resetwarnings)
        warnings_list, restore_warnings = setup_warning_catcher()
        self.addCleanup(restore_warnings)

        command = vendor.run_command("host", "git-clone-url", password="12345")

        expected_warning = UserWarning(
            "Invoking PLink with a password exposes the password in the "
            "process list."
        )

        for w in warnings_list:
            if type(w) == type(expected_warning) and w.args == expected_warning.args:
                break
        else:
            raise AssertionError(
                "Expected warning {!r} not in {!r}".format(expected_warning, warnings_list)
            )

        args = command.proc.args

        self.assertListEqual(expected, args[0])

    def test_run_command_with_port_username_and_privkey(self):
        if sys.platform == "win32":
            binary = ["plink.exe", "-ssh"]
        else:
            binary = ["plink", "-ssh"]
        expected = binary + [
            "-P",
            "2200",
            "-i",
            "/tmp/id_rsa",
            "user@host",
            "git-clone-url",
        ]

        vendor = PLinkSSHVendor()
        command = vendor.run_command(
            "host",
            "git-clone-url",
            username="user",
            port="2200",
            key_filename="/tmp/id_rsa",
        )

        args = command.proc.args

        self.assertListEqual(expected, args[0])

    def test_run_with_ssh_command(self):
        expected = [
            "/path/to/plink",
            "-x",
            "host",
            "git-clone-url",
        ]

        vendor = SubprocessSSHVendor()
        command = vendor.run_command(
            "host",
            "git-clone-url",
            ssh_command="/path/to/plink",
        )

        args = command.proc.args
        self.assertListEqual(expected, args[0])


class RsyncUrlTests(TestCase):
    def test_simple(self):
        self.assertEqual(parse_rsync_url("foo:bar/path"), (None, "foo", "bar/path"))
        self.assertEqual(
            parse_rsync_url("user@foo:bar/path"), ("user", "foo", "bar/path")
        )

    def test_path(self):
        self.assertRaises(ValueError, parse_rsync_url, "/path")


class CheckWantsTests(TestCase):
    def test_fine(self):
        check_wants(
            [b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"],
            {b"refs/heads/blah": b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"},
        )

    def test_missing(self):
        self.assertRaises(
            InvalidWants,
            check_wants,
            [b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"],
            {b"refs/heads/blah": b"3f3dc7a53fb752a6961d3a56683df46d4d3bf262"},
        )

    def test_annotated(self):
        self.assertRaises(
            InvalidWants,
            check_wants,
            [b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"],
            {
                b"refs/heads/blah": b"3f3dc7a53fb752a6961d3a56683df46d4d3bf262",
                b"refs/heads/blah^{}": b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262",
            },
        )


class FetchPackResultTests(TestCase):
    def test_eq(self):
        self.assertEqual(
            FetchPackResult(
                {b"refs/heads/master": b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"},
                {},
                b"user/agent",
            ),
            FetchPackResult(
                {b"refs/heads/master": b"2f3dc7a53fb752a6961d3a56683df46d4d3bf262"},
                {},
                b"user/agent",
            ),
        )


class GitCredentialStoreTests(TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"https://user:pass@example.org\n")
        cls.fname = f.name

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.fname)

    def test_nonmatching_scheme(self):
        self.assertEqual(
            get_credentials_from_store(b"http", b"example.org", fnames=[self.fname]),
            None,
        )

    def test_nonmatching_hostname(self):
        self.assertEqual(
            get_credentials_from_store(b"https", b"noentry.org", fnames=[self.fname]),
            None,
        )

    def test_match_without_username(self):
        self.assertEqual(
            get_credentials_from_store(b"https", b"example.org", fnames=[self.fname]),
            (b"user", b"pass"),
        )

    def test_match_with_matching_username(self):
        self.assertEqual(
            get_credentials_from_store(
                b"https", b"example.org", b"user", fnames=[self.fname]
            ),
            (b"user", b"pass"),
        )

    def test_no_match_with_nonmatching_username(self):
        self.assertEqual(
            get_credentials_from_store(
                b"https", b"example.org", b"otheruser", fnames=[self.fname]
            ),
            None,
        )


class RemoteErrorFromStderrTests(TestCase):
    def test_nothing(self):
        self.assertEqual(_remote_error_from_stderr(None), HangupException())

    def test_error_line(self):
        b = BytesIO(
            b"""\
This is some random output.
ERROR: This is the actual error
with a tail
"""
        )
        self.assertEqual(
            _remote_error_from_stderr(b),
            GitProtocolError("This is the actual error"),
        )

    def test_no_error_line(self):
        b = BytesIO(
            b"""\
This is output without an error line.
And this line is just random noise, too.
"""
        )
        self.assertEqual(
            _remote_error_from_stderr(b),
            HangupException(
                [
                    b"This is output without an error line.",
                    b"And this line is just random noise, too.",
                ]
            ),
        )
