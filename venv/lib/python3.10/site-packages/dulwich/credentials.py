# credentials.py -- support for git credential helpers

# Copyright (C) 2022 Daniele Trifirò <daniele@iterative.ai>
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

"""Support for git credential helpers

https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage

"""
import sys
from typing import Iterator, Optional
from urllib.parse import ParseResult, urlparse

from .config import ConfigDict, SectionLike


def match_urls(url: ParseResult, url_prefix: ParseResult) -> bool:
    base_match = (
        url.scheme == url_prefix.scheme
        and url.hostname == url_prefix.hostname
        and url.port == url_prefix.port
    )
    user_match = url.username == url_prefix.username if url_prefix.username else True
    path_match = url.path.rstrip("/").startswith(url_prefix.path.rstrip())
    return base_match and user_match and path_match


def match_partial_url(valid_url: ParseResult, partial_url: str) -> bool:
    """matches a parsed url with a partial url (no scheme/netloc)"""
    if "://" not in partial_url:
        parsed = urlparse("scheme://" + partial_url)
    else:
        parsed = urlparse(partial_url)
        if valid_url.scheme != parsed.scheme:
            return False

    if any(
        (
            (parsed.hostname and valid_url.hostname != parsed.hostname),
            (parsed.username and valid_url.username != parsed.username),
            (parsed.port and valid_url.port != parsed.port),
            (parsed.path and parsed.path.rstrip("/") != valid_url.path.rstrip("/")),
        ),
    ):
        return False

    return True


def urlmatch_credential_sections(
    config: ConfigDict, url: Optional[str]
) -> Iterator[SectionLike]:
    """Returns credential sections from the config which match the given URL"""
    encoding = config.encoding or sys.getdefaultencoding()
    parsed_url = urlparse(url or "")
    for config_section in config.sections():
        if config_section[0] != b"credential":
            continue

        if len(config_section) < 2:
            yield config_section
            continue

        config_url = config_section[1].decode(encoding)
        parsed_config_url = urlparse(config_url)
        if parsed_config_url.scheme and parsed_config_url.netloc:
            is_match = match_urls(parsed_url, parsed_config_url)
        else:
            is_match = match_partial_url(parsed_url, config_url)

        if is_match:
            yield config_section
