# test_protocol.py -- Tests for the git protocol
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

"""Tests for the smart protocol utility functions."""


from io import BytesIO

from dulwich.tests import TestCase

from ..errors import HangupException
from ..protocol import (MULTI_ACK, MULTI_ACK_DETAILED, SINGLE_ACK,
                        BufferedPktLineWriter, GitProtocolError, PktLineParser,
                        Protocol, ReceivableProtocol, ack_type,
                        extract_capabilities, extract_want_line_capabilities)


class BaseProtocolTests:
    def test_write_pkt_line_none(self):
        self.proto.write_pkt_line(None)
        self.assertEqual(self.rout.getvalue(), b"0000")

    def test_write_pkt_line(self):
        self.proto.write_pkt_line(b"bla")
        self.assertEqual(self.rout.getvalue(), b"0007bla")

    def test_read_pkt_line(self):
        self.rin.write(b"0008cmd ")
        self.rin.seek(0)
        self.assertEqual(b"cmd ", self.proto.read_pkt_line())

    def test_eof(self):
        self.rin.write(b"0000")
        self.rin.seek(0)
        self.assertFalse(self.proto.eof())
        self.assertEqual(None, self.proto.read_pkt_line())
        self.assertTrue(self.proto.eof())
        self.assertRaises(HangupException, self.proto.read_pkt_line)

    def test_unread_pkt_line(self):
        self.rin.write(b"0007foo0000")
        self.rin.seek(0)
        self.assertEqual(b"foo", self.proto.read_pkt_line())
        self.proto.unread_pkt_line(b"bar")
        self.assertEqual(b"bar", self.proto.read_pkt_line())
        self.assertEqual(None, self.proto.read_pkt_line())
        self.proto.unread_pkt_line(b"baz1")
        self.assertRaises(ValueError, self.proto.unread_pkt_line, b"baz2")

    def test_read_pkt_seq(self):
        self.rin.write(b"0008cmd 0005l0000")
        self.rin.seek(0)
        self.assertEqual([b"cmd ", b"l"], list(self.proto.read_pkt_seq()))

    def test_read_pkt_line_none(self):
        self.rin.write(b"0000")
        self.rin.seek(0)
        self.assertEqual(None, self.proto.read_pkt_line())

    def test_read_pkt_line_wrong_size(self):
        self.rin.write(b"0100too short")
        self.rin.seek(0)
        self.assertRaises(GitProtocolError, self.proto.read_pkt_line)

    def test_write_sideband(self):
        self.proto.write_sideband(3, b"bloe")
        self.assertEqual(self.rout.getvalue(), b"0009\x03bloe")

    def test_send_cmd(self):
        self.proto.send_cmd(b"fetch", b"a", b"b")
        self.assertEqual(self.rout.getvalue(), b"000efetch a\x00b\x00")

    def test_read_cmd(self):
        self.rin.write(b"0012cmd arg1\x00arg2\x00")
        self.rin.seek(0)
        self.assertEqual((b"cmd", [b"arg1", b"arg2"]), self.proto.read_cmd())

    def test_read_cmd_noend0(self):
        self.rin.write(b"0011cmd arg1\x00arg2")
        self.rin.seek(0)
        self.assertRaises(AssertionError, self.proto.read_cmd)


