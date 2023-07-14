# test_porcelain.py -- porcelain tests
# Copyright (C) 2013 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for dulwich.porcelain."""

import contextlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from io import BytesIO, StringIO
from unittest import skipIf

from dulwich import porcelain
from dulwich.tests import TestCase

from ..diff_tree import tree_changes
from ..errors import CommitError
from ..objects import ZERO_SHA, Blob, Tag, Tree
from ..porcelain import CheckoutError
from ..repo import NoIndexPresent, Repo
from ..server import DictBackend
from ..web import make_server, make_wsgi_chain
from .utils import build_commit_graph, make_commit, make_object

try:
    import gpg
except ImportError:
    gpg = None


def flat_walk_dir(dir_to_walk):
    for dirpath, _, filenames in os.walk(dir_to_walk):
        rel_dirpath = os.path.relpath(dirpath, dir_to_walk)
        if not dirpath == dir_to_walk:
            yield rel_dirpath
        for filename in filenames:
            if dirpath == dir_to_walk:
                yield filename
            else:
                yield os.path.join(rel_dirpath, filename)


class PorcelainTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)
        self.repo_path = os.path.join(self.test_dir, "repo")
        self.repo = Repo.init(self.repo_path, mkdir=True)
        self.addCleanup(self.repo.close)

    def assertRecentTimestamp(self, ts):
        # On some slow CIs it does actually take more than 5 seconds to go from
        # creating the tag to here.
        self.assertLess(time.time() - ts, 50)


@skipIf(gpg is None, "gpg is not available")
class PorcelainGpgTestCase(PorcelainTestCase):
    DEFAULT_KEY = """
-----BEGIN PGP PRIVATE KEY BLOCK-----

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
brMb2upTHa+kjktjdO96/BgSnKYqmNmPB/qB
=ivA/
-----END PGP PRIVATE KEY BLOCK-----
    """

    DEFAULT_KEY_ID = "8EB47C310E1F24AE383D832F7CDD800A52E65E26"

    NON_DEFAULT_KEY = """
-----BEGIN PGP PRIVATE KEY BLOCK-----

lQVYBGBjI0ABDADGWBRp+t02emfzUlhrc1psqIhhecFm6Em0Kv33cfDpnfoMF1tK
Yy/4eLYIR7FmpdbFPcDThFNHbXJzBi00L1mp0XQE2l50h/2bDAAgREdZ+NVo5a7/
RSZjauNU1PxW6pnXMehEh1tyIQmV78jAukaakwaicrpIenMiFUN3fAKHnLuFffA6
t0f3LqJvTDhUw/o2vPgw5e6UDQhA1C+KTv1KXVrhJNo88a3hZqCZ76z3drKR411Q
zYgT4DUb8lfnbN+z2wfqT9oM5cegh2k86/mxAA3BYOeQrhmQo/7uhezcgbxtdGZr
YlbuaNDTSBrn10ZoaxLPo2dJe2zWxgD6MpvsGU1w3tcRW508qo/+xoWp2/pDzmok
+uhOh1NAj9zB05VWBz1r7oBgCOIKpkD/LD4VKq59etsZ/UnrYDwKdXWZp7uhshkU
M7N35lUJcR76a852dlMdrgpmY18+BP7+o7M+5ElHTiqQbMuE1nHTg8RgVpdV+tUx
dg6GWY/XHf5asm8AEQEAAQAL/A85epOp+GnymmEQfI3+5D178D//Lwu9n86vECB6
xAHCqQtdjZnXpDp/1YUsL59P8nzgYRk7SoMskQDoQ/cB/XFuDOhEdMSgHaTVlnrj
ktCCq6rqGnUosyolbb64vIfVaSqd/5SnCStpAsnaBoBYrAu4ZmV4xfjDQWwn0q5s
u+r56mD0SkjPgbwk/b3qTVagVmf2OFzUgWwm1e/X+bA1oPag1NV8VS4hZPXswT4f
qhiyqUFOgP6vUBcqehkjkIDIl/54xII7/P5tp3LIZawvIXqHKNTqYPCqaCqCj+SL
vMYDIb6acjescfZoM71eAeHAANeFZzr/rwfBT+dEP6qKmPXNcvgE11X44ZCr04nT
zOV/uDUifEvKT5qgtyJpSFEVr7EXubJPKoNNhoYqq9z1pYU7IedX5BloiVXKOKTY
0pk7JkLqf3g5fYtXh/wol1owemITJy5V5PgaqZvk491LkI6S+kWC7ANYUg+TDPIW
afxW3E5N1CYV6XDAl0ZihbLcoQYAy0Ky/p/wayWKePyuPBLwx9O89GSONK2pQljZ
yaAgxPQ5/i1vx6LIMg7k/722bXR9W3zOjWOin4eatPM3d2hkG96HFvnBqXSmXOPV
03Xqy1/B5Tj8E9naLKUHE/OBQEc363DgLLG9db5HfPlpAngeppYPdyWkhzXyzkgS
PylaE5eW3zkdjEbYJ6RBTecTZEgBaMvJNPdWbn//frpP7kGvyiCg5Es+WjLInUZ6
0sdifcNTCewzLXK80v/y5mVOdJhPBgD5zs9cYdyiQJayqAuOr+He1eMHMVUbm9as
qBmPrst398eBW9ZYF7eBfTSlUf6B+WnvyLKEGsUf/7IK0EWDlzoBuWzWiHjUAY1g
m9eTV2MnvCCCefqCErWwfFo2nWOasAZA9sKD+ICIBY4tbtvSl4yfLBzTMwSvs9ZS
K1ocPSYUnhm2miSWZ8RLZPH7roHQasNHpyq/AX7DahFf2S/bJ+46ZGZ8Pigr7hA+
MjmpQ4qVdb5SaViPmZhAKO+PjuCHm+EF/2H0Y3Sl4eXgxZWoQVOUeXdWg9eMfYrj
XDtUMIFppV/QxbeztZKvJdfk64vt/crvLsOp0hOky9cKwY89r4QaHfexU3qR+qDq
UlMvR1rHk7dS5HZAtw0xKsFJNkuDxvBkMqv8Los8zp3nUl+U99dfZOArzNkW38wx
FPa0ixkC9za2BkDrWEA8vTnxw0A2upIFegDUhwOByrSyfPPnG3tKGeqt3Izb/kDk
Q9vmo+HgxBOguMIvlzbBfQZwtbd/gXzlvPqCtCJBbm90aGVyIFRlc3QgVXNlciA8
dGVzdDJAdGVzdC5jb20+iQHOBBMBCAA4AhsDBQsJCAcCBhUKCQgLAgQWAgMBAh4B
AheAFiEEapM5P1DF5qzT1vtFuTYhLttOFMAFAmDcEeEACgkQuTYhLttOFMDe0Qv/
Qx/bzXztJ3BCc+CYAVDx7Kr37S68etwwLgcWzhG+CDeMB5F/QE+upKgxy2iaqQFR
mxfOMgf/TIQkUfkbaASzK1LpnesYO85pk7XYjoN1bYEHiXTkeW+bgB6aJIxrRmO2
SrWasdBC/DsI3Mrya8YMt/TiHC6VpRJVxCe5vv7/kZC4CXrgTBnZocXx/YXimbke
poPMVdbvhYh6N0aGeS38jRKgyN10KXmhDTAQDwseVFavBWAjVfx3DEwjtK2Z2GbA
aL8JvAwRtqiPFkDMIKPL4UwxtXFws8SpMt6juroUkNyf6+BxNWYqmwXHPy8zCJAb
xkxIJMlEc+s7qQsP3fILOo8Xn+dVzJ5sa5AoARoXm1GMjsdqaKAzq99Dic/dHnaQ
Civev1PQsdwlYW2C2wNXNeIrxMndbDMFfNuZ6BnGHWJ/wjcp/pFs4YkyyZN8JH7L
hP2FO4Jgham3AuP13kC3Ivea7V6hR8QNcDZRwFPOMIX4tXwQv1T72+7DZGaA25O7
nQVXBGBjI0ABDADJMBYIcG0Yil9YxFs7aYzNbd7alUAr89VbY8eIGPHP3INFPM1w
lBQCu+4j6xdEbhMpppLBZ9A5TEylP4C6qLtPa+oLtPeuSw8gHDE10XE4lbgPs376
rL60XdImSOHhiduACUefYjqpcmFH9Bim1CC+koArYrSQJQx1Jri+OpnTaL/8UID0
KzD/kEgMVGlHIVj9oJmb4+j9pW8I/g0wDSnIaEKFMxqu6SIVJ1GWj+MUMvZigjLC
sNCZd7PnbOC5VeU3SsXj6he74Jx0AmGMPWIHi9M0DjHO5d1cCbXTnud8xxM1bOh4
7aCTnMK5cVyIr+adihgJpVVhrndSM8aklBPRgtozrGNCgF2CkYU2P1blxfloNr/8
UZpM83o+s1aObBszzRNLxnpNORqoLqjfPtLEPQnagxE+4EapCq0NZ/x6yO5VTwwp
NljdFAEk40uGuKyn1QA3uNMHy5DlpLl+tU7t1KEovdZ+OVYsYKZhVzw0MTpKogk9
JI7AN0q62ronPskAEQEAAQAL+O8BUSt1ZCVjPSIXIsrR+ZOSkszZwgJ1CWIoh0IH
YD2vmcMHGIhFYgBdgerpvhptKhaw7GcXDScEnYkyh5s4GE2hxclik1tbj/x1gYCN
8BNoyeDdPFxQG73qN12D99QYEctpOsz9xPLIDwmL0j1ehAfhwqHIAPm9Ca+i8JYM
x/F+35S/jnKDXRI+NVlwbiEyXKXxxIqNlpy9i8sDBGexO5H5Sg0zSN/B1duLekGD
biDw6gLc6bCgnS+0JOUpU07Z2fccMOY9ncjKGD2uIb/ePPUaek92GCQyq0eorCIV
brcQsRc5sSsNtnRKQTQtxioROeDg7kf2oWySeHTswlXW/219ihrSXgteHJd+rPm7
DYLEeGLRny8bRKv8rQdAtApHaJE4dAATXeY4RYo4NlXHYaztGYtU6kiM/3zCfWAe
9Nn+Wh9jMTZrjefUCagS5r6ZqAh7veNo/vgIGaCLh0a1Ypa0Yk9KFrn3LYEM3zgk
3m3bn+7qgy5cUYXoJ3DGJJEhBgDPonpW0WElqLs5ZMem1ha85SC38F0IkAaSuzuz
v3eORiKWuyJGF32Q2XHa1RHQs1JtUKd8rxFer3b8Oq71zLz6JtVc9dmRudvgcJYX
0PC11F6WGjZFSSp39dajFp0A5DKUs39F3w7J1yuDM56TDIN810ywufGAHARY1pZb
UJAy/dTqjFnCbNjpAakor3hVzqxcmUG+7Y2X9c2AGncT1MqAQC3M8JZcuZvkK8A9
cMk8B914ryYE7VsZMdMhyTwHmykGAPgNLLa3RDETeGeGCKWI+ZPOoU0ib5JtJZ1d
P3tNwfZKuZBZXKW9gqYqyBa/qhMip84SP30pr/TvulcdAFC759HK8sQZyJ6Vw24P
c+5ssRxrQUEw1rvJPWhmQCmCOZHBMQl5T6eaTOpR5u3aUKTMlxPKhK9eC1dCSTnI
/nyL8An3VKnLy+K/LI42YGphBVLLJmBewuTVDIJviWRdntiG8dElyEJMOywUltk3
2CEmqgsD9tPO8rXZjnMrMn3gfsiaoQYA6/6/e2utkHr7gAoWBgrBBdqVHsvqh5Ro
2DjLAOpZItO/EdCJfDAmbTYOa04535sBDP2tcH/vipPOPpbr1Y9Y/mNsKCulNxed
yqAmEkKOcerLUP5UHju0AB6VBjHJFdU2mqT+UjPyBk7WeKXgFomyoYMv3KpNOFWR
xi0Xji4kKHbttA6Hy3UcGPr9acyUAlDYeKmxbSUYIPhw32bbGrX9+F5YriTufRsG
3jftQVo9zqdcQSD/5pUTMn3EYbEcohYB2YWJAbYEGAEIACACGwwWIQRqkzk/UMXm
rNPW+0W5NiEu204UwAUCYNwR6wAKCRC5NiEu204UwOPnC/92PgB1c3h9FBXH1maz
g29fndHIHH65VLgqMiQ7HAMojwRlT5Xnj5tdkCBmszRkv5vMvdJRa3ZY8Ed/Inqr
hxBFNzpjqX4oj/RYIQLKXWWfkTKYVLJFZFPCSo00jesw2gieu3Ke/Yy4gwhtNodA
v+s6QNMvffTW/K3XNrWDB0E7/LXbdidzhm+MBu8ov2tuC3tp9liLICiE1jv/2xT4
CNSO6yphmk1/1zEYHS/mN9qJ2csBmte2cdmGyOcuVEHk3pyINNMDOamaURBJGRwF
XB5V7gTKUFU4jCp3chywKrBHJHxGGDUmPBmZtDtfWAOgL32drK7/KUyzZL/WO7Fj
akOI0hRDFOcqTYWL20H7+hAiX3oHMP7eou3L5C7wJ9+JMcACklN/WMjG9a536DFJ
4UgZ6HyKPP+wy837Hbe8b25kNMBwFgiaLR0lcgzxj7NyQWjVCMOEN+M55tRCjvL6
ya6JVZCRbMXfdCy8lVPgtNQ6VlHaj8Wvnn2FLbWWO2n2r3s=
=9zU5
-----END PGP PRIVATE KEY BLOCK-----
"""

    NON_DEFAULT_KEY_ID = "6A93393F50C5E6ACD3D6FB45B936212EDB4E14C0"

    def setUp(self):
        super().setUp()
        self.gpg_dir = os.path.join(self.test_dir, "gpg")
        os.mkdir(self.gpg_dir, mode=0o700)
        # Ignore errors when deleting GNUPGHOME, because of race conditions
        # (e.g. the gpg-agent socket having been deleted). See
        # https://github.com/jelmer/dulwich/issues/1000
        self.addCleanup(shutil.rmtree, self.gpg_dir, ignore_errors=True)
        self.overrideEnv('GNUPGHOME', self.gpg_dir)

    def import_default_key(self):
        subprocess.run(
            ["gpg", "--import"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            input=PorcelainGpgTestCase.DEFAULT_KEY,
            text=True,
        )

    def import_non_default_key(self):
        subprocess.run(
            ["gpg", "--import"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            input=PorcelainGpgTestCase.NON_DEFAULT_KEY,
            text=True,
        )


class ArchiveTests(PorcelainTestCase):
    """Tests for the archive command."""

    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"refs/heads/master"] = c3.id
        out = BytesIO()
        err = BytesIO()
        porcelain.archive(
            self.repo.path, b"refs/heads/master", outstream=out, errstream=err
        )
        self.assertEqual(b"", err.getvalue())
        tf = tarfile.TarFile(fileobj=out)
        self.addCleanup(tf.close)
        self.assertEqual([], tf.getnames())


class UpdateServerInfoTests(PorcelainTestCase):
    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"refs/heads/foo"] = c3.id
        porcelain.update_server_info(self.repo.path)
        self.assertTrue(
            os.path.exists(os.path.join(self.repo.controldir(), "info", "refs"))
        )


