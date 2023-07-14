# protocol.py -- Shared parts of the git protocols
# Copyright (C) 2008 John Carr <john.carr@unrouted.co.uk>
# Copyright (C) 2008-2012 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Generic functions for talking the git smart server protocol."""

from io import BytesIO
from os import SEEK_END

import dulwich

from .errors import GitProtocolError, HangupException

TCP_GIT_PORT = 9418

ZERO_SHA = b"0" * 40

SINGLE_ACK = 0
MULTI_ACK = 1
MULTI_ACK_DETAILED = 2

# pack data
SIDE_BAND_CHANNEL_DATA = 1
# progress messages
SIDE_BAND_CHANNEL_PROGRESS = 2
# fatal error message just before stream aborts
SIDE_BAND_CHANNEL_FATAL = 3

CAPABILITY_ATOMIC = b"atomic"
CAPABILITY_DEEPEN_SINCE = b"deepen-since"
CAPABILITY_DEEPEN_NOT = b"deepen-not"
CAPABILITY_DEEPEN_RELATIVE = b"deepen-relative"
CAPABILITY_DELETE_REFS = b"delete-refs"
CAPABILITY_INCLUDE_TAG = b"include-tag"
CAPABILITY_MULTI_ACK = b"multi_ack"
CAPABILITY_MULTI_ACK_DETAILED = b"multi_ack_detailed"
CAPABILITY_NO_DONE = b"no-done"
CAPABILITY_NO_PROGRESS = b"no-progress"
CAPABILITY_OFS_DELTA = b"ofs-delta"
CAPABILITY_QUIET = b"quiet"
CAPABILITY_REPORT_STATUS = b"report-status"
CAPABILITY_SHALLOW = b"shallow"
CAPABILITY_SIDE_BAND = b"side-band"
CAPABILITY_SIDE_BAND_64K = b"side-band-64k"
CAPABILITY_THIN_PACK = b"thin-pack"
CAPABILITY_AGENT = b"agent"
CAPABILITY_SYMREF = b"symref"
CAPABILITY_ALLOW_TIP_SHA1_IN_WANT = b"allow-tip-sha1-in-want"
CAPABILITY_ALLOW_REACHABLE_SHA1_IN_WANT = b"allow-reachable-sha1-in-want"

# Magic ref that is used to attach capabilities to when
# there are no refs. Should always be ste to ZERO_SHA.
CAPABILITIES_REF = b"capabilities^{}"

COMMON_CAPABILITIES = [
    CAPABILITY_OFS_DELTA,
    CAPABILITY_SIDE_BAND,
    CAPABILITY_SIDE_BAND_64K,
    CAPABILITY_AGENT,
    CAPABILITY_NO_PROGRESS,
]
KNOWN_UPLOAD_CAPABILITIES = set(
    COMMON_CAPABILITIES
    + [
        CAPABILITY_THIN_PACK,
        CAPABILITY_MULTI_ACK,
        CAPABILITY_MULTI_ACK_DETAILED,
        CAPABILITY_INCLUDE_TAG,
        CAPABILITY_DEEPEN_SINCE,
        CAPABILITY_SYMREF,
        CAPABILITY_SHALLOW,
        CAPABILITY_DEEPEN_NOT,
        CAPABILITY_DEEPEN_RELATIVE,
        CAPABILITY_ALLOW_TIP_SHA1_IN_WANT,
        CAPABILITY_ALLOW_REACHABLE_SHA1_IN_WANT,
    ]
)
KNOWN_RECEIVE_CAPABILITIES = set(
    COMMON_CAPABILITIES
    + [
        CAPABILITY_REPORT_STATUS,
        CAPABILITY_DELETE_REFS,
        CAPABILITY_QUIET,
        CAPABILITY_ATOMIC,
    ]
)

DEPTH_INFINITE = 0x7FFFFFFF

NAK_LINE = b"NAK\n"


def agent_string():
    return ("dulwich/" + ".".join(map(str, dulwich.__version__))).encode("ascii")


def capability_agent():
    return CAPABILITY_AGENT + b"=" + agent_string()


def capability_symref(from_ref, to_ref):
    return CAPABILITY_SYMREF + b"=" + from_ref + b":" + to_ref


