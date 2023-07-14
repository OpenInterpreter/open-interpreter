# reflog.py -- Parsing and writing reflog files
# Copyright (C) 2015 Jelmer Vernooij and others.
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

"""Utilities for reading and generating reflogs.
"""

import collections

from .objects import ZERO_SHA, format_timezone, parse_timezone

Entry = collections.namedtuple(
    "Entry",
    ["old_sha", "new_sha", "committer", "timestamp", "timezone", "message"],
)


def format_reflog_line(old_sha, new_sha, committer, timestamp, timezone, message):
    """Generate a single reflog line.

    Args:
      old_sha: Old Commit SHA
      new_sha: New Commit SHA
      committer: Committer name and e-mail
      timestamp: Timestamp
      timezone: Timezone
      message: Message
    """
    if old_sha is None:
        old_sha = ZERO_SHA
    return (
        old_sha
        + b" "
        + new_sha
        + b" "
        + committer
        + b" "
        + str(int(timestamp)).encode("ascii")
        + b" "
        + format_timezone(timezone)
        + b"\t"
        + message
    )


def parse_reflog_line(line):
    """Parse a reflog line.

    Args:
      line: Line to parse
    Returns: Tuple of (old_sha, new_sha, committer, timestamp, timezone,
        message)
    """
    (begin, message) = line.split(b"\t", 1)
    (old_sha, new_sha, rest) = begin.split(b" ", 2)
    (committer, timestamp_str, timezone_str) = rest.rsplit(b" ", 2)
    return Entry(
        old_sha,
        new_sha,
        committer,
        int(timestamp_str),
        parse_timezone(timezone_str)[0],
        message,
    )


def read_reflog(f):
    """Read reflog.

    Args:
      f: File-like object
    Returns: Iterator over Entry objects
    """
    for line in f:
        yield parse_reflog_line(line)


def drop_reflog_entry(f, index, rewrite=False):
    """Drop the specified reflog entry.

    Args:
        f: File-like object
        index: Reflog entry index (in Git reflog reverse 0-indexed order)
        rewrite: If a reflog entry's predecessor is removed, set its
            old SHA to the new SHA of the entry that now precedes it
    """
    if index < 0:
        raise ValueError("Invalid reflog index %d" % index)

    log = []
    offset = f.tell()
    for line in f:
        log.append((offset, parse_reflog_line(line)))
        offset = f.tell()

    inverse_index = len(log) - index - 1
    write_offset = log[inverse_index][0]
    f.seek(write_offset)

    if index == 0:
        f.truncate()
        return

    del log[inverse_index]
    if rewrite and index > 0 and log:
        if inverse_index == 0:
            previous_new = ZERO_SHA
        else:
            previous_new = log[inverse_index - 1][1].new_sha
        offset, entry = log[inverse_index]
        log[inverse_index] = (
            offset,
            Entry(
                previous_new,
                entry.new_sha,
                entry.committer,
                entry.timestamp,
                entry.timezone,
                entry.message,
            ),
        )

    for _, entry in log[inverse_index:]:
        f.write(
            format_reflog_line(
                entry.old_sha,
                entry.new_sha,
                entry.committer,
                entry.timestamp,
                entry.timezone,
                entry.message,
            )
        )
    f.truncate()
