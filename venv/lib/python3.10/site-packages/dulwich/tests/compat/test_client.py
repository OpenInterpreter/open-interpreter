# test_client.py -- Compatibility tests for git client.
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

"""Compatibility tests between the Dulwich client and the cgit server."""

import copy
import http.server
import os
import select
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
from contextlib import suppress
from io import BytesIO
from urllib.parse import unquote

from dulwich import client, file, index, objects, protocol, repo
from dulwich.tests import SkipTest, expectedFailure

from .utils import (_DEFAULT_GIT, CompatTestCase, check_for_daemon,
                    import_repo_to_dir, rmtree_ro, run_git_or_fail)

if sys.platform == "win32":
    import ctypes


class DulwichClientTestBase:
    """Tests for client/server compatibility."""

    def setUp(self):
        self.gitroot = os.path.dirname(
            import_repo_to_dir("server_new.export").rstrip(os.sep)
        )
        self.dest = os.path.join(self.gitroot, "dest")
        file.ensure_dir_exists(self.dest)
        run_git_or_fail(["init", "--quiet", "--bare"], cwd=self.dest)

    def tearDown(self):
        rmtree_ro(self.gitroot)

    def assertDestEqualsSrc(self):
        repo_dir = os.path.join(self.gitroot, "server_new.export")
        dest_repo_dir = os.path.join(self.gitroot, "dest")
        with repo.Repo(repo_dir) as src:
            with repo.Repo(dest_repo_dir) as dest:
                self.assertReposEqual(src, dest)

    def _client(self):
        raise NotImplementedError()

    def _build_path(self):
        raise NotImplementedError()

    def _do_send_pack(self):
        c = self._client()
        srcpath = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(srcpath) as src:
            sendrefs = dict(src.get_refs())
            del sendrefs[b"HEAD"]
            c.send_pack(
                self._build_path("/dest"),
                lambda _: sendrefs,
                src.generate_pack_data,
            )

    def test_send_pack(self):
        self._do_send_pack()
        self.assertDestEqualsSrc()

    def test_send_pack_nothing_to_send(self):
        self._do_send_pack()
        self.assertDestEqualsSrc()
        # nothing to send, but shouldn't raise either.
        self._do_send_pack()

    @staticmethod
    def _add_file(repo, tree_id, filename, contents):
        tree = repo[tree_id]
        blob = objects.Blob()
        blob.data = contents.encode("utf-8")
        repo.object_store.add_object(blob)
        tree.add(filename.encode("utf-8"), stat.S_IFREG | 0o644, blob.id)
        repo.object_store.add_object(tree)
        return tree.id

    def test_send_pack_from_shallow_clone(self):
        c = self._client()
        server_new_path = os.path.join(self.gitroot, "server_new.export")
        run_git_or_fail(["config", "http.uploadpack", "true"], cwd=server_new_path)
        run_git_or_fail(["config", "http.receivepack", "true"], cwd=server_new_path)
        remote_path = self._build_path("/server_new.export")
        with repo.Repo(self.dest) as local:
            result = c.fetch(remote_path, local, depth=1)
            for r in result.refs.items():
                local.refs.set_if_equals(r[0], None, r[1])
            tree_id = local[local.head()].tree
            for filename, contents in [
                ("bar", "bar contents"),
                ("zop", "zop contents"),
            ]:
                tree_id = self._add_file(local, tree_id, filename, contents)
                commit_id = local.do_commit(
                    message=b"add " + filename.encode("utf-8"),
                    committer=b"Joe Example <joe@example.com>",
                    tree=tree_id,
                )
            sendrefs = dict(local.get_refs())
            del sendrefs[b"HEAD"]
            c.send_pack(remote_path, lambda _: sendrefs, local.generate_pack_data)
        with repo.Repo(server_new_path) as remote:
            self.assertEqual(remote.head(), commit_id)

    def test_send_without_report_status(self):
        c = self._client()
        c._send_capabilities.remove(b"report-status")
        srcpath = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(srcpath) as src:
            sendrefs = dict(src.get_refs())
            del sendrefs[b"HEAD"]
            c.send_pack(
                self._build_path("/dest"),
                lambda _: sendrefs,
                src.generate_pack_data,
            )
            self.assertDestEqualsSrc()

    def make_dummy_commit(self, dest):
        b = objects.Blob.from_string(b"hi")
        dest.object_store.add_object(b)
        t = index.commit_tree(dest.object_store, [(b"hi", b.id, 0o100644)])
        c = objects.Commit()
        c.author = c.committer = b"Foo Bar <foo@example.com>"
        c.author_time = c.commit_time = 0
        c.author_timezone = c.commit_timezone = 0
        c.message = b"hi"
        c.tree = t
        dest.object_store.add_object(c)
        return c.id

    def disable_ff_and_make_dummy_commit(self):
        # disable non-fast-forward pushes to the server
        dest = repo.Repo(os.path.join(self.gitroot, "dest"))
        run_git_or_fail(
            ["config", "receive.denyNonFastForwards", "true"], cwd=dest.path
        )
        commit_id = self.make_dummy_commit(dest)
        return dest, commit_id

    def compute_send(self, src):
        sendrefs = dict(src.get_refs())
        del sendrefs[b"HEAD"]
        return sendrefs, src.generate_pack_data

    def test_send_pack_one_error(self):
        dest, dummy_commit = self.disable_ff_and_make_dummy_commit()
        dest.refs[b"refs/heads/master"] = dummy_commit
        repo_dir = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(repo_dir) as src:
            sendrefs, gen_pack = self.compute_send(src)
            c = self._client()
            result = c.send_pack(
                self._build_path("/dest"), lambda _: sendrefs, gen_pack
            )
            self.assertEqual(
                {
                    b"refs/heads/branch": None,
                    b"refs/heads/master": "non-fast-forward",
                },
                result.ref_status,
            )

    def test_send_pack_multiple_errors(self):
        dest, dummy = self.disable_ff_and_make_dummy_commit()
        # set up for two non-ff errors
        branch, master = b"refs/heads/branch", b"refs/heads/master"
        dest.refs[branch] = dest.refs[master] = dummy
        repo_dir = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(repo_dir) as src:
            sendrefs, gen_pack = self.compute_send(src)
            c = self._client()
            result = c.send_pack(
                self._build_path("/dest"), lambda _: sendrefs, gen_pack
            )
            self.assertEqual(
                {branch: "non-fast-forward", master: "non-fast-forward"},
                result.ref_status,
            )

    def test_archive(self):
        c = self._client()
        f = BytesIO()
        c.archive(self._build_path("/server_new.export"), b"HEAD", f.write)
        f.seek(0)
        tf = tarfile.open(fileobj=f)
        self.assertEqual(["baz", "foo"], tf.getnames())

    def test_fetch_pack(self):
        c = self._client()
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(self._build_path("/server_new.export"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

    def test_fetch_pack_depth(self):
        c = self._client()
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(self._build_path("/server_new.export"), dest, depth=1)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertEqual(
                dest.get_shallow(),
                {
                    b"35e0b59e187dd72a0af294aedffc213eaa4d03ff",
                    b"514dc6d3fbfe77361bcaef320c4d21b72bc10be9",
                },
            )

    def test_repeat(self):
        c = self._client()
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(self._build_path("/server_new.export"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()
            result = c.fetch(self._build_path("/server_new.export"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

    def test_fetch_empty_pack(self):
        c = self._client()
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(self._build_path("/server_new.export"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

            def dw(refs, **kwargs):
                return list(refs.values())

            result = c.fetch(
                self._build_path("/server_new.export"),
                dest,
                determine_wants=dw,
            )
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

    def test_incremental_fetch_pack(self):
        self.test_fetch_pack()
        dest, dummy = self.disable_ff_and_make_dummy_commit()
        dest.refs[b"refs/heads/master"] = dummy
        c = self._client()
        repo_dir = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(repo_dir) as dest:
            result = c.fetch(self._build_path("/dest"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

    def test_fetch_pack_no_side_band_64k(self):
        c = self._client()
        c._fetch_capabilities.remove(b"side-band-64k")
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(self._build_path("/server_new.export"), dest)
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])
            self.assertDestEqualsSrc()

    def test_fetch_pack_zero_sha(self):
        # zero sha1s are already present on the client, and should
        # be ignored
        c = self._client()
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            result = c.fetch(
                self._build_path("/server_new.export"),
                dest,
                lambda refs, **kwargs: [protocol.ZERO_SHA],
            )
            for r in result.refs.items():
                dest.refs.set_if_equals(r[0], None, r[1])

    def test_send_remove_branch(self):
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            dummy_commit = self.make_dummy_commit(dest)
            dest.refs[b"refs/heads/master"] = dummy_commit
            dest.refs[b"refs/heads/abranch"] = dummy_commit
            sendrefs = dict(dest.refs)
            sendrefs[b"refs/heads/abranch"] = b"00" * 20
            del sendrefs[b"HEAD"]

            def gen_pack(have, want, ofs_delta=False, progress=None):
                return 0, []

            c = self._client()
            self.assertEqual(dest.refs[b"refs/heads/abranch"], dummy_commit)
            c.send_pack(self._build_path("/dest"), lambda _: sendrefs, gen_pack)
            self.assertNotIn(b"refs/heads/abranch", dest.refs)

    def test_send_new_branch_empty_pack(self):
        with repo.Repo(os.path.join(self.gitroot, "dest")) as dest:
            dummy_commit = self.make_dummy_commit(dest)
            dest.refs[b"refs/heads/master"] = dummy_commit
            dest.refs[b"refs/heads/abranch"] = dummy_commit
            sendrefs = {b"refs/heads/bbranch": dummy_commit}

            def gen_pack(have, want, ofs_delta=False, progress=None):
                return 0, []

            c = self._client()
            self.assertEqual(dest.refs[b"refs/heads/abranch"], dummy_commit)
            c.send_pack(self._build_path("/dest"), lambda _: sendrefs, gen_pack)
            self.assertEqual(dummy_commit, dest.refs[b"refs/heads/abranch"])

    def test_get_refs(self):
        c = self._client()
        refs = c.get_refs(self._build_path("/server_new.export"))

        repo_dir = os.path.join(self.gitroot, "server_new.export")
        with repo.Repo(repo_dir) as dest:
            self.assertDictEqual(dest.refs.as_dict(), refs)


class DulwichTCPClientTest(CompatTestCase, DulwichClientTestBase):
    def setUp(self):
        CompatTestCase.setUp(self)
        DulwichClientTestBase.setUp(self)
        if check_for_daemon(limit=1):
            raise SkipTest(
                "git-daemon was already running on port %s" % protocol.TCP_GIT_PORT
            )
        fd, self.pidfile = tempfile.mkstemp(
            prefix="dulwich-test-git-client", suffix=".pid"
        )
        os.fdopen(fd).close()
        args = [
            _DEFAULT_GIT,
            "daemon",
            "--verbose",
            "--export-all",
            "--pid-file=%s" % self.pidfile,
            "--base-path=%s" % self.gitroot,
            "--enable=receive-pack",
            "--enable=upload-archive",
            "--listen=localhost",
            "--reuseaddr",
            self.gitroot,
        ]
        self.process = subprocess.Popen(
            args,
            cwd=self.gitroot,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not check_for_daemon():
            raise SkipTest("git-daemon failed to start")

    def tearDown(self):
        with open(self.pidfile) as f:
            pid = int(f.read().strip())
        if sys.platform == "win32":
            PROCESS_TERMINATE = 1
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
        else:
            with suppress(OSError):
                os.kill(pid, signal.SIGKILL)
                os.unlink(self.pidfile)
        self.process.wait()
        self.process.stdout.close()
        self.process.stderr.close()
        DulwichClientTestBase.tearDown(self)
        CompatTestCase.tearDown(self)

    def _client(self):
        return client.TCPGitClient("localhost")

    def _build_path(self, path):
        return path

    if sys.platform == "win32":

        @expectedFailure
        def test_fetch_pack_no_side_band_64k(self):
            DulwichClientTestBase.test_fetch_pack_no_side_band_64k(self)

    def test_send_remove_branch(self):
        # This test fails intermittently on my machine, probably due to some sort
        # of race condition. Probably also related to #1015
        self.skipTest('skip flaky test; see #1015')


class TestSSHVendor:
    @staticmethod
    def run_command(
        host,
        command,
        username=None,
        port=None,
        password=None,
        key_filename=None,
    ):
        cmd, path = command.split(" ")
        cmd = cmd.split("-", 1)
        path = path.replace("'", "")
        p = subprocess.Popen(
            cmd + [path],
            bufsize=0,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return client.SubprocessWrapper(p)


class DulwichMockSSHClientTest(CompatTestCase, DulwichClientTestBase):
    def setUp(self):
        CompatTestCase.setUp(self)
        DulwichClientTestBase.setUp(self)
        self.real_vendor = client.get_ssh_vendor
        client.get_ssh_vendor = TestSSHVendor

    def tearDown(self):
        DulwichClientTestBase.tearDown(self)
        CompatTestCase.tearDown(self)
        client.get_ssh_vendor = self.real_vendor

    def _client(self):
        return client.SSHGitClient("localhost")

    def _build_path(self, path):
        return self.gitroot + path


class DulwichSubprocessClientTest(CompatTestCase, DulwichClientTestBase):
    def setUp(self):
        CompatTestCase.setUp(self)
        DulwichClientTestBase.setUp(self)

    def tearDown(self):
        DulwichClientTestBase.tearDown(self)
        CompatTestCase.tearDown(self)

    def _client(self):
        return client.SubprocessGitClient()

    def _build_path(self, path):
        return self.gitroot + path


class GitHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request handler that calls out to 'git http-backend'."""

    # Make rfile unbuffered -- we need to read one line and then pass
    # the rest to a subprocess, so we can't use buffered input.
    rbufsize = 0

    def do_POST(self):
        self.run_backend()

    def do_GET(self):
        self.run_backend()

    def send_head(self):
        return self.run_backend()

    def log_request(self, code="-", size="-"):
        # Let's be quiet, the test suite is noisy enough already
        pass

    def run_backend(self):  # noqa: C901
        """Call out to git http-backend."""
        # Based on CGIHTTPServer.CGIHTTPRequestHandler.run_cgi:
        # Copyright (c) 2001-2010 Python Software Foundation;
        # All Rights Reserved
        # Licensed under the Python Software Foundation License.
        rest = self.path
        # find an explicit query string, if present.
        i = rest.rfind("?")
        if i >= 0:
            rest, query = rest[:i], rest[i + 1 :]
        else:
            query = ""

        env = copy.deepcopy(os.environ)
        env["SERVER_SOFTWARE"] = self.version_string()
        env["SERVER_NAME"] = self.server.server_name
        env["GATEWAY_INTERFACE"] = "CGI/1.1"
        env["SERVER_PROTOCOL"] = self.protocol_version
        env["SERVER_PORT"] = str(self.server.server_port)
        env["GIT_PROJECT_ROOT"] = self.server.root_path
        env["GIT_HTTP_EXPORT_ALL"] = "1"
        env["REQUEST_METHOD"] = self.command
        uqrest = unquote(rest)
        env["PATH_INFO"] = uqrest
        env["SCRIPT_NAME"] = "/"
        if query:
            env["QUERY_STRING"] = query
        host = self.address_string()
        if host != self.client_address[0]:
            env["REMOTE_HOST"] = host
        env["REMOTE_ADDR"] = self.client_address[0]
        authorization = self.headers.get("authorization")
        if authorization:
            authorization = authorization.split()
            if len(authorization) == 2:
                import base64
                import binascii

                env["AUTH_TYPE"] = authorization[0]
                if authorization[0].lower() == "basic":
                    try:
                        authorization = base64.decodestring(authorization[1])
                    except binascii.Error:
                        pass
                    else:
                        authorization = authorization.split(":")
                        if len(authorization) == 2:
                            env["REMOTE_USER"] = authorization[0]
        # XXX REMOTE_IDENT
        content_type = self.headers.get("content-type")
        if content_type:
            env["CONTENT_TYPE"] = content_type
        length = self.headers.get("content-length")
        if length:
            env["CONTENT_LENGTH"] = length
        referer = self.headers.get("referer")
        if referer:
            env["HTTP_REFERER"] = referer
        accept = []
        for line in self.headers.getallmatchingheaders("accept"):
            if line[:1] in "\t\n\r ":
                accept.append(line.strip())
            else:
                accept = accept + line[7:].split(",")
        env["HTTP_ACCEPT"] = ",".join(accept)
        ua = self.headers.get("user-agent")
        if ua:
            env["HTTP_USER_AGENT"] = ua
        co = self.headers.get("cookie")
        if co:
            env["HTTP_COOKIE"] = co
        # XXX Other HTTP_* headers
        # Since we're setting the env in the parent, provide empty
        # values to override previously set values
        for k in (
            "QUERY_STRING",
            "REMOTE_HOST",
            "CONTENT_LENGTH",
            "HTTP_USER_AGENT",
            "HTTP_COOKIE",
            "HTTP_REFERER",
        ):
            env.setdefault(k, "")

        self.wfile.write(b"HTTP/1.1 200 Script output follows\r\n")
        self.wfile.write(("Server: %s\r\n" % self.server.server_name).encode("ascii"))
        self.wfile.write(("Date: %s\r\n" % self.date_time_string()).encode("ascii"))

        decoded_query = query.replace("+", " ")

        try:
            nbytes = int(length)
        except (TypeError, ValueError):
            nbytes = -1
        if self.command.lower() == "post":
            if nbytes > 0:
                data = self.rfile.read(nbytes)
            elif self.headers.get('transfer-encoding') == 'chunked':
                chunks = []
                while True:
                    line = self.rfile.readline()
                    length = int(line.rstrip(), 16)
                    chunk = self.rfile.read(length + 2)
                    chunks.append(chunk[:-2])
                    if length == 0:
                        break
                data = b''.join(chunks)
                env["CONTENT_LENGTH"] = str(len(data))
            else:
                raise AssertionError
        else:
            data = None
            env["CONTENT_LENGTH"] = "0"
        # throw away additional data [see bug #427345]
        while select.select([self.rfile._sock], [], [], 0)[0]:
            if not self.rfile._sock.recv(1):
                break
        args = ["http-backend"]
        if "=" not in decoded_query:
            args.append(decoded_query)
        stdout = run_git_or_fail(args, input=data, env=env, stderr=subprocess.PIPE)
        self.wfile.write(stdout)


class HTTPGitServer(http.server.HTTPServer):

    allow_reuse_address = True

    def __init__(self, server_address, root_path):
        http.server.HTTPServer.__init__(self, server_address, GitHTTPRequestHandler)
        self.root_path = root_path
        self.server_name = "localhost"

    def get_url(self):
        return "http://{}:{}/".format(self.server_name, self.server_port)


class DulwichHttpClientTest(CompatTestCase, DulwichClientTestBase):

    min_git_version = (1, 7, 0, 2)

    def setUp(self):
        CompatTestCase.setUp(self)
        DulwichClientTestBase.setUp(self)
        self._httpd = HTTPGitServer(("localhost", 0), self.gitroot)
        self.addCleanup(self._httpd.shutdown)
        threading.Thread(target=self._httpd.serve_forever).start()
        run_git_or_fail(["config", "http.uploadpack", "true"], cwd=self.dest)
        run_git_or_fail(["config", "http.receivepack", "true"], cwd=self.dest)

    def tearDown(self):
        DulwichClientTestBase.tearDown(self)
        CompatTestCase.tearDown(self)
        self._httpd.shutdown()
        self._httpd.socket.close()

    def _client(self):
        return client.HttpGitClient(self._httpd.get_url())

    def _build_path(self, path):
        return path

    def test_archive(self):
        raise SkipTest("exporting archives not supported over http")
