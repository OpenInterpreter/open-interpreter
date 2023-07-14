# release_robot.py
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

"""Determine last version string from tags.

Alternate to `Versioneer <https://pypi.python.org/pypi/versioneer/>`_ using
`Dulwich <https://pypi.python.org/pypi/dulwich>`_ to sort tags by time from
newest to oldest.

Copy the following into the package ``__init__.py`` module::

    from dulwich.contrib.release_robot import get_current_version
    __version__ = get_current_version()

This example assumes the tags have a leading "v" like "v0.3", and that the
``.git`` folder is in a project folder that contains the package folder.

EG::

    * project
    |
    * .git
    |
    +-* package
      |
      * __init__.py  <-- put __version__ here


"""

import datetime
import re
import sys
import time

from ..repo import Repo

# CONSTANTS
PROJDIR = "."
PATTERN = r"[ a-zA-Z_\-]*([\d\.]+[\-\w\.]*)"


def get_recent_tags(projdir=PROJDIR):
    """Get list of tags in order from newest to oldest and their datetimes.

    Args:
      projdir: path to ``.git``
    Returns:
      list of tags sorted by commit time from newest to oldest

    Each tag in the list contains the tag name, commit time, commit id, author
    and any tag meta. If a tag isn't annotated, then its tag meta is ``None``.
    Otherwise the tag meta is a tuple containing the tag time, tag id and tag
    name. Time is in UTC.
    """
    with Repo(projdir) as project:  # dulwich repository object
        refs = project.get_refs()  # dictionary of refs and their SHA-1 values
        tags = {}  # empty dictionary to hold tags, commits and datetimes
        # iterate over refs in repository
        for key, value in refs.items():
            key = key.decode("utf-8")  # compatible with Python-3
            obj = project.get_object(value)  # dulwich object from SHA-1
            # don't just check if object is "tag" b/c it could be a "commit"
            # instead check if "tags" is in the ref-name
            if "tags" not in key:
                # skip ref if not a tag
                continue
            # strip the leading text from refs to get "tag name"
            _, tag = key.rsplit("/", 1)
            # check if tag object is "commit" or "tag" pointing to a "commit"
            try:
                commit = obj.object  # a tuple (commit class, commit id)
            except AttributeError:
                commit = obj
                tag_meta = None
            else:
                tag_meta = (
                    datetime.datetime(*time.gmtime(obj.tag_time)[:6]),
                    obj.id.decode("utf-8"),
                    obj.name.decode("utf-8"),
                )  # compatible with Python-3
                commit = project.get_object(commit[1])  # commit object
            # get tag commit datetime, but dulwich returns seconds since
            # beginning of epoch, so use Python time module to convert it to
            # timetuple then convert to datetime
            tags[tag] = [
                datetime.datetime(*time.gmtime(commit.commit_time)[:6]),
                commit.id.decode("utf-8"),
                commit.author.decode("utf-8"),
                tag_meta,
            ]  # compatible with Python-3

    # return list of tags sorted by their datetimes from newest to oldest
    return sorted(tags.items(), key=lambda tag: tag[1][0], reverse=True)


def get_current_version(projdir=PROJDIR, pattern=PATTERN, logger=None):
    """Return the most recent tag, using an options regular expression pattern.

    The default pattern will strip any characters preceding the first semantic
    version. *EG*: "Release-0.2.1-rc.1" will be come "0.2.1-rc.1". If no match
    is found, then the most recent tag is return without modification.

    Args:
      projdir: path to ``.git``
      pattern: regular expression pattern with group that matches version
      logger: a Python logging instance to capture exception
    Returns:
      tag matching first group in regular expression pattern
    """
    tags = get_recent_tags(projdir)
    try:
        tag = tags[0][0]
    except IndexError:
        return
    matches = re.match(pattern, tag)
    try:
        current_version = matches.group(1)
    except (IndexError, AttributeError) as err:
        if logger:
            logger.exception(err)
        return tag
    return current_version


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _PROJDIR = sys.argv[1]
    else:
        _PROJDIR = PROJDIR
    print(get_current_version(projdir=_PROJDIR))
