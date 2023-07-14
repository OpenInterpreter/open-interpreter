# test_paramiko_vendor.py
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

"""Tests for paramiko_vendor."""

import socket
import threading
from io import StringIO
from unittest import skipIf

from dulwich.tests import TestCase

try:
    import paramiko
except ImportError:
    has_paramiko = False
else:
    has_paramiko = True
    from .paramiko_vendor import ParamikoSSHVendor

    class Server(paramiko.ServerInterface):
        """http://docs.paramiko.org/en/2.4/api/server.html"""
        def __init__(self, commands, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.commands = commands

        def check_channel_exec_request(self, channel, command):
            self.commands.append(command)
            return True

        def check_auth_password(self, username, password):
            if username == USER and password == PASSWORD:
                return paramiko.AUTH_SUCCESSFUL
            return paramiko.AUTH_FAILED

        def check_auth_publickey(self, username, key):
            pubkey = paramiko.RSAKey.from_private_key(StringIO(CLIENT_KEY))
            if username == USER and key == pubkey:
                return paramiko.AUTH_SUCCESSFUL
            return paramiko.AUTH_FAILED

        def check_channel_request(self, kind, chanid):
            if kind == "session":
                return paramiko.OPEN_SUCCEEDED
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

        def get_allowed_auths(self, username):
            return "password,publickey"


USER = 'testuser'
PASSWORD = 'test'
SERVER_KEY = """\
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAy/L1sSYAzxsMprtNXW4u/1jGXXkQmQ2xtmKVlR+RlIL3a1BH
bzTpPlZyjltAAwzIP8XRh0iJFKz5y3zSQChhX47ZGN0NvQsVct8R+YwsUonwfAJ+
JN0KBKKvC8fPHlzqBr3gX+ZxqsFH934tQ6wdQPH5eQWtdM8L826lMsH1737uyTGk
+mCSDjL3c6EzY83g7qhkJU2R4qbi6ne01FaWADzG8sOzXnHT+xpxtk8TTT8yCVUY
MmBNsSoA/ka3iWz70ghB+6Xb0WpFJZXWq1oYovviPAfZGZSrxBZMxsWMye70SdLl
TqsBEt0+miIcm9s0fvjWvQuhaHX6mZs5VO4r5QIDAQABAoIBAGYqeYWaYgFdrYLA
hUrubUCg+g3NHdFuGL4iuIgRXl4lFUh+2KoOuWDu8Uf60iA1AQNhV0sLvQ/Mbv3O
s4xMLisuZfaclctDiCUZNenqnDFkxEF7BjH1QJV94W5nU4wEQ3/JEmM4D2zYkfKb
FJW33JeyH6TOgUvohDYYEU1R+J9V8qA243p+ui1uVtNI6Pb0TXJnG5y9Ny4vkSWH
Fi0QoMPR1r9xJ4SEearGzA/crb4SmmDTKhGSoMsT3d5ATieLmwcS66xWz8w4oFGJ
yzDq24s4Fp9ccNjMf/xR8XRiekJv835gjEqwF9IXyvgOaq6XJ1iCqGPFDKa25nui
JnEstOkCgYEA/ZXk7aIanvdeJlTqpX578sJfCnrXLydzE8emk1b7+5mrzGxQ4/pM
PBQs2f8glT3t0O0mRX9NoRqnwrid88/b+cY4NCOICFZeasX336/gYQxyVeRLJS6Z
hnGEQqry8qS7PdKAyeHMNmZFrUh4EiHiObymEfQS+mkRUObn0cGBTw8CgYEAzeQU
D2baec1DawjppKaRynAvWjp+9ry1lZx9unryKVRwjRjkEpw+b3/+hdaF1IvsVSce
cNj+6W2guZ2tyHuPhZ64/4SJVyE2hKDSKD4xTb2nVjsMeN0bLD2UWXC9mwbx8nWa
2tmtUZ7a/okQb2cSdosJinRewLNqXIsBXamT1csCgYEA0cXb2RCOQQ6U3dTFPx4A
3vMXuA2iUKmrsqMoEx6T2LBow/Sefdkik1iFOdipVYwjXP+w9zC2QR1Rxez/DR/X
8ymceNUjxPHdrSoTQQG29dFcC92MpDeGXQcuyA+uZjcLhbrLOzYEvsOfxBb87NMG
14hNQPDNekTMREafYo9WrtUCgYAREK54+FVzcwf7fymedA/xb4r9N4v+d3W1iNsC
8d3Qfyc1CrMct8aVB07ZWQaOr2pPRIbJY7L9NhD0UZVt4I/sy1MaGqonhqE2LP4+
R6legDG2e/50ph7yc8gwAaA1kUXMiuLi8Nfkw/3yyvmJwklNegi4aRzRbA2Mzhi2
4q9WMQKBgQCb0JNyxHG4pvLWCF/j0Sm1FfvrpnqSv5678n1j4GX7Ka/TubOK1Y4K
U+Oib7dKa/zQMWehVFNTayrsq6bKVZ6q7zG+IHiRLw4wjeAxREFH6WUjDrn9vl2l
D48DKbBuBwuVOJWyq3qbfgJXojscgNQklrsPdXVhDwOF0dYxP89HnA==
-----END RSA PRIVATE KEY-----"""
CLIENT_KEY = """\
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAxvREKSElPOm/0z/nPO+j5rk2tjdgGcGc7We1QZ6TRXYLu7nN
GeEFIL4p8N1i6dmB+Eydt7xqCU79MWD6Yy4prFe1+/K1wCDUxIbFMxqQcX5zjJzd
i8j8PbcaUlVhP/OkjtkSxrXaGDO1BzfdV4iEBtTV/2l3zmLKJlt3jnOHLczP24CB
DTQKp3rKshbRefzot9Y+wnaK692RsYgsyo9YEP0GyWKG9topCHk13r46J6vGLeuj
ryUKqmbLJkzbJbIcEqwTDo5iHaCVqaMr5Hrb8BdMucSseqZQJsXSd+9tdRcIblUQ
38kZjmFMm4SFbruJcpZCNM2wNSZPIRX+3eiwNwIDAQABAoIBAHSacOBSJsr+jIi5
KUOTh9IPtzswVUiDKwARCjB9Sf8p4lKR4N1L/n9kNJyQhApeikgGT2GCMftmqgoo
tlculQoHFgemBlOmak0MV8NNzF5YKEy/GzF0CDH7gJfEpoyetVFrdA+2QS5yD6U9
XqKQxiBi2VEqdScmyyeT8AwzNYTnPeH/DOEcnbdRjqiy/CD79F49CQ1lX1Fuqm0K
I7BivBH1xo/rVnUP4F+IzocDqoga+Pjdj0LTXIgJlHQDSbhsQqWujWQDDuKb+MAw
sNK4Zf8ErV3j1PyA7f/M5LLq6zgstkW4qikDHo4SpZX8kFOO8tjqb7kujj7XqeaB
CxqrOTECgYEA73uWkrohcmDJ4KqbuL3tbExSCOUiaIV+sT1eGPNi7GCmXD4eW5Z4
75v2IHymW83lORSu/DrQ6sKr1nkuRpqr2iBzRmQpl/H+wahIhBXlnJ25uUjDsuPO
1Pq2LcmyD+jTxVnmbSe/q7O09gZQw3I6H4+BMHmpbf8tC97lqimzpJ0CgYEA1K0W
ZL70Xtn9quyHvbtae/BW07NZnxvUg4UaVIAL9Zu34JyplJzyzbIjrmlDbv6aRogH
/KtuG9tfbf55K/jjqNORiuRtzt1hUN1ye4dyW7tHx2/7lXdlqtyK40rQl8P0kqf8
zaS6BqjnobgSdSpg32rWoL/pcBHPdJCJEgQ8zeMCgYEA0/PK8TOhNIzrP1dgGSKn
hkkJ9etuB5nW5mEM7gJDFDf6JPupfJ/xiwe6z0fjKK9S57EhqgUYMB55XYnE5iIw
ZQ6BV9SAZ4V7VsRs4dJLdNC3tn/rDGHJBgCaym2PlbsX6rvFT+h1IC8dwv0V79Ui
Ehq9WTzkMoE8yhvNokvkPZUCgYEAgBAFxv5xGdh79ftdtXLmhnDvZ6S8l6Fjcxqo
Ay/jg66Tp43OU226iv/0mmZKM8Dd1xC8dnon4GBVc19jSYYiWBulrRPlx0Xo/o+K
CzZBN1lrXH1i6dqufpc0jq8TMf/N+q1q/c1uMupsKCY1/xVYpc+ok71b7J7c49zQ
nOeuUW8CgYA9Infooy65FTgbzca0c9kbCUBmcAPQ2ItH3JcPKWPQTDuV62HcT00o
fZdIV47Nez1W5Clk191RMy8TXuqI54kocciUWpThc6j44hz49oUueb8U4bLcEHzA
WxtWBWHwxfSmqgTXilEA3ALJp0kNolLnEttnhENwJpZHlqtes0ZA4w==
-----END RSA PRIVATE KEY-----"""


@skipIf(not has_paramiko, "paramiko is not installed")
class ParamikoSSHVendorTests(TestCase):

    def setUp(self):
        import paramiko.transport

        # re-enable server functionality for tests
        if hasattr(paramiko.transport, "SERVER_DISABLED_BY_GENTOO"):
            paramiko.transport.SERVER_DISABLED_BY_GENTOO = False

        self.commands = []
        socket.setdefaulttimeout(10)
        self.addCleanup(socket.setdefaulttimeout, None)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.listen(5)
        self.addCleanup(self.socket.close)
        self.port = self.socket.getsockname()[1]
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def tearDown(self):
        self.thread.join()

    def _run(self):
        try:
            conn, addr = self.socket.accept()
        except OSError:
            return False
        self.transport = paramiko.Transport(conn)
        self.addCleanup(self.transport.close)
        host_key = paramiko.RSAKey.from_private_key(StringIO(SERVER_KEY))
        self.transport.add_server_key(host_key)
        server = Server(self.commands)
        self.transport.start_server(server=server)

    def test_run_command_password(self):
        vendor = ParamikoSSHVendor(allow_agent=False, look_for_keys=False,)
        vendor.run_command(
            '127.0.0.1', 'test_run_command_password',
            username=USER, port=self.port, password=PASSWORD)

        self.assertIn(b'test_run_command_password', self.commands)

    def test_run_command_with_privkey(self):
        key = paramiko.RSAKey.from_private_key(StringIO(CLIENT_KEY))

        vendor = ParamikoSSHVendor(allow_agent=False, look_for_keys=False,)
        vendor.run_command(
            '127.0.0.1', 'test_run_command_with_privkey',
            username=USER, port=self.port, pkey=key)

        self.assertIn(b'test_run_command_with_privkey', self.commands)

    def test_run_command_data_transfer(self):
        vendor = ParamikoSSHVendor(allow_agent=False, look_for_keys=False,)
        con = vendor.run_command(
            '127.0.0.1', 'test_run_command_data_transfer',
            username=USER, port=self.port, password=PASSWORD)

        self.assertIn(b'test_run_command_data_transfer', self.commands)

        channel = self.transport.accept(5)
        channel.send(b'stdout\n')
        channel.send_stderr(b'stderr\n')
        channel.close()

        # Fixme: it's return false
        # self.assertTrue(con.can_read())

        self.assertEqual(b'stdout\n', con.read(4096))

        # Fixme: it's return empty string
        # self.assertEqual(b'stderr\n', con.read_stderr(4096))