class ProtocolTests(BaseProtocolTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.rout = BytesIO()
        self.rin = BytesIO()
        self.proto = Protocol(self.rin.read, self.rout.write)


class ReceivableBytesIO(BytesIO):
    """BytesIO with socket-like recv semantics for testing."""

    def __init__(self):
        BytesIO.__init__(self)
        self.allow_read_past_eof = False

    def recv(self, size):
        # fail fast if no bytes are available; in a real socket, this would
        # block forever
        if self.tell() == len(self.getvalue()) and not self.allow_read_past_eof:
            raise GitProtocolError("Blocking read past end of socket")
        if size == 1:
            return self.read(1)
        # calls shouldn't return quite as much as asked for
        return self.read(size - 1)


class ReceivableProtocolTests(BaseProtocolTests, TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.rout = BytesIO()
        self.rin = ReceivableBytesIO()
        self.proto = ReceivableProtocol(self.rin.recv, self.rout.write)
        self.proto._rbufsize = 8

    def test_eof(self):
        # Allow blocking reads past EOF just for this test. The only parts of
        # the protocol that might check for EOF do not depend on the recv()
        # semantics anyway.
        self.rin.allow_read_past_eof = True
        BaseProtocolTests.test_eof(self)

    def test_recv(self):
        all_data = b"1234567" * 10  # not a multiple of bufsize
        self.rin.write(all_data)
        self.rin.seek(0)
        data = b""
        # We ask for 8 bytes each time and actually read 7, so it should take
        # exactly 10 iterations.
        for _ in range(10):
            data += self.proto.recv(10)
        # any more reads would block
        self.assertRaises(GitProtocolError, self.proto.recv, 10)
        self.assertEqual(all_data, data)

    def test_recv_read(self):
        all_data = b"1234567"  # recv exactly in one call
        self.rin.write(all_data)
        self.rin.seek(0)
        self.assertEqual(b"1234", self.proto.recv(4))
        self.assertEqual(b"567", self.proto.read(3))
        self.assertRaises(GitProtocolError, self.proto.recv, 10)

    def test_read_recv(self):
        all_data = b"12345678abcdefg"
        self.rin.write(all_data)
        self.rin.seek(0)
        self.assertEqual(b"1234", self.proto.read(4))
        self.assertEqual(b"5678abc", self.proto.recv(8))
        self.assertEqual(b"defg", self.proto.read(4))
        self.assertRaises(GitProtocolError, self.proto.recv, 10)

    def test_mixed(self):
        # arbitrary non-repeating string
        all_data = b",".join(str(i).encode("ascii") for i in range(100))
        self.rin.write(all_data)
        self.rin.seek(0)
        data = b""

        for i in range(1, 100):
            data += self.proto.recv(i)
            # if we get to the end, do a non-blocking read instead of blocking
            if len(data) + i > len(all_data):
                data += self.proto.recv(i)
                # ReceivableBytesIO leaves off the last byte unless we ask
                # nicely
                data += self.proto.recv(1)
                break
            else:
                data += self.proto.read(i)
        else:
            # didn't break, something must have gone wrong
            self.fail()

        self.assertEqual(all_data, data)


class CapabilitiesTestCase(TestCase):
    def test_plain(self):
        self.assertEqual((b"bla", []), extract_capabilities(b"bla"))

    def test_caps(self):
        self.assertEqual((b"bla", [b"la"]), extract_capabilities(b"bla\0la"))
        self.assertEqual((b"bla", [b"la"]), extract_capabilities(b"bla\0la\n"))
        self.assertEqual((b"bla", [b"la", b"la"]), extract_capabilities(b"bla\0la la"))

    def test_plain_want_line(self):
        self.assertEqual((b"want bla", []), extract_want_line_capabilities(b"want bla"))

    def test_caps_want_line(self):
        self.assertEqual(
            (b"want bla", [b"la"]),
            extract_want_line_capabilities(b"want bla la"),
        )
        self.assertEqual(
            (b"want bla", [b"la"]),
            extract_want_line_capabilities(b"want bla la\n"),
        )
        self.assertEqual(
            (b"want bla", [b"la", b"la"]),
            extract_want_line_capabilities(b"want bla la la"),
        )

    def test_ack_type(self):
        self.assertEqual(SINGLE_ACK, ack_type([b"foo", b"bar"]))
        self.assertEqual(MULTI_ACK, ack_type([b"foo", b"bar", b"multi_ack"]))
        self.assertEqual(
            MULTI_ACK_DETAILED,
            ack_type([b"foo", b"bar", b"multi_ack_detailed"]),
        )
        # choose detailed when both present
        self.assertEqual(
            MULTI_ACK_DETAILED,
            ack_type([b"foo", b"bar", b"multi_ack", b"multi_ack_detailed"]),
        )


class BufferedPktLineWriterTests(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self._output = BytesIO()
        self._writer = BufferedPktLineWriter(self._output.write, bufsize=16)

    def assertOutputEquals(self, expected):
        self.assertEqual(expected, self._output.getvalue())

    def _truncate(self):
        self._output.seek(0)
        self._output.truncate()

    def test_write(self):
        self._writer.write(b"foo")
        self.assertOutputEquals(b"")
        self._writer.flush()
        self.assertOutputEquals(b"0007foo")

    def test_write_none(self):
        self._writer.write(None)
        self.assertOutputEquals(b"")
        self._writer.flush()
        self.assertOutputEquals(b"0000")

    def test_flush_empty(self):
        self._writer.flush()
        self.assertOutputEquals(b"")

    def test_write_multiple(self):
        self._writer.write(b"foo")
        self._writer.write(b"bar")
        self.assertOutputEquals(b"")
        self._writer.flush()
        self.assertOutputEquals(b"0007foo0007bar")

    def test_write_across_boundary(self):
        self._writer.write(b"foo")
        self._writer.write(b"barbaz")
        self.assertOutputEquals(b"0007foo000abarba")
        self._truncate()
        self._writer.flush()
        self.assertOutputEquals(b"z")

    def test_write_to_boundary(self):
        self._writer.write(b"foo")
        self._writer.write(b"barba")
        self.assertOutputEquals(b"0007foo0009barba")
        self._truncate()
        self._writer.write(b"z")
        self._writer.flush()
        self.assertOutputEquals(b"0005z")


class PktLineParserTests(TestCase):
    def test_none(self):
        pktlines = []
        parser = PktLineParser(pktlines.append)
        parser.parse(b"0000")
        self.assertEqual(pktlines, [None])
        self.assertEqual(b"", parser.get_tail())

    def test_small_fragments(self):
        pktlines = []
        parser = PktLineParser(pktlines.append)
        parser.parse(b"00")
        parser.parse(b"05")
        parser.parse(b"z0000")
        self.assertEqual(pktlines, [b"z", None])
        self.assertEqual(b"", parser.get_tail())

    def test_multiple_packets(self):
        pktlines = []
        parser = PktLineParser(pktlines.append)
        parser.parse(b"0005z0006aba")
        self.assertEqual(pktlines, [b"z", b"ab"])
        self.assertEqual(b"a", parser.get_tail())
