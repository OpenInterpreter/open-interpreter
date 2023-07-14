# errors.py -- errors for dulwich
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
# Copyright (C) 2009-2012 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Dulwich-related exception classes and utility functions."""


# Please do not add more errors here, but instead add them close to the code
# that raises the error.


import binascii


class ChecksumMismatch(Exception):
    """A checksum didn't match the expected contents."""

    def __init__(self, expected, got, extra=None):
        if len(expected) == 20:
            expected = binascii.hexlify(expected)
        if len(got) == 20:
            got = binascii.hexlify(got)
        self.expected = expected
        self.got = got
        self.extra = extra
        if self.extra is None:
            Exception.__init__(
                self,
                "Checksum mismatch: Expected {}, got {}".format(expected, got),
            )
        else:
            Exception.__init__(
                self,
                "Checksum mismatch: Expected {}, got {}; {}".format(expected, got, extra),
            )


class WrongObjectException(Exception):
    """Baseclass for all the _ is not a _ exceptions on objects.

    Do not instantiate directly.

    Subclasses should define a type_name attribute that indicates what
    was expected if they were raised.
    """

    type_name: str

    def __init__(self, sha, *args, **kwargs):
        Exception.__init__(self, "{} is not a {}".format(sha, self.type_name))


class NotCommitError(WrongObjectException):
    """Indicates that the sha requested does not point to a commit."""

    type_name = "commit"


class NotTreeError(WrongObjectException):
    """Indicates that the sha requested does not point to a tree."""

    type_name = "tree"


class NotTagError(WrongObjectException):
    """Indicates that the sha requested does not point to a tag."""

    type_name = "tag"


class NotBlobError(WrongObjectException):
    """Indicates that the sha requested does not point to a blob."""

    type_name = "blob"


class MissingCommitError(Exception):
    """Indicates that a commit was not found in the repository"""

    def __init__(self, sha, *args, **kwargs):
        self.sha = sha
        Exception.__init__(self, "%s is not in the revision store" % sha)


class ObjectMissing(Exception):
    """Indicates that a requested object is missing."""

    def __init__(self, sha, *args, **kwargs):
        Exception.__init__(self, "%s is not in the pack" % sha)


class ApplyDeltaError(Exception):
    """Indicates that applying a delta failed."""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class NotGitRepository(Exception):
    """Indicates that no Git repository was found."""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class GitProtocolError(Exception):
    """Git protocol exception."""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.args == other.args


class SendPackError(GitProtocolError):
    """An error occurred during send_pack."""


class HangupException(GitProtocolError):
    """Hangup exception."""

    def __init__(self, stderr_lines=None):
        if stderr_lines:
            super().__init__(
                "\n".join(
                    [line.decode("utf-8", "surrogateescape") for line in stderr_lines]
                )
            )
        else:
            super().__init__(
                "The remote server unexpectedly closed the connection."
            )
        self.stderr_lines = stderr_lines

    def __eq__(self, other):
        return isinstance(self, type(other)) and self.stderr_lines == other.stderr_lines


class UnexpectedCommandError(GitProtocolError):
    """Unexpected command received in a proto line."""

    def __init__(self, command):
        if command is None:
            command = "flush-pkt"
        else:
            command = "command %s" % command
        super().__init__(
            "Protocol got unexpected %s" % command
        )


class FileFormatException(Exception):
    """Base class for exceptions relating to reading git file formats."""


class PackedRefsException(FileFormatException):
    """Indicates an error parsing a packed-refs file."""


class ObjectFormatException(FileFormatException):
    """Indicates an error parsing an object."""


class NoIndexPresent(Exception):
    """No index is present."""


class CommitError(Exception):
    """An error occurred while performing a commit."""


class RefFormatError(Exception):
    """Indicates an invalid ref name."""


class HookError(Exception):
    """An error occurred while executing a hook."""