def extract_capability_names(capabilities):
    return {parse_capability(c)[0] for c in capabilities}


def parse_capability(capability):
    parts = capability.split(b"=", 1)
    if len(parts) == 1:
        return (parts[0], None)
    return tuple(parts)


def symref_capabilities(symrefs):
    return [capability_symref(*k) for k in symrefs]


COMMAND_DEEPEN = b"deepen"
COMMAND_SHALLOW = b"shallow"
COMMAND_UNSHALLOW = b"unshallow"
COMMAND_DONE = b"done"
COMMAND_WANT = b"want"
COMMAND_HAVE = b"have"


def format_cmd_pkt(cmd, *args):
    return cmd + b" " + b"".join([(a + b"\0") for a in args])


def parse_cmd_pkt(line):
    splice_at = line.find(b" ")
    cmd, args = line[:splice_at], line[splice_at + 1 :]
    assert args[-1:] == b"\x00"
    return cmd, args[:-1].split(b"\0")


def pkt_line(data):
    """Wrap data in a pkt-line.

    Args:
      data: The data to wrap, as a str or None.
    Returns: The data prefixed with its length in pkt-line format; if data was
        None, returns the flush-pkt ('0000').
    """
    if data is None:
        return b"0000"
    return ("%04x" % (len(data) + 4)).encode("ascii") + data


class Protocol:
    """Class for interacting with a remote git process over the wire.

    Parts of the git wire protocol use 'pkt-lines' to communicate. A pkt-line
    consists of the length of the line as a 4-byte hex string, followed by the
    payload data. The length includes the 4-byte header. The special line
    '0000' indicates the end of a section of input and is called a 'flush-pkt'.

    For details on the pkt-line format, see the cgit distribution:
        Documentation/technical/protocol-common.txt
    """

    def __init__(self, read, write, close=None, report_activity=None):
        self.read = read
        self.write = write
        self._close = close
        self.report_activity = report_activity
        self._readahead = None

    def close(self):
        if self._close:
            self._close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def read_pkt_line(self):
        """Reads a pkt-line from the remote git process.

        This method may read from the readahead buffer; see unread_pkt_line.

        Returns: The next string from the stream, without the length prefix, or
            None for a flush-pkt ('0000').
        """
        if self._readahead is None:
            read = self.read
        else:
            read = self._readahead.read
            self._readahead = None

        try:
            sizestr = read(4)
            if not sizestr:
                raise HangupException()
            size = int(sizestr, 16)
            if size == 0:
                if self.report_activity:
                    self.report_activity(4, "read")
                return None
            if self.report_activity:
                self.report_activity(size, "read")
            pkt_contents = read(size - 4)
        except ConnectionResetError as exc:
            raise HangupException() from exc
        except OSError as exc:
            raise GitProtocolError(str(exc)) from exc
        else:
            if len(pkt_contents) + 4 != size:
                raise GitProtocolError(
                    "Length of pkt read %04x does not match length prefix %04x"
                    % (len(pkt_contents) + 4, size)
                )
            return pkt_contents

    def eof(self):
        """Test whether the protocol stream has reached EOF.

        Note that this refers to the actual stream EOF and not just a
        flush-pkt.

        Returns: True if the stream is at EOF, False otherwise.
        """
        try:
            next_line = self.read_pkt_line()
        except HangupException:
            return True
        self.unread_pkt_line(next_line)
        return False

    def unread_pkt_line(self, data):
        """Unread a single line of data into the readahead buffer.

        This method can be used to unread a single pkt-line into a fixed
        readahead buffer.

        Args:
          data: The data to unread, without the length prefix.
        Raises:
          ValueError: If more than one pkt-line is unread.
        """
        if self._readahead is not None:
            raise ValueError("Attempted to unread multiple pkt-lines.")
        self._readahead = BytesIO(pkt_line(data))

    def read_pkt_seq(self):
        """Read a sequence of pkt-lines from the remote git process.

        Returns: Yields each line of data up to but not including the next
            flush-pkt.
        """
        pkt = self.read_pkt_line()
        while pkt:
            yield pkt
            pkt = self.read_pkt_line()

    def write_pkt_line(self, line):
        """Sends a pkt-line to the remote git process.

        Args:
          line: A string containing the data to send, without the length
            prefix.
        """
        try:
            line = pkt_line(line)
            self.write(line)
            if self.report_activity:
                self.report_activity(len(line), "write")
        except OSError as exc:
            raise GitProtocolError(str(exc)) from exc

    def write_sideband(self, channel, blob):
        """Write multiplexed data to the sideband.

        Args:
          channel: An int specifying the channel to write to.
          blob: A blob of data (as a string) to send on this channel.
        """
        # a pktline can be a max of 65520. a sideband line can therefore be
        # 65520-5 = 65515
        # WTF: Why have the len in ASCII, but the channel in binary.
        while blob:
            self.write_pkt_line(bytes(bytearray([channel])) + blob[:65515])
            blob = blob[65515:]

    def send_cmd(self, cmd, *args):
        """Send a command and some arguments to a git server.

        Only used for the TCP git protocol (git://).

        Args:
          cmd: The remote service to access.
          args: List of arguments to send to remove service.
        """
        self.write_pkt_line(format_cmd_pkt(cmd, *args))

    def read_cmd(self):
        """Read a command and some arguments from the git client

        Only used for the TCP git protocol (git://).

        Returns: A tuple of (command, [list of arguments]).
        """
        line = self.read_pkt_line()
        return parse_cmd_pkt(line)