class CommitTests(PorcelainTestCase):
    def test_custom_author(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"refs/heads/foo"] = c3.id
        sha = porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

    def test_unicode(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"refs/heads/foo"] = c3.id
        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

    def test_no_verify(self):
        if os.name != "posix":
            self.skipTest("shell hook tests requires POSIX shell")
        self.assertTrue(os.path.exists("/bin/sh"))

        hooks_dir = os.path.join(self.repo.controldir(), "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        self.addCleanup(shutil.rmtree, hooks_dir)

        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )

        hook_fail = "#!/bin/sh\nexit 1"

        # hooks are executed in pre-commit, commit-msg order
        # test commit-msg failure first, then pre-commit failure, then
        # no_verify to skip both hooks
        commit_msg = os.path.join(hooks_dir, "commit-msg")
        with open(commit_msg, "w") as f:
            f.write(hook_fail)
        os.chmod(commit_msg, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        with self.assertRaises(CommitError):
            porcelain.commit(
                self.repo.path,
                message="Some message",
                author="Joe <joe@example.com>",
                committer="Bob <bob@example.com>",
            )

        pre_commit = os.path.join(hooks_dir, "pre-commit")
        with open(pre_commit, "w") as f:
            f.write(hook_fail)
        os.chmod(pre_commit, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        with self.assertRaises(CommitError):
            porcelain.commit(
                self.repo.path,
                message="Some message",
                author="Joe <joe@example.com>",
                committer="Bob <bob@example.com>",
            )

        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
            no_verify=True,
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

    def test_timezone(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"refs/heads/foo"] = c3.id
        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            author_timezone=18000,
            committer="Bob <bob@example.com>",
            commit_timezone=18000,
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

        commit = self.repo.get_object(sha)
        self.assertEqual(commit._author_timezone, 18000)
        self.assertEqual(commit._commit_timezone, 18000)

        self.overrideEnv("GIT_AUTHOR_DATE", "1995-11-20T19:12:08-0501")
        self.overrideEnv("GIT_COMMITTER_DATE", "1995-11-20T19:12:08-0501")

        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

        commit = self.repo.get_object(sha)
        self.assertEqual(commit._author_timezone, -18060)
        self.assertEqual(commit._commit_timezone, -18060)

        self.overrideEnv("GIT_AUTHOR_DATE", None)
        self.overrideEnv("GIT_COMMITTER_DATE", None)

        local_timezone = time.localtime().tm_gmtoff

        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

        commit = self.repo.get_object(sha)
        self.assertEqual(commit._author_timezone, local_timezone)
        self.assertEqual(commit._commit_timezone, local_timezone)


@skipIf(platform.python_implementation() == "PyPy" or sys.platform == "win32", "gpgme not easily available or supported on Windows and PyPy")
class CommitSignTests(PorcelainGpgTestCase):

    def test_default_key(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        cfg = self.repo.get_config()
        cfg.set(("user",), "signingKey", PorcelainGpgTestCase.DEFAULT_KEY_ID)
        self.import_default_key()

        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
            signoff=True,
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

        commit = self.repo.get_object(sha)
        # GPG Signatures aren't deterministic, so we can't do a static assertion.
        commit.verify()
        commit.verify(keyids=[PorcelainGpgTestCase.DEFAULT_KEY_ID])

        self.import_non_default_key()
        self.assertRaises(
            gpg.errors.MissingSignatures,
            commit.verify,
            keyids=[PorcelainGpgTestCase.NON_DEFAULT_KEY_ID],
        )

        commit.committer = b"Alice <alice@example.com>"
        self.assertRaises(
            gpg.errors.BadSignatures,
            commit.verify,
        )

    def test_non_default_key(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        cfg = self.repo.get_config()
        cfg.set(("user",), "signingKey", PorcelainGpgTestCase.DEFAULT_KEY_ID)
        self.import_non_default_key()

        sha = porcelain.commit(
            self.repo.path,
            message="Some message",
            author="Joe <joe@example.com>",
            committer="Bob <bob@example.com>",
            signoff=PorcelainGpgTestCase.NON_DEFAULT_KEY_ID,
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)

        commit = self.repo.get_object(sha)
        # GPG Signatures aren't deterministic, so we can't do a static assertion.
        commit.verify()


class TimezoneTests(PorcelainTestCase):

    def put_envs(self, value):
        self.overrideEnv("GIT_AUTHOR_DATE", value)
        self.overrideEnv("GIT_COMMITTER_DATE", value)

    def fallback(self, value):
        self.put_envs(value)
        self.assertRaises(porcelain.TimezoneFormatError, porcelain.get_user_timezones)

    def test_internal_format(self):
        self.put_envs("0 +0500")
        self.assertTupleEqual((18000, 18000), porcelain.get_user_timezones())

    def test_rfc_2822(self):
        self.put_envs("Mon, 20 Nov 1995 19:12:08 -0500")
        self.assertTupleEqual((-18000, -18000), porcelain.get_user_timezones())

        self.put_envs("Mon, 20 Nov 1995 19:12:08")
        self.assertTupleEqual((0, 0), porcelain.get_user_timezones())

    def test_iso8601(self):
        self.put_envs("1995-11-20T19:12:08-0501")
        self.assertTupleEqual((-18060, -18060), porcelain.get_user_timezones())

        self.put_envs("1995-11-20T19:12:08+0501")
        self.assertTupleEqual((18060, 18060), porcelain.get_user_timezones())

        self.put_envs("1995-11-20T19:12:08-05:01")
        self.assertTupleEqual((-18060, -18060), porcelain.get_user_timezones())

        self.put_envs("1995-11-20 19:12:08-05")
        self.assertTupleEqual((-18000, -18000), porcelain.get_user_timezones())

        # https://github.com/git/git/blob/96b2d4fa927c5055adc5b1d08f10a5d7352e2989/t/t6300-for-each-ref.sh#L128
        self.put_envs("2006-07-03 17:18:44 +0200")
        self.assertTupleEqual((7200, 7200), porcelain.get_user_timezones())

    def test_missing_or_malformed(self):
        # TODO: add more here
        self.fallback("0 + 0500")
        self.fallback("a +0500")

        self.fallback("1995-11-20T19:12:08")
        self.fallback("1995-11-20T19:12:08-05:")

        self.fallback("1995.11.20")
        self.fallback("11/20/1995")
        self.fallback("20.11.1995")

    def test_different_envs(self):
        self.overrideEnv("GIT_AUTHOR_DATE", "0 +0500")
        self.overrideEnv("GIT_COMMITTER_DATE", "0 +0501")
        self.assertTupleEqual((18000, 18060), porcelain.get_user_timezones())

    def test_no_envs(self):
        local_timezone = time.localtime().tm_gmtoff

        self.put_envs("0 +0500")
        self.assertTupleEqual((18000, 18000), porcelain.get_user_timezones())

        self.overrideEnv("GIT_COMMITTER_DATE", None)
        self.assertTupleEqual((18000, local_timezone), porcelain.get_user_timezones())

        self.put_envs("0 +0500")
        self.overrideEnv("GIT_AUTHOR_DATE", None)
        self.assertTupleEqual((local_timezone, 18000), porcelain.get_user_timezones())

        self.put_envs("0 +0500")
        self.overrideEnv("GIT_AUTHOR_DATE", None)
        self.overrideEnv("GIT_COMMITTER_DATE", None)
        self.assertTupleEqual((local_timezone, local_timezone), porcelain.get_user_timezones())


class CleanTests(PorcelainTestCase):
    def put_files(self, tracked, ignored, untracked, empty_dirs):
        """Put the described files in the wd"""
        all_files = tracked | ignored | untracked
        for file_path in all_files:
            abs_path = os.path.join(self.repo.path, file_path)
            # File may need to be written in a dir that doesn't exist yet, so
            # create the parent dir(s) as necessary
            parent_dir = os.path.dirname(abs_path)
            try:
                os.makedirs(parent_dir)
            except FileExistsError:
                pass
            with open(abs_path, "w") as f:
                f.write("")

        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.writelines(ignored)

        for dir_path in empty_dirs:
            os.mkdir(os.path.join(self.repo.path, "empty_dir"))

        files_to_add = [os.path.join(self.repo.path, t) for t in tracked]
        porcelain.add(repo=self.repo.path, paths=files_to_add)
        porcelain.commit(repo=self.repo.path, message="init commit")

    def assert_wd(self, expected_paths):
        """Assert paths of files and dirs in wd are same as expected_paths"""
        control_dir_rel = os.path.relpath(self.repo._controldir, self.repo.path)

        # normalize paths to simplify comparison across platforms
        found_paths = {
            os.path.normpath(p)
            for p in flat_walk_dir(self.repo.path)
            if not p.split(os.sep)[0] == control_dir_rel
        }
        norm_expected_paths = {os.path.normpath(p) for p in expected_paths}
        self.assertEqual(found_paths, norm_expected_paths)

    def test_from_root(self):
        self.put_files(
            tracked={"tracked_file", "tracked_dir/tracked_file", ".gitignore"},
            ignored={"ignored_file"},
            untracked={
                "untracked_file",
                "tracked_dir/untracked_dir/untracked_file",
                "untracked_dir/untracked_dir/untracked_file",
            },
            empty_dirs={"empty_dir"},
        )

        porcelain.clean(repo=self.repo.path, target_dir=self.repo.path)

        self.assert_wd(
            {
                "tracked_file",
                "tracked_dir/tracked_file",
                ".gitignore",
                "ignored_file",
                "tracked_dir",
            }
        )

    def test_from_subdir(self):
        self.put_files(
            tracked={"tracked_file", "tracked_dir/tracked_file", ".gitignore"},
            ignored={"ignored_file"},
            untracked={
                "untracked_file",
                "tracked_dir/untracked_dir/untracked_file",
                "untracked_dir/untracked_dir/untracked_file",
            },
            empty_dirs={"empty_dir"},
        )

        porcelain.clean(
            repo=self.repo,
            target_dir=os.path.join(self.repo.path, "untracked_dir"),
        )

        self.assert_wd(
            {
                "tracked_file",
                "tracked_dir/tracked_file",
                ".gitignore",
                "ignored_file",
                "untracked_file",
                "tracked_dir/untracked_dir/untracked_file",
                "empty_dir",
                "untracked_dir",
                "tracked_dir",
                "tracked_dir/untracked_dir",
            }
        )


class CloneTests(PorcelainTestCase):
    def test_simple_local(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1], [2, 1], [3, 1, 2]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f1_1)],
            2: [(b"f1", f1_1), (b"f2", f1_1)],
            3: [(b"f1", f1_1), (b"f2", f1_1)],
        }

        c1, c2, c3 = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c3.id
        self.repo.refs[b"refs/tags/foo"] = c3.id
        target_path = tempfile.mkdtemp()
        errstream = BytesIO()
        self.addCleanup(shutil.rmtree, target_path)
        r = porcelain.clone(
            self.repo.path, target_path, checkout=False, errstream=errstream
        )
        self.addCleanup(r.close)
        self.assertEqual(r.path, target_path)
        target_repo = Repo(target_path)
        self.assertEqual(0, len(target_repo.open_index()))
        self.assertEqual(c3.id, target_repo.refs[b"refs/tags/foo"])
        self.assertNotIn(b"f1", os.listdir(target_path))
        self.assertNotIn(b"f2", os.listdir(target_path))
        c = r.get_config()
        encoded_path = self.repo.path
        if not isinstance(encoded_path, bytes):
            encoded_path = encoded_path.encode("utf-8")
        self.assertEqual(encoded_path, c.get((b"remote", b"origin"), b"url"))
        self.assertEqual(
            b"+refs/heads/*:refs/remotes/origin/*",
            c.get((b"remote", b"origin"), b"fetch"),
        )

    def test_simple_local_with_checkout(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1], [2, 1], [3, 1, 2]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f1_1)],
            2: [(b"f1", f1_1), (b"f2", f1_1)],
            3: [(b"f1", f1_1), (b"f2", f1_1)],
        }

        c1, c2, c3 = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c3.id
        target_path = tempfile.mkdtemp()
        errstream = BytesIO()
        self.addCleanup(shutil.rmtree, target_path)
        with porcelain.clone(
            self.repo.path, target_path, checkout=True, errstream=errstream
        ) as r:
            self.assertEqual(r.path, target_path)
        with Repo(target_path) as r:
            self.assertEqual(r.head(), c3.id)
        self.assertIn("f1", os.listdir(target_path))
        self.assertIn("f2", os.listdir(target_path))

    def test_bare_local_with_checkout(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1], [2, 1], [3, 1, 2]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f1_1)],
            2: [(b"f1", f1_1), (b"f2", f1_1)],
            3: [(b"f1", f1_1), (b"f2", f1_1)],
        }

        c1, c2, c3 = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c3.id
        target_path = tempfile.mkdtemp()
        errstream = BytesIO()
        self.addCleanup(shutil.rmtree, target_path)
        with porcelain.clone(
            self.repo.path, target_path, bare=True, errstream=errstream
        ) as r:
            self.assertEqual(r.path, target_path)
        with Repo(target_path) as r:
            r.head()
            self.assertRaises(NoIndexPresent, r.open_index)
        self.assertNotIn(b"f1", os.listdir(target_path))
        self.assertNotIn(b"f2", os.listdir(target_path))

    def test_no_checkout_with_bare(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1]]
        trees = {1: [(b"f1", f1_1), (b"f2", f1_1)]}

        (c1,) = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c1.id
        self.repo.refs[b"HEAD"] = c1.id
        target_path = tempfile.mkdtemp()
        errstream = BytesIO()
        self.addCleanup(shutil.rmtree, target_path)
        self.assertRaises(
            porcelain.Error,
            porcelain.clone,
            self.repo.path,
            target_path,
            checkout=True,
            bare=True,
            errstream=errstream,
        )

    def test_no_head_no_checkout(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1]]
        trees = {1: [(b"f1", f1_1), (b"f2", f1_1)]}

        (c1,) = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c1.id
        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        errstream = BytesIO()
        r = porcelain.clone(
            self.repo.path, target_path, checkout=True, errstream=errstream
        )
        r.close()

    def test_no_head_no_checkout_outstream_errstream_autofallback(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1]]
        trees = {1: [(b"f1", f1_1), (b"f2", f1_1)]}

        (c1,) = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c1.id
        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        errstream = porcelain.NoneStream()
        r = porcelain.clone(
            self.repo.path, target_path, checkout=True, errstream=errstream
        )
        r.close()

    def test_source_broken(self):
        with tempfile.TemporaryDirectory() as parent:
            target_path = os.path.join(parent, "target")
            self.assertRaises(
                Exception, porcelain.clone, "/nonexistent/repo", target_path
            )
            self.assertFalse(os.path.exists(target_path))

    def test_fetch_symref(self):
        f1_1 = make_object(Blob, data=b"f1")
        trees = {1: [(b"f1", f1_1), (b"f2", f1_1)]}
        [c1] = build_commit_graph(self.repo.object_store, [[1]], trees)
        self.repo.refs.set_symbolic_ref(b"HEAD", b"refs/heads/else")
        self.repo.refs[b"refs/heads/else"] = c1.id
        target_path = tempfile.mkdtemp()
        errstream = BytesIO()
        self.addCleanup(shutil.rmtree, target_path)
        r = porcelain.clone(
            self.repo.path, target_path, checkout=False, errstream=errstream
        )
        self.addCleanup(r.close)
        self.assertEqual(r.path, target_path)
        target_repo = Repo(target_path)
        self.assertEqual(0, len(target_repo.open_index()))
        self.assertEqual(c1.id, target_repo.refs[b"refs/heads/else"])
        self.assertEqual(c1.id, target_repo.refs[b"HEAD"])
        self.assertEqual(
            {b"HEAD": b"refs/heads/else", b"refs/remotes/origin/HEAD": b"refs/remotes/origin/else"},
            target_repo.refs.get_symrefs(),
        )

    def test_detached_head(self):
        f1_1 = make_object(Blob, data=b"f1")
        commit_spec = [[1], [2, 1], [3, 1, 2]]
        trees = {
            1: [(b"f1", f1_1), (b"f2", f1_1)],
            2: [(b"f1", f1_1), (b"f2", f1_1)],
            3: [(b"f1", f1_1), (b"f2", f1_1)],
        }

        c1, c2, c3 = build_commit_graph(self.repo.object_store, commit_spec, trees)
        self.repo.refs[b"refs/heads/master"] = c2.id
        self.repo.refs.remove_if_equals(b"HEAD", None)
        self.repo.refs[b"HEAD"] = c3.id
        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        errstream = porcelain.NoneStream()
        with porcelain.clone(
            self.repo.path, target_path, checkout=True, errstream=errstream
        ) as r:
            self.assertEqual(c3.id, r.refs[b"HEAD"])