_RBUFSIZE = 8192  # Default read buffer size.


class ReceivableProtocol(Protocol):
    """Variant of Protocol that allows reading up to a size without blocking.

    This class has a recv() method that behaves like socket.recv() in addition
    to a read() method.

    If you want to read n bytes from the wire and block until exactly n bytes
    (or EOF) are read, use read(n). If you want to read at most n bytes from
    the wire but don't care if you get less, use recv(n). Note that recv(n)
    will still block until at least one byte is read.
    """

    def __init__(
        self, recv, write, close=None, report_activity=None, rbufsize=_RBUFSIZE
    ):
        super().__init__(
            self.read, write, close=close, report_activity=report_activity
        )
        self._recv = recv
        self._rbuf = BytesIO()
        self._rbufsize = rbufsize

    def read(self, size):
        # From _fileobj.read in socket.py in the Python 2.6.5 standard library,
        # with the following modifications:
        #  - omit the size <= 0 branch
        #  - seek back to start rather than 0 in case some buffer has been
        #    consumed.
        #  - use SEEK_END instead of the magic number.
        # Copyright (c) 2001-2010 Python Software Foundation; All Rights
        # Reserved
        # Licensed under the Python Software Foundation License.
        # TODO: see if buffer is more efficient than cBytesIO.
        assert size > 0

        # Our use of BytesIO rather than lists of string objects returned by
        # recv() minimizes memory usage and fragmentation that occurs when
        # rbufsize is large compared to the typical return value of recv().
        buf = self._rbuf
        start = buf.tell()
        buf.seek(0, SEEK_END)
        # buffer may have been partially consumed by recv()
        buf_len = buf.tell() - start
        if buf_len >= size:
            # Already have size bytes in our buffer?  Extract and return.
            buf.seek(start)
            rv = buf.read(size)
            self._rbuf = BytesIO()
            self._rbuf.write(buf.read())
            self._rbuf.seek(0)
            return rv

        self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
        while True:
            left = size - buf_len
            # recv() will malloc the amount of memory given as its
            # parameter even though it often returns much less data
            # than that.  The returned data string is short lived
            # as we copy it into a BytesIO and free it.  This avoids
            # fragmentation issues on many platforms.
            data = self._recv(left)
            if not data:
                break
            n = len(data)
            if n == size and not buf_len:
                # Shortcut.  Avoid buffer data copies when:
                # - We have no data in our buffer.
                # AND
                # - Our call to recv returned exactly the
                #   number of bytes we were asked to read.
                return data
            if n == left:
                buf.write(data)
                del data  # explicit free
                break
            assert n <= left, "_recv(%d) returned %d bytes" % (left, n)
            buf.write(data)
            buf_len += n
            del data  # explicit free
            # assert buf_len == buf.tell()
        buf.seek(start)
        return buf.read()

    def recv(self, size):
        assert size > 0

        buf = self._rbuf
        start = buf.tell()
        buf.seek(0, SEEK_END)
        buf_len = buf.tell()
        buf.seek(start)

        left = buf_len - start
        if not left:
            # only read from the wire if our read buffer is exhausted
            data = self._recv(self._rbufsize)
            if len(data) == size:
                # shortcut: skip the buffer if we read exactly size bytes
                return data
            buf = BytesIO()
            buf.write(data)
            buf.seek(0)
            del data  # explicit free
            self._rbuf = buf
        return buf.read(size)