class InitTests(TestCase):
    def test_non_bare(self):
        repo_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo_dir)
        porcelain.init(repo_dir)

    def test_bare(self):
        repo_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo_dir)
        porcelain.init(repo_dir, bare=True)


class AddTests(PorcelainTestCase):
    def test_add_default_paths(self):
        # create a file for initial commit
        fullpath = os.path.join(self.repo.path, "blah")
        with open(fullpath, "w") as f:
            f.write("\n")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test",
            author=b"test <email>",
            committer=b"test <email>",
        )

        # Add a second test file and a file in a directory
        with open(os.path.join(self.repo.path, "foo"), "w") as f:
            f.write("\n")
        os.mkdir(os.path.join(self.repo.path, "adir"))
        with open(os.path.join(self.repo.path, "adir", "afile"), "w") as f:
            f.write("\n")
        cwd = os.getcwd()
        try:
            os.chdir(self.repo.path)
            self.assertEqual({"foo", "blah", "adir", ".git"}, set(os.listdir(".")))
            self.assertEqual(
                (["foo", os.path.join("adir", "afile")], set()),
                porcelain.add(self.repo.path),
            )
        finally:
            os.chdir(cwd)

        # Check that foo was added and nothing in .git was modified
        index = self.repo.open_index()
        self.assertEqual(sorted(index), [b"adir/afile", b"blah", b"foo"])

    def test_add_default_paths_subdir(self):
        os.mkdir(os.path.join(self.repo.path, "foo"))
        with open(os.path.join(self.repo.path, "blah"), "w") as f:
            f.write("\n")
        with open(os.path.join(self.repo.path, "foo", "blie"), "w") as f:
            f.write("\n")

        cwd = os.getcwd()
        try:
            os.chdir(os.path.join(self.repo.path, "foo"))
            porcelain.add(repo=self.repo.path)
            porcelain.commit(
                repo=self.repo.path,
                message=b"test",
                author=b"test <email>",
                committer=b"test <email>",
            )
        finally:
            os.chdir(cwd)

        index = self.repo.open_index()
        self.assertEqual(sorted(index), [b"foo/blie"])

    def test_add_file(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(self.repo.path, paths=[fullpath])
        self.assertIn(b"foo", self.repo.open_index())

    def test_add_ignored(self):
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("foo\nsubdir/")
        with open(os.path.join(self.repo.path, "foo"), "w") as f:
            f.write("BAR")
        with open(os.path.join(self.repo.path, "bar"), "w") as f:
            f.write("BAR")
        os.mkdir(os.path.join(self.repo.path, "subdir"))
        with open(os.path.join(self.repo.path, "subdir", "baz"), "w") as f:
            f.write("BAZ")
        (added, ignored) = porcelain.add(
            self.repo.path,
            paths=[
                os.path.join(self.repo.path, "foo"),
                os.path.join(self.repo.path, "bar"),
                os.path.join(self.repo.path, "subdir"),
            ],
        )
        self.assertIn(b"bar", self.repo.open_index())
        self.assertEqual({"bar"}, set(added))
        self.assertEqual({"foo", os.path.join("subdir", "")}, ignored)

    def test_add_file_absolute_path(self):
        # Absolute paths are (not yet) supported
        with open(os.path.join(self.repo.path, "foo"), "w") as f:
            f.write("BAR")
        porcelain.add(self.repo, paths=[os.path.join(self.repo.path, "foo")])
        self.assertIn(b"foo", self.repo.open_index())

    def test_add_not_in_repo(self):
        with open(os.path.join(self.test_dir, "foo"), "w") as f:
            f.write("BAR")
        self.assertRaises(
            ValueError,
            porcelain.add,
            self.repo,
            paths=[os.path.join(self.test_dir, "foo")],
        )
        self.assertRaises(
            (ValueError, FileNotFoundError),
            porcelain.add,
            self.repo,
            paths=["../foo"],
        )
        self.assertEqual([], list(self.repo.open_index()))

    def test_add_file_clrf_conversion(self):
        # Set the right configuration to the repo
        c = self.repo.get_config()
        c.set("core", "autocrlf", "input")
        c.write_to_path()

        # Add a file with CRLF line-ending
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "wb") as f:
            f.write(b"line1\r\nline2")
        porcelain.add(self.repo.path, paths=[fullpath])

        # The line-endings should have been converted to LF
        index = self.repo.open_index()
        self.assertIn(b"foo", index)

        entry = index[b"foo"]
        blob = self.repo[entry.sha]
        self.assertEqual(blob.data, b"line1\nline2")