def extract_capabilities(text):
    """Extract a capabilities list from a string, if present.

    Args:
      text: String to extract from
    Returns: Tuple with text with capabilities removed and list of capabilities
    """
    if b"\0" not in text:
        return text, []
    text, capabilities = text.rstrip().split(b"\0")
    return (text, capabilities.strip().split(b" "))


def extract_want_line_capabilities(text):
    """Extract a capabilities list from a want line, if present.

    Note that want lines have capabilities separated from the rest of the line
    by a space instead of a null byte. Thus want lines have the form:

        want obj-id cap1 cap2 ...

    Args:
      text: Want line to extract from
    Returns: Tuple with text with capabilities removed and list of capabilities
    """
    split_text = text.rstrip().split(b" ")
    if len(split_text) < 3:
        return text, []
    return (b" ".join(split_text[:2]), split_text[2:])


def ack_type(capabilities):
    """Extract the ack type from a capabilities list."""
    if b"multi_ack_detailed" in capabilities:
        return MULTI_ACK_DETAILED
    elif b"multi_ack" in capabilities:
        return MULTI_ACK
    return SINGLE_ACK


class BufferedPktLineWriter:
    """Writer that wraps its data in pkt-lines and has an independent buffer.

    Consecutive calls to write() wrap the data in a pkt-line and then buffers
    it until enough lines have been written such that their total length
    (including length prefix) reach the buffer size.
    """

    def __init__(self, write, bufsize=65515):
        """Initialize the BufferedPktLineWriter.

        Args:
          write: A write callback for the underlying writer.
          bufsize: The internal buffer size, including length prefixes.
        """
        self._write = write
        self._bufsize = bufsize
        self._wbuf = BytesIO()
        self._buflen = 0

    def write(self, data):
        """Write data, wrapping it in a pkt-line."""
        line = pkt_line(data)
        line_len = len(line)
        over = self._buflen + line_len - self._bufsize
        if over >= 0:
            start = line_len - over
            self._wbuf.write(line[:start])
            self.flush()
        else:
            start = 0
        saved = line[start:]
        self._wbuf.write(saved)
        self._buflen += len(saved)

    def flush(self):
        """Flush all data from the buffer."""
        data = self._wbuf.getvalue()
        if data:
            self._write(data)
        self._len = 0
        self._wbuf = BytesIO()


class PktLineParser:
    """Packet line parser that hands completed packets off to a callback."""

    def __init__(self, handle_pkt):
        self.handle_pkt = handle_pkt
        self._readahead = BytesIO()

    def parse(self, data):
        """Parse a fragment of data and call back for any completed packets."""
        self._readahead.write(data)
        buf = self._readahead.getvalue()
        if len(buf) < 4:
            return
        while len(buf) >= 4:
            size = int(buf[:4], 16)
            if size == 0:
                self.handle_pkt(None)
                buf = buf[4:]
            elif size <= len(buf):
                self.handle_pkt(buf[4:size])
                buf = buf[size:]
            else:
                break
        self._readahead = BytesIO()
        self._readahead.write(buf)

    def get_tail(self):
        """Read back any unused data."""
        return self._readahead.getvalue()


def format_capability_line(capabilities):
    return b"".join([b" " + c for c in capabilities])


def format_ref_line(ref, sha, capabilities=None):
    if capabilities is None:
        return sha + b" " + ref + b"\n"
    else:
        return (
            sha + b" " + ref + b"\0"
            + format_capability_line(capabilities)
            + b"\n")


def format_shallow_line(sha):
    return COMMAND_SHALLOW + b" " + sha


def format_unshallow_line(sha):
    return COMMAND_UNSHALLOW + b" " + sha


def format_ack_line(sha, ack_type=b""):
    if ack_type:
        ack_type = b" " + ack_type
    return b"ACK " + sha + ack_type + b"\n"