class RemoveTests(PorcelainTestCase):
    def test_remove_file(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(self.repo.path, paths=[fullpath])
        porcelain.commit(
            repo=self.repo,
            message=b"test",
            author=b"test <email>",
            committer=b"test <email>",
        )
        self.assertTrue(os.path.exists(os.path.join(self.repo.path, "foo")))
        cwd = os.getcwd()
        try:
            os.chdir(self.repo.path)
            porcelain.remove(self.repo.path, paths=["foo"])
        finally:
            os.chdir(cwd)
        self.assertFalse(os.path.exists(os.path.join(self.repo.path, "foo")))

    def test_remove_file_staged(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        cwd = os.getcwd()
        try:
            os.chdir(self.repo.path)
            porcelain.add(self.repo.path, paths=[fullpath])
            self.assertRaises(Exception, porcelain.rm, self.repo.path, paths=["foo"])
        finally:
            os.chdir(cwd)

    def test_remove_file_removed_on_disk(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(self.repo.path, paths=[fullpath])
        cwd = os.getcwd()
        try:
            os.chdir(self.repo.path)
            os.remove(fullpath)
            porcelain.remove(self.repo.path, paths=["foo"])
        finally:
            os.chdir(cwd)
        self.assertFalse(os.path.exists(os.path.join(self.repo.path, "foo")))


class LogTests(PorcelainTestCase):
    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        outstream = StringIO()
        porcelain.log(self.repo.path, outstream=outstream)
        self.assertEqual(3, outstream.getvalue().count("-" * 50))

    def test_max_entries(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        outstream = StringIO()
        porcelain.log(self.repo.path, outstream=outstream, max_entries=1)
        self.assertEqual(1, outstream.getvalue().count("-" * 50))


class ShowTests(PorcelainTestCase):
    def test_nolist(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        outstream = StringIO()
        porcelain.show(self.repo.path, objects=c3.id, outstream=outstream)
        self.assertTrue(outstream.getvalue().startswith("-" * 50))

    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        outstream = StringIO()
        porcelain.show(self.repo.path, objects=[c3.id], outstream=outstream)
        self.assertTrue(outstream.getvalue().startswith("-" * 50))

    def test_blob(self):
        b = Blob.from_string(b"The Foo\n")
        self.repo.object_store.add_object(b)
        outstream = StringIO()
        porcelain.show(self.repo.path, objects=[b.id], outstream=outstream)
        self.assertEqual(outstream.getvalue(), "The Foo\n")

    def test_commit_no_parent(self):
        a = Blob.from_string(b"The Foo\n")
        ta = Tree()
        ta.add(b"somename", 0o100644, a.id)
        ca = make_commit(tree=ta.id)
        self.repo.object_store.add_objects([(a, None), (ta, None), (ca, None)])
        outstream = StringIO()
        porcelain.show(self.repo.path, objects=[ca.id], outstream=outstream)
        self.assertMultiLineEqual(
            outstream.getvalue(),
            """\
--------------------------------------------------
commit: 344da06c1bb85901270b3e8875c988a027ec087d
Author: Test Author <test@nodomain.com>
Committer: Test Committer <test@nodomain.com>
Date:   Fri Jan 01 2010 00:00:00 +0000

Test message.

diff --git a/somename b/somename
new file mode 100644
index 0000000..ea5c7bf
--- /dev/null
+++ b/somename
@@ -0,0 +1 @@
+The Foo
""",
        )

    def test_tag(self):
        a = Blob.from_string(b"The Foo\n")
        ta = Tree()
        ta.add(b"somename", 0o100644, a.id)
        ca = make_commit(tree=ta.id)
        self.repo.object_store.add_objects([(a, None), (ta, None), (ca, None)])
        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
            objectish=ca.id,
            tag_time=1552854211,
            tag_timezone=0,
        )
        outstream = StringIO()
        porcelain.show(self.repo, objects=[b"refs/tags/tryme"], outstream=outstream)
        self.maxDiff = None
        self.assertMultiLineEqual(
            outstream.getvalue(),
            """\
Tagger: foo <foo@bar.com>
Date:   Sun Mar 17 2019 20:23:31 +0000

bar

--------------------------------------------------
commit: 344da06c1bb85901270b3e8875c988a027ec087d
Author: Test Author <test@nodomain.com>
Committer: Test Committer <test@nodomain.com>
Date:   Fri Jan 01 2010 00:00:00 +0000

Test message.

diff --git a/somename b/somename
new file mode 100644
index 0000000..ea5c7bf
--- /dev/null
+++ b/somename
@@ -0,0 +1 @@
+The Foo
""",
        )

    def test_commit_with_change(self):
        a = Blob.from_string(b"The Foo\n")
        ta = Tree()
        ta.add(b"somename", 0o100644, a.id)
        ca = make_commit(tree=ta.id)
        b = Blob.from_string(b"The Bar\n")
        tb = Tree()
        tb.add(b"somename", 0o100644, b.id)
        cb = make_commit(tree=tb.id, parents=[ca.id])
        self.repo.object_store.add_objects(
            [
                (a, None),
                (b, None),
                (ta, None),
                (tb, None),
                (ca, None),
                (cb, None),
            ]
        )
        outstream = StringIO()
        porcelain.show(self.repo.path, objects=[cb.id], outstream=outstream)
        self.assertMultiLineEqual(
            outstream.getvalue(),
            """\
--------------------------------------------------
commit: 2c6b6c9cb72c130956657e1fdae58e5b103744fa
Author: Test Author <test@nodomain.com>
Committer: Test Committer <test@nodomain.com>
Date:   Fri Jan 01 2010 00:00:00 +0000

Test message.

diff --git a/somename b/somename
index ea5c7bf..fd38bcb 100644
--- a/somename
+++ b/somename
@@ -1 +1 @@
-The Foo
+The Bar
""",
        )


class SymbolicRefTests(PorcelainTestCase):
    def test_set_wrong_symbolic_ref(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        self.assertRaises(
            porcelain.Error, porcelain.symbolic_ref, self.repo.path, b"foobar"
        )

    def test_set_force_wrong_symbolic_ref(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        porcelain.symbolic_ref(self.repo.path, b"force_foobar", force=True)

        # test if we actually changed the file
        with self.repo.get_named_file("HEAD") as f:
            new_ref = f.read()
        self.assertEqual(new_ref, b"ref: refs/heads/force_foobar\n")

    def test_set_symbolic_ref(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        porcelain.symbolic_ref(self.repo.path, b"master")

    def test_set_symbolic_ref_other_than_master(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store,
            [[1], [2, 1], [3, 1, 2]],
            attrs=dict(refs="develop"),
        )
        self.repo.refs[b"HEAD"] = c3.id
        self.repo.refs[b"refs/heads/develop"] = c3.id

        porcelain.symbolic_ref(self.repo.path, b"develop")

        # test if we actually changed the file
        with self.repo.get_named_file("HEAD") as f:
            new_ref = f.read()
        self.assertEqual(new_ref, b"ref: refs/heads/develop\n")


class DiffTreeTests(PorcelainTestCase):
    def test_empty(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        outstream = BytesIO()
        porcelain.diff_tree(self.repo.path, c2.tree, c3.tree, outstream=outstream)
        self.assertEqual(outstream.getvalue(), b"")


class CommitTreeTests(PorcelainTestCase):
    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        b = Blob()
        b.data = b"foo the bar"
        t = Tree()
        t.add(b"somename", 0o100644, b.id)
        self.repo.object_store.add_object(t)
        self.repo.object_store.add_object(b)
        sha = porcelain.commit_tree(
            self.repo.path,
            t.id,
            message=b"Withcommit.",
            author=b"Joe <joe@example.com>",
            committer=b"Jane <jane@example.com>",
        )
        self.assertIsInstance(sha, bytes)
        self.assertEqual(len(sha), 40)


class RevListTests(PorcelainTestCase):
    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        outstream = BytesIO()
        porcelain.rev_list(self.repo.path, [c3.id], outstream=outstream)
        self.assertEqual(
            c3.id + b"\n" + c2.id + b"\n" + c1.id + b"\n", outstream.getvalue()
        )


@skipIf(platform.python_implementation() == "PyPy" or sys.platform == "win32", "gpgme not easily available or supported on Windows and PyPy")
class TagCreateSignTests(PorcelainGpgTestCase):

    def test_default_key(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        cfg = self.repo.get_config()
        cfg.set(("user",), "signingKey", PorcelainGpgTestCase.DEFAULT_KEY_ID)
        self.import_default_key()

        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
            sign=True,
        )

        tags = self.repo.refs.as_dict(b"refs/tags")
        self.assertEqual(list(tags.keys()), [b"tryme"])
        tag = self.repo[b"refs/tags/tryme"]
        self.assertIsInstance(tag, Tag)
        self.assertEqual(b"foo <foo@bar.com>", tag.tagger)
        self.assertEqual(b"bar\n", tag.message)
        self.assertRecentTimestamp(tag.tag_time)
        tag = self.repo[b'refs/tags/tryme']
        # GPG Signatures aren't deterministic, so we can't do a static assertion.
        tag.verify()
        tag.verify(keyids=[PorcelainGpgTestCase.DEFAULT_KEY_ID])

        self.import_non_default_key()
        self.assertRaises(
            gpg.errors.MissingSignatures,
            tag.verify,
            keyids=[PorcelainGpgTestCase.NON_DEFAULT_KEY_ID],
        )

        tag._chunked_text = [b"bad data", tag._signature]
        self.assertRaises(
            gpg.errors.BadSignatures,
            tag.verify,
        )

    def test_non_default_key(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        cfg = self.repo.get_config()
        cfg.set(("user",), "signingKey", PorcelainGpgTestCase.DEFAULT_KEY_ID)
        self.import_non_default_key()

        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
            sign=PorcelainGpgTestCase.NON_DEFAULT_KEY_ID,
        )

        tags = self.repo.refs.as_dict(b"refs/tags")
        self.assertEqual(list(tags.keys()), [b"tryme"])
        tag = self.repo[b"refs/tags/tryme"]
        self.assertIsInstance(tag, Tag)
        self.assertEqual(b"foo <foo@bar.com>", tag.tagger)
        self.assertEqual(b"bar\n", tag.message)
        self.assertRecentTimestamp(tag.tag_time)
        tag = self.repo[b'refs/tags/tryme']
        # GPG Signatures aren't deterministic, so we can't do a static assertion.
        tag.verify()


class TagCreateTests(PorcelainTestCase):

    def test_annotated(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
        )

        tags = self.repo.refs.as_dict(b"refs/tags")
        self.assertEqual(list(tags.keys()), [b"tryme"])
        tag = self.repo[b"refs/tags/tryme"]
        self.assertIsInstance(tag, Tag)
        self.assertEqual(b"foo <foo@bar.com>", tag.tagger)
        self.assertEqual(b"bar\n", tag.message)
        self.assertRecentTimestamp(tag.tag_time)

    def test_unannotated(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        porcelain.tag_create(self.repo.path, b"tryme", annotated=False)

        tags = self.repo.refs.as_dict(b"refs/tags")
        self.assertEqual(list(tags.keys()), [b"tryme"])
        self.repo[b"refs/tags/tryme"]
        self.assertEqual(list(tags.values()), [self.repo.head()])

    def test_unannotated_unicode(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id

        porcelain.tag_create(self.repo.path, "tryme", annotated=False)

        tags = self.repo.refs.as_dict(b"refs/tags")
        self.assertEqual(list(tags.keys()), [b"tryme"])
        self.repo[b"refs/tags/tryme"]
        self.assertEqual(list(tags.values()), [self.repo.head()])


class TagListTests(PorcelainTestCase):
    def test_empty(self):
        tags = porcelain.tag_list(self.repo.path)
        self.assertEqual([], tags)

    def test_simple(self):
        self.repo.refs[b"refs/tags/foo"] = b"aa" * 20
        self.repo.refs[b"refs/tags/bar/bla"] = b"bb" * 20
        tags = porcelain.tag_list(self.repo.path)

        self.assertEqual([b"bar/bla", b"foo"], tags)


class TagDeleteTests(PorcelainTestCase):
    def test_simple(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.tag_create(self.repo, b"foo")
        self.assertIn(b"foo", porcelain.tag_list(self.repo))
        porcelain.tag_delete(self.repo, b"foo")
        self.assertNotIn(b"foo", porcelain.tag_list(self.repo))


class ResetTests(PorcelainTestCase):
    def test_hard_head(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )

        with open(os.path.join(self.repo.path, "foo"), "wb") as f:
            f.write(b"OOH")

        porcelain.reset(self.repo, "hard", b"HEAD")

        index = self.repo.open_index()
        changes = list(
            tree_changes(
                self.repo,
                index.commit(self.repo.object_store),
                self.repo[b"HEAD"].tree,
            )
        )

        self.assertEqual([], changes)

    def test_hard_commit(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(self.repo.path, paths=[fullpath])
        sha = porcelain.commit(
            self.repo.path,
            message=b"Some message",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )

        with open(fullpath, "wb") as f:
            f.write(b"BAZ")
        porcelain.add(self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some other message",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )

        porcelain.reset(self.repo, "hard", sha)

        index = self.repo.open_index()
        changes = list(
            tree_changes(
                self.repo,
                index.commit(self.repo.object_store),
                self.repo[sha].tree,
            )
        )

        self.assertEqual([], changes)


class ResetFileTests(PorcelainTestCase):

    def test_reset_modify_file_to_commit(self):
        file = 'foo'
        full_path = os.path.join(self.repo.path, file)

        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self.repo, paths=[full_path])
        sha = porcelain.commit(
            self.repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        with open(full_path, 'a') as f:
            f.write('something new')
        porcelain.reset_file(self.repo, file, target=sha)

        with open(full_path) as f:
            self.assertEqual('hello', f.read())

    def test_reset_remove_file_to_commit(self):
        file = 'foo'
        full_path = os.path.join(self.repo.path, file)

        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self.repo, paths=[full_path])
        sha = porcelain.commit(
            self.repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        os.remove(full_path)
        porcelain.reset_file(self.repo, file, target=sha)

        with open(full_path) as f:
            self.assertEqual('hello', f.read())

    def test_resetfile_with_dir(self):
        os.mkdir(os.path.join(self.repo.path, 'new_dir'))
        full_path = os.path.join(self.repo.path, 'new_dir', 'foo')

        with open(full_path, 'w') as f:
            f.write('hello')
        porcelain.add(self.repo, paths=[full_path])
        sha = porcelain.commit(
            self.repo,
            message=b"unitest",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        with open(full_path, 'a') as f:
            f.write('something new')
        porcelain.commit(
            self.repo,
            message=b"unitest 2",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        porcelain.reset_file(self.repo, os.path.join('new_dir', 'foo'), target=sha)

        with open(full_path) as f:
            self.assertEqual('hello', f.read())


def _commit_file_with_content(repo, filename, content):
    file_path = os.path.join(repo.path, filename)

    with open(file_path, 'w') as f:
        f.write(content)
    porcelain.add(repo, paths=[file_path])
    sha = porcelain.commit(
        repo,
        message=b"add " + filename.encode(),
        committer=b"Jane <jane@example.com>",
        author=b"John <john@example.com>",
    )

    return sha, file_path


class CheckoutTests(PorcelainTestCase):

    def setUp(self):
        super().setUp()
        self._sha, self._foo_path = _commit_file_with_content(self.repo, 'foo', 'hello\n')
        porcelain.branch_create(self.repo, 'uni')

    def test_checkout_to_existing_branch(self):
        self.assertEqual(b"master", porcelain.active_branch(self.repo))
        porcelain.checkout_branch(self.repo, b'uni')
        self.assertEqual(b"uni", porcelain.active_branch(self.repo))

    def test_checkout_to_non_existing_branch(self):
        self.assertEqual(b"master", porcelain.active_branch(self.repo))

        with self.assertRaises(KeyError):
            porcelain.checkout_branch(self.repo, b'bob')

        self.assertEqual(b"master", porcelain.active_branch(self.repo))

    def test_checkout_to_branch_with_modified_files(self):
        with open(self._foo_path, 'a') as f:
            f.write('new message\n')
        porcelain.add(self.repo, paths=[self._foo_path])

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': [b"foo"]}, [], []], status)

        # Both branches have file 'foo' checkout should be fine.
        porcelain.checkout_branch(self.repo, b'uni')
        self.assertEqual(b"uni", porcelain.active_branch(self.repo))

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': [b"foo"]}, [], []], status)

    def test_checkout_with_deleted_files(self):
        porcelain.remove(self.repo.path, [os.path.join(self.repo.path, 'foo')])
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [b'foo'], 'modify': []}, [], []], status)

        # Both branches have file 'foo' checkout should be fine.
        porcelain.checkout_branch(self.repo, b'uni')
        self.assertEqual(b"uni", porcelain.active_branch(self.repo))

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [b"foo"], 'modify': []}, [], []], status)

    def test_checkout_to_branch_with_added_files(self):
        file_path = os.path.join(self.repo.path, 'bar')

        with open(file_path, 'w') as f:
            f.write('bar content\n')
        porcelain.add(self.repo, paths=[file_path])
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [b'bar'], 'delete': [], 'modify': []}, [], []], status)

        # Both branches have file 'foo' checkout should be fine.
        porcelain.checkout_branch(self.repo, b'uni')
        self.assertEqual(b'uni', porcelain.active_branch(self.repo))

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [b'bar'], 'delete': [], 'modify': []}, [], []], status)

    def test_checkout_to_branch_with_modified_file_not_present(self):
        # Commit a new file that the other branch doesn't have.
        _, nee_path = _commit_file_with_content(self.repo, 'nee', 'Good content\n')

        # Modify the file the other branch doesn't have.
        with open(nee_path, 'a') as f:
            f.write('bar content\n')
        porcelain.add(self.repo, paths=[nee_path])
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': [b'nee']}, [], []], status)

        # 'uni' branch doesn't have 'nee' and it has been modified, should result in the checkout being aborted.
        with self.assertRaises(CheckoutError):
            porcelain.checkout_branch(self.repo, b'uni')

        self.assertEqual(b'master', porcelain.active_branch(self.repo))

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': [b'nee']}, [], []], status)

    def test_checkout_to_branch_with_modified_file_not_present_forced(self):
        # Commit a new file that the other branch doesn't have.
        _, nee_path = _commit_file_with_content(self.repo, 'nee', 'Good content\n')

        # Modify the file the other branch doesn't have.
        with open(nee_path, 'a') as f:
            f.write('bar content\n')
        porcelain.add(self.repo, paths=[nee_path])
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': [b'nee']}, [], []], status)

        # 'uni' branch doesn't have 'nee' and it has been modified, but we force to reset the entire index.
        porcelain.checkout_branch(self.repo, b'uni', force=True)

        self.assertEqual(b'uni', porcelain.active_branch(self.repo))

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

    def test_checkout_to_branch_with_unstaged_files(self):
        # Edit `foo`.
        with open(self._foo_path, 'a') as f:
            f.write('new message')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [b'foo'], []], status)

        porcelain.checkout_branch(self.repo, b'uni')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [b'foo'], []], status)

    def test_checkout_to_branch_with_untracked_files(self):
        with open(os.path.join(self.repo.path, 'neu'), 'a') as f:
            f.write('new message\n')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], ['neu']], status)

        porcelain.checkout_branch(self.repo, b'uni')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], ['neu']], status)

    def test_checkout_to_branch_with_new_files(self):
        porcelain.checkout_branch(self.repo, b'uni')
        sub_directory = os.path.join(self.repo.path, 'sub1')
        os.mkdir(sub_directory)
        for index in range(5):
            _commit_file_with_content(self.repo, 'new_file_' + str(index + 1), "Some content\n")
            _commit_file_with_content(self.repo, os.path.join('sub1', 'new_file_' + str(index + 10)), "Good content\n")

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        porcelain.checkout_branch(self.repo, b'master')
        self.assertEqual(b"master", porcelain.active_branch(self.repo))
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        porcelain.checkout_branch(self.repo, b'uni')
        self.assertEqual(b"uni", porcelain.active_branch(self.repo))
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

    def test_checkout_to_branch_with_file_in_sub_directory(self):
        sub_directory = os.path.join(self.repo.path, 'sub1', 'sub2')
        os.makedirs(sub_directory)

        sub_directory_file = os.path.join(sub_directory, 'neu')
        with open(sub_directory_file, 'w') as f:
            f.write('new message\n')

        porcelain.add(self.repo, paths=[sub_directory_file])
        porcelain.commit(
            self.repo,
            message=b"add " + sub_directory_file.encode(),
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        self.assertTrue(os.path.isdir(sub_directory))
        self.assertTrue(os.path.isdir(os.path.dirname(sub_directory)))

        porcelain.checkout_branch(self.repo, b'uni')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        self.assertFalse(os.path.isdir(sub_directory))
        self.assertFalse(os.path.isdir(os.path.dirname(sub_directory)))

        porcelain.checkout_branch(self.repo, b'master')

        self.assertTrue(os.path.isdir(sub_directory))
        self.assertTrue(os.path.isdir(os.path.dirname(sub_directory)))

    def test_checkout_to_branch_with_multiple_files_in_sub_directory(self):
        sub_directory = os.path.join(self.repo.path, 'sub1', 'sub2')
        os.makedirs(sub_directory)

        sub_directory_file_1 = os.path.join(sub_directory, 'neu')
        with open(sub_directory_file_1, 'w') as f:
            f.write('new message\n')

        sub_directory_file_2 = os.path.join(sub_directory, 'gus')
        with open(sub_directory_file_2, 'w') as f:
            f.write('alternative message\n')

        porcelain.add(self.repo, paths=[sub_directory_file_1, sub_directory_file_2])
        porcelain.commit(
            self.repo,
            message=b"add files neu and gus.",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )
        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        self.assertTrue(os.path.isdir(sub_directory))
        self.assertTrue(os.path.isdir(os.path.dirname(sub_directory)))

        porcelain.checkout_branch(self.repo, b'uni')

        status = list(porcelain.status(self.repo))
        self.assertEqual([{'add': [], 'delete': [], 'modify': []}, [], []], status)

        self.assertFalse(os.path.isdir(sub_directory))
        self.assertFalse(os.path.isdir(os.path.dirname(sub_directory)))

    def _commit_something_wrong(self):
        with open(self._foo_path, 'a') as f:
            f.write('something wrong')

        porcelain.add(self.repo, paths=[self._foo_path])
        return porcelain.commit(
            self.repo,
            message=b"I may added something wrong",
            committer=b"Jane <jane@example.com>",
            author=b"John <john@example.com>",
        )

    def test_checkout_to_commit_sha(self):
        self._commit_something_wrong()

        porcelain.checkout_branch(self.repo, self._sha)
        self.assertEqual(self._sha, self.repo.head())

    def test_checkout_to_head(self):
        new_sha = self._commit_something_wrong()

        porcelain.checkout_branch(self.repo, b"HEAD")
        self.assertEqual(new_sha, self.repo.head())

    def _checkout_remote_branch(self):
        errstream = BytesIO()
        outstream = BytesIO()

        porcelain.commit(
            repo=self.repo.path,
            message=b"init",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.clone(
            self.repo.path, target=clone_path, errstream=errstream
        )
        try:
            self.assertEqual(target_repo[b"HEAD"], self.repo[b"HEAD"])
        finally:
            target_repo.close()

        # create a second file to be pushed back to origin
        handle, fullpath = tempfile.mkstemp(dir=clone_path)
        os.close(handle)
        porcelain.add(repo=clone_path, paths=[fullpath])
        porcelain.commit(
            repo=clone_path,
            message=b"push",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup a non-checked out branch in the remote
        refs_path = b"refs/heads/foo"
        new_id = self.repo[b"HEAD"].id
        self.assertNotEqual(new_id, ZERO_SHA)
        self.repo.refs[refs_path] = new_id

        # Push to the remote
        porcelain.push(
            clone_path,
            "origin",
            b"HEAD:" + refs_path,
            outstream=outstream,
            errstream=errstream,
        )

        self.assertEqual(
            target_repo.refs[b"refs/remotes/origin/foo"],
            target_repo.refs[b"HEAD"],
        )

        porcelain.checkout_branch(target_repo, b"origin/foo")
        original_id = target_repo[b"HEAD"].id
        uni_id = target_repo[b"refs/remotes/origin/uni"].id

        expected_refs = {
            b"HEAD": original_id,
            b"refs/heads/master": original_id,
            b"refs/heads/foo": original_id,
            b"refs/remotes/origin/foo": original_id,
            b"refs/remotes/origin/uni": uni_id,
            b"refs/remotes/origin/HEAD": new_id,
            b"refs/remotes/origin/master": new_id,
        }
        self.assertEqual(expected_refs, target_repo.get_refs())

        return target_repo

    def test_checkout_remote_branch(self):
        repo = self._checkout_remote_branch()
        repo.close()

    def test_checkout_remote_branch_then_master_then_remote_branch_again(self):
        target_repo = self._checkout_remote_branch()
        self.assertEqual(b"foo", porcelain.active_branch(target_repo))
        _commit_file_with_content(target_repo, 'bar', 'something\n')
        self.assertTrue(os.path.isfile(os.path.join(target_repo.path, 'bar')))

        porcelain.checkout_branch(target_repo, b"master")

        self.assertEqual(b"master", porcelain.active_branch(target_repo))
        self.assertFalse(os.path.isfile(os.path.join(target_repo.path, 'bar')))

        porcelain.checkout_branch(target_repo, b"origin/foo")

        self.assertEqual(b"foo", porcelain.active_branch(target_repo))
        self.assertTrue(os.path.isfile(os.path.join(target_repo.path, 'bar')))

        target_repo.close()


class SubmoduleTests(PorcelainTestCase):

    def test_empty(self):
        porcelain.commit(
            repo=self.repo.path,
            message=b"init",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        self.assertEqual([], list(porcelain.submodule_list(self.repo)))

    def test_add(self):
        porcelain.submodule_add(self.repo, "../bar.git", "bar")
        with open('%s/.gitmodules' % self.repo.path) as f:
            self.assertEqual("""\
[submodule "bar"]
\turl = ../bar.git
\tpath = bar
""", f.read())

    def test_init(self):
        porcelain.submodule_add(self.repo, "../bar.git", "bar")
        porcelain.submodule_init(self.repo)


class PushTests(PorcelainTestCase):
    def test_simple(self):
        """
        Basic test of porcelain push where self.repo is the remote.  First
        clone the remote, commit a file to the clone, then push the changes
        back to the remote.
        """
        outstream = BytesIO()
        errstream = BytesIO()

        porcelain.commit(
            repo=self.repo.path,
            message=b"init",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.clone(
            self.repo.path, target=clone_path, errstream=errstream
        )
        try:
            self.assertEqual(target_repo[b"HEAD"], self.repo[b"HEAD"])
        finally:
            target_repo.close()

        # create a second file to be pushed back to origin
        handle, fullpath = tempfile.mkstemp(dir=clone_path)
        os.close(handle)
        porcelain.add(repo=clone_path, paths=[fullpath])
        porcelain.commit(
            repo=clone_path,
            message=b"push",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup a non-checked out branch in the remote
        refs_path = b"refs/heads/foo"
        new_id = self.repo[b"HEAD"].id
        self.assertNotEqual(new_id, ZERO_SHA)
        self.repo.refs[refs_path] = new_id

        # Push to the remote
        porcelain.push(
            clone_path,
            "origin",
            b"HEAD:" + refs_path,
            outstream=outstream,
            errstream=errstream,
        )

        self.assertEqual(
            target_repo.refs[b"refs/remotes/origin/foo"],
            target_repo.refs[b"HEAD"],
        )

        # Check that the target and source
        with Repo(clone_path) as r_clone:
            self.assertEqual(
                {
                    b"HEAD": new_id,
                    b"refs/heads/foo": r_clone[b"HEAD"].id,
                    b"refs/heads/master": new_id,
                },
                self.repo.get_refs(),
            )
            self.assertEqual(r_clone[b"HEAD"].id, self.repo[refs_path].id)

            # Get the change in the target repo corresponding to the add
            # this will be in the foo branch.
            change = list(
                tree_changes(
                    self.repo,
                    self.repo[b"HEAD"].tree,
                    self.repo[b"refs/heads/foo"].tree,
                )
            )[0]
            self.assertEqual(
                os.path.basename(fullpath), change.new.path.decode("ascii")
            )

    def test_local_missing(self):
        """Pushing a new branch."""
        outstream = BytesIO()
        errstream = BytesIO()

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.init(clone_path)
        target_repo.close()

        self.assertRaises(
            porcelain.Error,
            porcelain.push,
            self.repo,
            clone_path,
            b"HEAD:refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

    def test_new(self):
        """Pushing a new branch."""
        outstream = BytesIO()
        errstream = BytesIO()

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.init(clone_path)
        target_repo.close()

        # create a second file to be pushed back to origin
        handle, fullpath = tempfile.mkstemp(dir=clone_path)
        os.close(handle)
        porcelain.add(repo=clone_path, paths=[fullpath])
        new_id = porcelain.commit(
            repo=self.repo,
            message=b"push",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Push to the remote
        porcelain.push(
            self.repo,
            clone_path,
            b"HEAD:refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

        with Repo(clone_path) as r_clone:
            self.assertEqual(
                {
                    b"HEAD": new_id,
                    b"refs/heads/master": new_id,
                },
                r_clone.get_refs(),
            )

    def test_delete(self):
        """Basic test of porcelain push, removing a branch."""
        outstream = BytesIO()
        errstream = BytesIO()

        porcelain.commit(
            repo=self.repo.path,
            message=b"init",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.clone(
            self.repo.path, target=clone_path, errstream=errstream
        )
        target_repo.close()

        # Setup a non-checked out branch in the remote
        refs_path = b"refs/heads/foo"
        new_id = self.repo[b"HEAD"].id
        self.assertNotEqual(new_id, ZERO_SHA)
        self.repo.refs[refs_path] = new_id

        # Push to the remote
        porcelain.push(
            clone_path,
            self.repo.path,
            b":" + refs_path,
            outstream=outstream,
            errstream=errstream,
        )

        self.assertEqual(
            {
                b"HEAD": new_id,
                b"refs/heads/master": new_id,
            },
            self.repo.get_refs(),
        )

    def test_diverged(self):
        outstream = BytesIO()
        errstream = BytesIO()

        porcelain.commit(
            repo=self.repo.path,
            message=b"init",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Setup target repo cloned from temp test repo
        clone_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_path)
        target_repo = porcelain.clone(
            self.repo.path, target=clone_path, errstream=errstream
        )
        target_repo.close()

        remote_id = porcelain.commit(
            repo=self.repo.path,
            message=b"remote change",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        local_id = porcelain.commit(
            repo=clone_path,
            message=b"local change",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        outstream = BytesIO()
        errstream = BytesIO()

        # Push to the remote
        self.assertRaises(
            porcelain.DivergedBranches,
            porcelain.push,
            clone_path,
            self.repo.path,
            b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

        self.assertEqual(
            {
                b"HEAD": remote_id,
                b"refs/heads/master": remote_id,
            },
            self.repo.get_refs(),
        )

        self.assertEqual(b"", outstream.getvalue())
        self.assertEqual(b"", errstream.getvalue())

        outstream = BytesIO()
        errstream = BytesIO()

        # Push to the remote with --force
        porcelain.push(
            clone_path,
            self.repo.path,
            b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
            force=True,
        )

        self.assertEqual(
            {
                b"HEAD": local_id,
                b"refs/heads/master": local_id,
            },
            self.repo.get_refs(),
        )

        self.assertEqual(b"", outstream.getvalue())
        self.assertTrue(re.match(b"Push to .* successful.\n", errstream.getvalue()))


class PullTests(PorcelainTestCase):
    def setUp(self):
        super().setUp()
        # create a file for initial commit
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test",
            author=b"test <email>",
            committer=b"test <email>",
        )

        # Setup target repo
        self.target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.target_path)
        target_repo = porcelain.clone(
            self.repo.path, target=self.target_path, errstream=BytesIO()
        )
        target_repo.close()

        # create a second file to be pushed
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test2",
            author=b"test2 <email>",
            committer=b"test2 <email>",
        )

        self.assertIn(b"refs/heads/master", self.repo.refs)
        self.assertIn(b"refs/heads/master", target_repo.refs)

    def test_simple(self):
        outstream = BytesIO()
        errstream = BytesIO()

        # Pull changes into the cloned repo
        porcelain.pull(
            self.target_path,
            self.repo.path,
            b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

        # Check the target repo for pushed changes
        with Repo(self.target_path) as r:
            self.assertEqual(r[b"HEAD"].id, self.repo[b"HEAD"].id)

    def test_diverged(self):
        outstream = BytesIO()
        errstream = BytesIO()

        c3a = porcelain.commit(
            repo=self.target_path,
            message=b"test3a",
            author=b"test2 <email>",
            committer=b"test2 <email>",
        )

        porcelain.commit(
            repo=self.repo.path,
            message=b"test3b",
            author=b"test2 <email>",
            committer=b"test2 <email>",
        )

        # Pull changes into the cloned repo
        self.assertRaises(
            porcelain.DivergedBranches,
            porcelain.pull,
            self.target_path,
            self.repo.path,
            b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

        # Check the target repo for pushed changes
        with Repo(self.target_path) as r:
            self.assertEqual(r[b"refs/heads/master"].id, c3a)

        self.assertRaises(
            NotImplementedError,
            porcelain.pull,
            self.target_path,
            self.repo.path,
            b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
            fast_forward=False,
        )

        # Check the target repo for pushed changes
        with Repo(self.target_path) as r:
            self.assertEqual(r[b"refs/heads/master"].id, c3a)

    def test_no_refspec(self):
        outstream = BytesIO()
        errstream = BytesIO()

        # Pull changes into the cloned repo
        porcelain.pull(
            self.target_path,
            self.repo.path,
            outstream=outstream,
            errstream=errstream,
        )

        # Check the target repo for pushed changes
        with Repo(self.target_path) as r:
            self.assertEqual(r[b"HEAD"].id, self.repo[b"HEAD"].id)

    def test_no_remote_location(self):
        outstream = BytesIO()
        errstream = BytesIO()

        # Pull changes into the cloned repo
        porcelain.pull(
            self.target_path,
            refspecs=b"refs/heads/master",
            outstream=outstream,
            errstream=errstream,
        )

        # Check the target repo for pushed changes
        with Repo(self.target_path) as r:
            self.assertEqual(r[b"HEAD"].id, self.repo[b"HEAD"].id)


class StatusTests(PorcelainTestCase):
    def test_empty(self):
        results = porcelain.status(self.repo)
        self.assertEqual({"add": [], "delete": [], "modify": []}, results.staged)
        self.assertEqual([], results.unstaged)

    def test_status_base(self):
        """Integration test for `status` functionality."""

        # Commit a dummy file then modify it
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("origstuff")

        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # modify access and modify time of path
        os.utime(fullpath, (0, 0))

        with open(fullpath, "wb") as f:
            f.write(b"stuff")

        # Make a dummy file and stage it
        filename_add = "bar"
        fullpath = os.path.join(self.repo.path, filename_add)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)

        results = porcelain.status(self.repo)

        self.assertEqual(results.staged["add"][0], filename_add.encode("ascii"))
        self.assertEqual(results.unstaged, [b"foo"])

    def test_status_all(self):
        del_path = os.path.join(self.repo.path, "foo")
        mod_path = os.path.join(self.repo.path, "bar")
        add_path = os.path.join(self.repo.path, "baz")
        us_path = os.path.join(self.repo.path, "blye")
        ut_path = os.path.join(self.repo.path, "blyat")
        with open(del_path, "w") as f:
            f.write("origstuff")
        with open(mod_path, "w") as f:
            f.write("origstuff")
        with open(us_path, "w") as f:
            f.write("origstuff")
        porcelain.add(repo=self.repo.path, paths=[del_path, mod_path, us_path])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )
        porcelain.remove(self.repo.path, [del_path])
        with open(add_path, "w") as f:
            f.write("origstuff")
        with open(mod_path, "w") as f:
            f.write("more_origstuff")
        with open(us_path, "w") as f:
            f.write("more_origstuff")
        porcelain.add(repo=self.repo.path, paths=[add_path, mod_path])
        with open(us_path, "w") as f:
            f.write("\norigstuff")
        with open(ut_path, "w") as f:
            f.write("origstuff")
        results = porcelain.status(self.repo.path)
        self.assertDictEqual(
            {"add": [b"baz"], "delete": [b"foo"], "modify": [b"bar"]},
            results.staged,
        )
        self.assertListEqual(results.unstaged, [b"blye"])
        results_no_untracked = porcelain.status(self.repo.path, untracked_files="no")
        self.assertListEqual(results_no_untracked.untracked, [])

    def test_status_wrong_untracked_files_value(self):
        with self.assertRaises(ValueError):
            porcelain.status(self.repo.path, untracked_files="antani")

    def test_status_untracked_path(self):
        untracked_dir = os.path.join(self.repo_path, "untracked_dir")
        os.mkdir(untracked_dir)
        untracked_file = os.path.join(untracked_dir, "untracked_file")
        with open(untracked_file, "w") as fh:
            fh.write("untracked")

        _, _, untracked = porcelain.status(self.repo.path, untracked_files="all")
        self.assertEqual(untracked, ["untracked_dir/untracked_file"])

    def test_status_crlf_mismatch(self):
        # First make a commit as if the file has been added on a Linux system
        # or with core.autocrlf=True
        file_path = os.path.join(self.repo.path, "crlf")
        with open(file_path, "wb") as f:
            f.write(b"line1\nline2")
        porcelain.add(repo=self.repo.path, paths=[file_path])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Then update the file as if it was created by CGit on a Windows
        # system with core.autocrlf=true
        with open(file_path, "wb") as f:
            f.write(b"line1\r\nline2")

        results = porcelain.status(self.repo)
        self.assertDictEqual({"add": [], "delete": [], "modify": []}, results.staged)
        self.assertListEqual(results.unstaged, [b"crlf"])
        self.assertListEqual(results.untracked, [])

    def test_status_autocrlf_true(self):
        # First make a commit as if the file has been added on a Linux system
        # or with core.autocrlf=True
        file_path = os.path.join(self.repo.path, "crlf")
        with open(file_path, "wb") as f:
            f.write(b"line1\nline2")
        porcelain.add(repo=self.repo.path, paths=[file_path])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        # Then update the file as if it was created by CGit on a Windows
        # system with core.autocrlf=true
        with open(file_path, "wb") as f:
            f.write(b"line1\r\nline2")

        # TODO: It should be set automatically by looking at the configuration
        c = self.repo.get_config()
        c.set("core", "autocrlf", True)
        c.write_to_path()

        results = porcelain.status(self.repo)
        self.assertDictEqual({"add": [], "delete": [], "modify": []}, results.staged)
        self.assertListEqual(results.unstaged, [])
        self.assertListEqual(results.untracked, [])

    def test_status_autocrlf_input(self):
        # Commit existing file with CRLF
        file_path = os.path.join(self.repo.path, "crlf-exists")
        with open(file_path, "wb") as f:
            f.write(b"line1\r\nline2")
        porcelain.add(repo=self.repo.path, paths=[file_path])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        c = self.repo.get_config()
        c.set("core", "autocrlf", "input")
        c.write_to_path()

        # Add new (untracked) file
        file_path = os.path.join(self.repo.path, "crlf-new")
        with open(file_path, "wb") as f:
            f.write(b"line1\r\nline2")
        porcelain.add(repo=self.repo.path, paths=[file_path])

        results = porcelain.status(self.repo)
        self.assertDictEqual({"add": [b"crlf-new"], "delete": [], "modify": []}, results.staged)
        self.assertListEqual(results.unstaged, [])
        self.assertListEqual(results.untracked, [])

    def test_get_tree_changes_add(self):
        """Unit test for get_tree_changes add."""

        # Make a dummy file, stage
        filename = "bar"
        fullpath = os.path.join(self.repo.path, filename)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        filename = "foo"
        fullpath = os.path.join(self.repo.path, filename)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        changes = porcelain.get_tree_changes(self.repo.path)

        self.assertEqual(changes["add"][0], filename.encode("ascii"))
        self.assertEqual(len(changes["add"]), 1)
        self.assertEqual(len(changes["modify"]), 0)
        self.assertEqual(len(changes["delete"]), 0)

    def test_get_tree_changes_modify(self):
        """Unit test for get_tree_changes modify."""

        # Make a dummy file, stage, commit, modify
        filename = "foo"
        fullpath = os.path.join(self.repo.path, filename)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )
        with open(fullpath, "w") as f:
            f.write("otherstuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        changes = porcelain.get_tree_changes(self.repo.path)

        self.assertEqual(changes["modify"][0], filename.encode("ascii"))
        self.assertEqual(len(changes["add"]), 0)
        self.assertEqual(len(changes["modify"]), 1)
        self.assertEqual(len(changes["delete"]), 0)

    def test_get_tree_changes_delete(self):
        """Unit test for get_tree_changes delete."""

        # Make a dummy file, stage, commit, remove
        filename = "foo"
        fullpath = os.path.join(self.repo.path, filename)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )
        cwd = os.getcwd()
        try:
            os.chdir(self.repo.path)
            porcelain.remove(repo=self.repo.path, paths=[filename])
        finally:
            os.chdir(cwd)
        changes = porcelain.get_tree_changes(self.repo.path)

        self.assertEqual(changes["delete"][0], filename.encode("ascii"))
        self.assertEqual(len(changes["add"]), 0)
        self.assertEqual(len(changes["modify"]), 0)
        self.assertEqual(len(changes["delete"]), 1)

    def test_get_untracked_paths(self):
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("ignored\n")
        with open(os.path.join(self.repo.path, "ignored"), "w") as f:
            f.write("blah\n")
        with open(os.path.join(self.repo.path, "notignored"), "w") as f:
            f.write("blah\n")
        os.symlink(
            os.path.join(self.repo.path, os.pardir, "external_target"),
            os.path.join(self.repo.path, "link"),
        )
        self.assertEqual(
            {"ignored", "notignored", ".gitignore", "link"},
            set(
                porcelain.get_untracked_paths(
                    self.repo.path, self.repo.path, self.repo.open_index()
                )
            ),
        )
        self.assertEqual(
            {".gitignore", "notignored", "link"},
            set(porcelain.status(self.repo).untracked),
        )
        self.assertEqual(
            {".gitignore", "notignored", "ignored", "link"},
            set(porcelain.status(self.repo, ignored=True).untracked),
        )

    def test_get_untracked_paths_subrepo(self):
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("nested/\n")
        with open(os.path.join(self.repo.path, "notignored"), "w") as f:
            f.write("blah\n")

        subrepo = Repo.init(os.path.join(self.repo.path, "nested"), mkdir=True)
        with open(os.path.join(subrepo.path, "ignored"), "w") as f:
            f.write("bleep\n")
        with open(os.path.join(subrepo.path, "with"), "w") as f:
            f.write("bloop\n")
        with open(os.path.join(subrepo.path, "manager"), "w") as f:
            f.write("blop\n")

        self.assertEqual(
            {".gitignore", "notignored", os.path.join("nested", "")},
            set(
                porcelain.get_untracked_paths(
                    self.repo.path, self.repo.path, self.repo.open_index()
                )
            ),
        )
        self.assertEqual(
            {".gitignore", "notignored"},
            set(
                porcelain.get_untracked_paths(
                    self.repo.path,
                    self.repo.path,
                    self.repo.open_index(),
                    exclude_ignored=True,
                )
            ),
        )
        self.assertEqual(
            {"ignored", "with", "manager"},
            set(
                porcelain.get_untracked_paths(
                    subrepo.path, subrepo.path, subrepo.open_index()
                )
            ),
        )
        self.assertEqual(
            set(),
            set(
                porcelain.get_untracked_paths(
                    subrepo.path,
                    self.repo.path,
                    self.repo.open_index(),
                )
            ),
        )
        self.assertEqual(
            {os.path.join('nested', 'ignored'),
                os.path.join('nested', 'with'),
                os.path.join('nested', 'manager')},
            set(
                porcelain.get_untracked_paths(
                    self.repo.path,
                    subrepo.path,
                    self.repo.open_index(),
                )
            ),
        )

    def test_get_untracked_paths_subdir(self):
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("subdir/\nignored")
        with open(os.path.join(self.repo.path, "notignored"), "w") as f:
            f.write("blah\n")
        os.mkdir(os.path.join(self.repo.path, "subdir"))
        with open(os.path.join(self.repo.path, "ignored"), "w") as f:
            f.write("foo")
        with open(os.path.join(self.repo.path, "subdir", "ignored"), "w") as f:
            f.write("foo")

        self.assertEqual(
            {
                ".gitignore",
                "notignored",
                "ignored",
                os.path.join("subdir", ""),
            },
            set(
                porcelain.get_untracked_paths(
                    self.repo.path,
                    self.repo.path,
                    self.repo.open_index(),
                )
            )
        )
        self.assertEqual(
            {".gitignore", "notignored"},
            set(
                porcelain.get_untracked_paths(
                    self.repo.path,
                    self.repo.path,
                    self.repo.open_index(),
                    exclude_ignored=True,
                )
            )
        )

    def test_get_untracked_paths_invalid_untracked_files(self):
        with self.assertRaises(ValueError):
            list(
                porcelain.get_untracked_paths(
                    self.repo.path,
                    self.repo.path,
                    self.repo.open_index(),
                    untracked_files="invalid_value",
                )
            )

    def test_get_untracked_paths_normal(self):
        with self.assertRaises(NotImplementedError):
            _, _, _ = porcelain.status(
                repo=self.repo.path, untracked_files="normal"
            )

# TODO(jelmer): Add test for dulwich.porcelain.daemon


class UploadPackTests(PorcelainTestCase):
    """Tests for upload_pack."""

    def test_upload_pack(self):
        outf = BytesIO()
        exitcode = porcelain.upload_pack(self.repo.path, BytesIO(b"0000"), outf)
        outlines = outf.getvalue().splitlines()
        self.assertEqual([b"0000"], outlines)
        self.assertEqual(0, exitcode)


class ReceivePackTests(PorcelainTestCase):
    """Tests for receive_pack."""

    def test_receive_pack(self):
        filename = "foo"
        fullpath = os.path.join(self.repo.path, filename)
        with open(fullpath, "w") as f:
            f.write("stuff")
        porcelain.add(repo=self.repo.path, paths=fullpath)
        self.repo.do_commit(
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
            author_timestamp=1402354300,
            commit_timestamp=1402354300,
            author_timezone=0,
            commit_timezone=0,
        )
        outf = BytesIO()
        exitcode = porcelain.receive_pack(self.repo.path, BytesIO(b"0000"), outf)
        outlines = outf.getvalue().splitlines()
        self.assertEqual(
            [
                b"0091319b56ce3aee2d489f759736a79cc552c9bb86d9 HEAD\x00 report-status "
                b"delete-refs quiet ofs-delta side-band-64k "
                b"no-done symref=HEAD:refs/heads/master",
                b"003f319b56ce3aee2d489f759736a79cc552c9bb86d9 refs/heads/master",
                b"0000",
            ],
            outlines,
        )
        self.assertEqual(0, exitcode)


class BranchListTests(PorcelainTestCase):
    def test_standard(self):
        self.assertEqual(set(), set(porcelain.branch_list(self.repo)))

    def test_new_branch(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.branch_create(self.repo, b"foo")
        self.assertEqual(
            {b"master", b"foo"}, set(porcelain.branch_list(self.repo))
        )


class BranchCreateTests(PorcelainTestCase):
    def test_branch_exists(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.branch_create(self.repo, b"foo")
        self.assertRaises(porcelain.Error, porcelain.branch_create, self.repo, b"foo")
        porcelain.branch_create(self.repo, b"foo", force=True)

    def test_new_branch(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.branch_create(self.repo, b"foo")
        self.assertEqual(
            {b"master", b"foo"}, set(porcelain.branch_list(self.repo))
        )


class BranchDeleteTests(PorcelainTestCase):
    def test_simple(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.branch_create(self.repo, b"foo")
        self.assertIn(b"foo", porcelain.branch_list(self.repo))
        porcelain.branch_delete(self.repo, b"foo")
        self.assertNotIn(b"foo", porcelain.branch_list(self.repo))

    def test_simple_unicode(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo[b"HEAD"] = c1.id
        porcelain.branch_create(self.repo, "foo")
        self.assertIn(b"foo", porcelain.branch_list(self.repo))
        porcelain.branch_delete(self.repo, "foo")
        self.assertNotIn(b"foo", porcelain.branch_list(self.repo))


class FetchTests(PorcelainTestCase):
    def test_simple(self):
        outstream = BytesIO()
        errstream = BytesIO()

        # create a file for initial commit
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test",
            author=b"test <email>",
            committer=b"test <email>",
        )

        # Setup target repo
        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        target_repo = porcelain.clone(
            self.repo.path, target=target_path, errstream=errstream
        )

        # create a second file to be pushed
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test2",
            author=b"test2 <email>",
            committer=b"test2 <email>",
        )

        self.assertNotIn(self.repo[b"HEAD"].id, target_repo)
        target_repo.close()

        # Fetch changes into the cloned repo
        porcelain.fetch(target_path, "origin", outstream=outstream, errstream=errstream)

        # Assert that fetch updated the local image of the remote
        self.assert_correct_remote_refs(target_repo.get_refs(), self.repo.get_refs())

        # Check the target repo for pushed changes
        with Repo(target_path) as r:
            self.assertIn(self.repo[b"HEAD"].id, r)

    def test_with_remote_name(self):
        remote_name = "origin"
        outstream = BytesIO()
        errstream = BytesIO()

        # create a file for initial commit
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test",
            author=b"test <email>",
            committer=b"test <email>",
        )

        # Setup target repo
        target_path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target_path)
        target_repo = porcelain.clone(
            self.repo.path, target=target_path, errstream=errstream
        )

        # Capture current refs
        target_refs = target_repo.get_refs()

        # create a second file to be pushed
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.commit(
            repo=self.repo.path,
            message=b"test2",
            author=b"test2 <email>",
            committer=b"test2 <email>",
        )

        self.assertNotIn(self.repo[b"HEAD"].id, target_repo)

        target_config = target_repo.get_config()
        target_config.set(
            (b"remote", remote_name.encode()), b"url", self.repo.path.encode()
        )
        target_repo.close()

        # Fetch changes into the cloned repo
        porcelain.fetch(
            target_path, remote_name, outstream=outstream, errstream=errstream
        )

        # Assert that fetch updated the local image of the remote
        self.assert_correct_remote_refs(target_repo.get_refs(), self.repo.get_refs())

        # Check the target repo for pushed changes, as well as updates
        # for the refs
        with Repo(target_path) as r:
            self.assertIn(self.repo[b"HEAD"].id, r)
            self.assertNotEqual(self.repo.get_refs(), target_refs)

    def assert_correct_remote_refs(
        self, local_refs, remote_refs, remote_name=b"origin"
    ):
        """Assert that known remote refs corresponds to actual remote refs."""
        local_ref_prefix = b"refs/heads"
        remote_ref_prefix = b"refs/remotes/" + remote_name

        locally_known_remote_refs = {
            k[len(remote_ref_prefix) + 1 :]: v
            for k, v in local_refs.items()
            if k.startswith(remote_ref_prefix)
        }

        normalized_remote_refs = {
            k[len(local_ref_prefix) + 1 :]: v
            for k, v in remote_refs.items()
            if k.startswith(local_ref_prefix)
        }
        if b"HEAD" in locally_known_remote_refs and b"HEAD" in remote_refs:
            normalized_remote_refs[b"HEAD"] = remote_refs[b"HEAD"]

        self.assertEqual(locally_known_remote_refs, normalized_remote_refs)


class RepackTests(PorcelainTestCase):
    def test_empty(self):
        porcelain.repack(self.repo)

    def test_simple(self):
        handle, fullpath = tempfile.mkstemp(dir=self.repo.path)
        os.close(handle)
        porcelain.add(repo=self.repo.path, paths=fullpath)
        porcelain.repack(self.repo)


class LsTreeTests(PorcelainTestCase):
    def test_empty(self):
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        f = StringIO()
        porcelain.ls_tree(self.repo, b"HEAD", outstream=f)
        self.assertEqual(f.getvalue(), "")

    def test_simple(self):
        # Commit a dummy file then modify it
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("origstuff")

        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        f = StringIO()
        porcelain.ls_tree(self.repo, b"HEAD", outstream=f)
        self.assertEqual(
            f.getvalue(),
            "100644 blob 8b82634d7eae019850bb883f06abf428c58bc9aa\tfoo\n",
        )

    def test_recursive(self):
        # Create a directory then write a dummy file in it
        dirpath = os.path.join(self.repo.path, "adir")
        filepath = os.path.join(dirpath, "afile")
        os.mkdir(dirpath)
        with open(filepath, "w") as f:
            f.write("origstuff")
        porcelain.add(repo=self.repo.path, paths=[filepath])
        porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )
        f = StringIO()
        porcelain.ls_tree(self.repo, b"HEAD", outstream=f)
        self.assertEqual(
            f.getvalue(),
            "40000 tree b145cc69a5e17693e24d8a7be0016ed8075de66d\tadir\n",
        )
        f = StringIO()
        porcelain.ls_tree(self.repo, b"HEAD", outstream=f, recursive=True)
        self.assertEqual(
            f.getvalue(),
            "40000 tree b145cc69a5e17693e24d8a7be0016ed8075de66d\tadir\n"
            "100644 blob 8b82634d7eae019850bb883f06abf428c58bc9aa\tadir"
            "/afile\n",
        )


class LsRemoteTests(PorcelainTestCase):
    def test_empty(self):
        self.assertEqual({}, porcelain.ls_remote(self.repo.path))

    def test_some(self):
        cid = porcelain.commit(
            repo=self.repo.path,
            message=b"test status",
            author=b"author <email>",
            committer=b"committer <email>",
        )

        self.assertEqual(
            {b"refs/heads/master": cid, b"HEAD": cid},
            porcelain.ls_remote(self.repo.path),
        )


class LsFilesTests(PorcelainTestCase):
    def test_empty(self):
        self.assertEqual([], list(porcelain.ls_files(self.repo)))

    def test_simple(self):
        # Commit a dummy file then modify it
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("origstuff")

        porcelain.add(repo=self.repo.path, paths=[fullpath])
        self.assertEqual([b"foo"], list(porcelain.ls_files(self.repo)))


class RemoteAddTests(PorcelainTestCase):
    def test_new(self):
        porcelain.remote_add(self.repo, "jelmer", "git://jelmer.uk/code/dulwich")
        c = self.repo.get_config()
        self.assertEqual(
            c.get((b"remote", b"jelmer"), b"url"),
            b"git://jelmer.uk/code/dulwich",
        )

    def test_exists(self):
        porcelain.remote_add(self.repo, "jelmer", "git://jelmer.uk/code/dulwich")
        self.assertRaises(
            porcelain.RemoteExists,
            porcelain.remote_add,
            self.repo,
            "jelmer",
            "git://jelmer.uk/code/dulwich",
        )


class RemoteRemoveTests(PorcelainTestCase):
    def test_remove(self):
        porcelain.remote_add(self.repo, "jelmer", "git://jelmer.uk/code/dulwich")
        c = self.repo.get_config()
        self.assertEqual(
            c.get((b"remote", b"jelmer"), b"url"),
            b"git://jelmer.uk/code/dulwich",
        )
        porcelain.remote_remove(self.repo, "jelmer")
        self.assertRaises(KeyError, porcelain.remote_remove, self.repo, "jelmer")
        c = self.repo.get_config()
        self.assertRaises(KeyError, c.get, (b"remote", b"jelmer"), b"url")


class CheckIgnoreTests(PorcelainTestCase):
    def test_check_ignored(self):
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("foo")
        foo_path = os.path.join(self.repo.path, "foo")
        with open(foo_path, "w") as f:
            f.write("BAR")
        bar_path = os.path.join(self.repo.path, "bar")
        with open(bar_path, "w") as f:
            f.write("BAR")
        self.assertEqual(["foo"], list(porcelain.check_ignore(self.repo, [foo_path])))
        self.assertEqual([], list(porcelain.check_ignore(self.repo, [bar_path])))

    def test_check_added_abs(self):
        path = os.path.join(self.repo.path, "foo")
        with open(path, "w") as f:
            f.write("BAR")
        self.repo.stage(["foo"])
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("foo\n")
        self.assertEqual([], list(porcelain.check_ignore(self.repo, [path])))
        self.assertEqual(
            ["foo"],
            list(porcelain.check_ignore(self.repo, [path], no_index=True)),
        )

    def test_check_added_rel(self):
        with open(os.path.join(self.repo.path, "foo"), "w") as f:
            f.write("BAR")
        self.repo.stage(["foo"])
        with open(os.path.join(self.repo.path, ".gitignore"), "w") as f:
            f.write("foo\n")
        cwd = os.getcwd()
        os.mkdir(os.path.join(self.repo.path, "bar"))
        os.chdir(os.path.join(self.repo.path, "bar"))
        try:
            self.assertEqual(list(porcelain.check_ignore(self.repo, ["../foo"])), [])
            self.assertEqual(
                ["../foo"],
                list(porcelain.check_ignore(self.repo, ["../foo"], no_index=True)),
            )
        finally:
            os.chdir(cwd)


class UpdateHeadTests(PorcelainTestCase):
    def test_set_to_branch(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo.refs[b"refs/heads/blah"] = c1.id
        porcelain.update_head(self.repo, "blah")
        self.assertEqual(c1.id, self.repo.head())
        self.assertEqual(b"ref: refs/heads/blah", self.repo.refs.read_ref(b"HEAD"))

    def test_set_to_branch_detached(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo.refs[b"refs/heads/blah"] = c1.id
        porcelain.update_head(self.repo, "blah", detached=True)
        self.assertEqual(c1.id, self.repo.head())
        self.assertEqual(c1.id, self.repo.refs.read_ref(b"HEAD"))

    def test_set_to_commit_detached(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo.refs[b"refs/heads/blah"] = c1.id
        porcelain.update_head(self.repo, c1.id, detached=True)
        self.assertEqual(c1.id, self.repo.head())
        self.assertEqual(c1.id, self.repo.refs.read_ref(b"HEAD"))

    def test_set_new_branch(self):
        [c1] = build_commit_graph(self.repo.object_store, [[1]])
        self.repo.refs[b"refs/heads/blah"] = c1.id
        porcelain.update_head(self.repo, "blah", new_branch="bar")
        self.assertEqual(c1.id, self.repo.head())
        self.assertEqual(b"ref: refs/heads/bar", self.repo.refs.read_ref(b"HEAD"))


class MailmapTests(PorcelainTestCase):
    def test_no_mailmap(self):
        self.assertEqual(
            b"Jelmer Vernooij <jelmer@samba.org>",
            porcelain.check_mailmap(self.repo, b"Jelmer Vernooij <jelmer@samba.org>"),
        )

    def test_mailmap_lookup(self):
        with open(os.path.join(self.repo.path, ".mailmap"), "wb") as f:
            f.write(
                b"""\
Jelmer Vernooij <jelmer@debian.org>
"""
            )
        self.assertEqual(
            b"Jelmer Vernooij <jelmer@debian.org>",
            porcelain.check_mailmap(self.repo, b"Jelmer Vernooij <jelmer@samba.org>"),
        )


class FsckTests(PorcelainTestCase):
    def test_none(self):
        self.assertEqual([], list(porcelain.fsck(self.repo)))

    def test_git_dir(self):
        obj = Tree()
        a = Blob()
        a.data = b"foo"
        obj.add(b".git", 0o100644, a.id)
        self.repo.object_store.add_objects([(a, None), (obj, None)])
        self.assertEqual(
            [(obj.id, "invalid name .git")],
            [(sha, str(e)) for (sha, e) in porcelain.fsck(self.repo)],
        )


class DescribeTests(PorcelainTestCase):
    def test_no_commits(self):
        self.assertRaises(KeyError, porcelain.describe, self.repo.path)

    def test_single_commit(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        sha = porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        self.assertEqual(
            "g{}".format(sha[:7].decode("ascii")),
            porcelain.describe(self.repo.path),
        )

    def test_tag(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
        )
        self.assertEqual("tryme", porcelain.describe(self.repo.path))

    def test_tag_and_commit(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
        )
        with open(fullpath, "w") as f:
            f.write("BAR2")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        sha = porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        self.assertEqual(
            "tryme-1-g{}".format(sha[:7].decode("ascii")),
            porcelain.describe(self.repo.path),
        )

    def test_tag_and_commit_full(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        porcelain.tag_create(
            self.repo.path,
            b"tryme",
            b"foo <foo@bar.com>",
            b"bar",
            annotated=True,
        )
        with open(fullpath, "w") as f:
            f.write("BAR2")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        sha = porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        self.assertEqual(
            "tryme-1-g{}".format(sha.decode("ascii")),
            porcelain.describe(self.repo.path, abbrev=40),
        )


class PathToTreeTests(PorcelainTestCase):
    def setUp(self):
        super().setUp()
        self.fp = os.path.join(self.test_dir, "bar")
        with open(self.fp, "w") as f:
            f.write("something")
        oldcwd = os.getcwd()
        self.addCleanup(os.chdir, oldcwd)
        os.chdir(self.test_dir)

    def test_path_to_tree_path_base(self):
        self.assertEqual(b"bar", porcelain.path_to_tree_path(self.test_dir, self.fp))
        self.assertEqual(b"bar", porcelain.path_to_tree_path(".", "./bar"))
        self.assertEqual(b"bar", porcelain.path_to_tree_path(".", "bar"))
        cwd = os.getcwd()
        self.assertEqual(
            b"bar", porcelain.path_to_tree_path(".", os.path.join(cwd, "bar"))
        )
        self.assertEqual(b"bar", porcelain.path_to_tree_path(cwd, "bar"))

    def test_path_to_tree_path_syntax(self):
        self.assertEqual(b"bar", porcelain.path_to_tree_path(".", "./bar"))

    def test_path_to_tree_path_error(self):
        with self.assertRaises(ValueError):
            with tempfile.TemporaryDirectory() as od:
                porcelain.path_to_tree_path(od, self.fp)

    def test_path_to_tree_path_rel(self):
        cwd = os.getcwd()
        os.mkdir(os.path.join(self.repo.path, "foo"))
        os.mkdir(os.path.join(self.repo.path, "foo/bar"))
        try:
            os.chdir(os.path.join(self.repo.path, "foo/bar"))
            with open("baz", "w") as f:
                f.write("contents")
            self.assertEqual(b"bar/baz", porcelain.path_to_tree_path("..", "baz"))
            self.assertEqual(
                b"bar/baz",
                porcelain.path_to_tree_path(
                    os.path.join(os.getcwd(), ".."),
                    os.path.join(os.getcwd(), "baz"),
                ),
            )
            self.assertEqual(
                b"bar/baz",
                porcelain.path_to_tree_path("..", os.path.join(os.getcwd(), "baz")),
            )
            self.assertEqual(
                b"bar/baz",
                porcelain.path_to_tree_path(os.path.join(os.getcwd(), ".."), "baz"),
            )
        finally:
            os.chdir(cwd)


class GetObjectByPathTests(PorcelainTestCase):
    def test_simple(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
        )
        self.assertEqual(b"BAR", porcelain.get_object_by_path(self.repo, "foo").data)
        self.assertEqual(b"BAR", porcelain.get_object_by_path(self.repo, b"foo").data)

    def test_encoding(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        porcelain.commit(
            self.repo.path,
            message=b"Some message",
            author=b"Joe <joe@example.com>",
            committer=b"Bob <bob@example.com>",
            encoding=b"utf-8",
        )
        self.assertEqual(b"BAR", porcelain.get_object_by_path(self.repo, "foo").data)
        self.assertEqual(b"BAR", porcelain.get_object_by_path(self.repo, b"foo").data)

    def test_missing(self):
        self.assertRaises(KeyError, porcelain.get_object_by_path, self.repo, "foo")


class WriteTreeTests(PorcelainTestCase):
    def test_simple(self):
        fullpath = os.path.join(self.repo.path, "foo")
        with open(fullpath, "w") as f:
            f.write("BAR")
        porcelain.add(repo=self.repo.path, paths=[fullpath])
        self.assertEqual(
            b"d2092c8a9f311f0311083bf8d177f2ca0ab5b241",
            porcelain.write_tree(self.repo),
        )


class ActiveBranchTests(PorcelainTestCase):
    def test_simple(self):
        self.assertEqual(b"master", porcelain.active_branch(self.repo))


class FindUniqueAbbrevTests(PorcelainTestCase):

    def test_simple(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        self.assertEqual(
            c1.id.decode('ascii')[:7],
            porcelain.find_unique_abbrev(self.repo.object_store, c1.id))


class PackRefsTests(PorcelainTestCase):
    def test_all(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        self.repo.refs[b"refs/heads/master"] = c2.id
        self.repo.refs[b"refs/tags/foo"] = c1.id

        porcelain.pack_refs(self.repo, all=True)

        self.assertEqual(
            self.repo.refs.get_packed_refs(),
            {
                b"refs/heads/master": c2.id,
                b"refs/tags/foo": c1.id,
            },
        )

    def test_not_all(self):
        c1, c2, c3 = build_commit_graph(
            self.repo.object_store, [[1], [2, 1], [3, 1, 2]]
        )
        self.repo.refs[b"HEAD"] = c3.id
        self.repo.refs[b"refs/heads/master"] = c2.id
        self.repo.refs[b"refs/tags/foo"] = c1.id

        porcelain.pack_refs(self.repo)

        self.assertEqual(
            self.repo.refs.get_packed_refs(),
            {
                b"refs/tags/foo": c1.id,
            },
        )


class ServerTests(PorcelainTestCase):
    @contextlib.contextmanager
    def _serving(self):
        with make_server('localhost', 0, self.app) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            try:
                yield f"http://localhost:{server.server_port}"

            finally:
                server.shutdown()
                thread.join(10)

    def setUp(self):
        super().setUp()

        self.served_repo_path = os.path.join(self.test_dir, "served_repo.git")
        self.served_repo = Repo.init_bare(self.served_repo_path, mkdir=True)
        self.addCleanup(self.served_repo.close)

        backend = DictBackend({"/": self.served_repo})
        self.app = make_wsgi_chain(backend)

    def test_pull(self):
        c1, = build_commit_graph(self.served_repo.object_store, [[1]])
        self.served_repo.refs[b"refs/heads/master"] = c1.id

        with self._serving() as url:
            porcelain.pull(self.repo, url, "master")

    def test_push(self):
        c1, = build_commit_graph(self.repo.object_store, [[1]])
        self.repo.refs[b"refs/heads/master"] = c1.id

        with self._serving() as url:
            porcelain.push(self.repo, url, "master")
