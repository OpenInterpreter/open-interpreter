# test_credentials.py -- tests for credentials.py

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

from urllib.parse import urlparse

from dulwich.tests import TestCase

from ..config import ConfigDict
from ..credentials import (match_partial_url, match_urls,
                           urlmatch_credential_sections)


class TestCredentialHelpersUtils(TestCase):

    def test_match_urls(self):
        url = urlparse("https://github.com/jelmer/dulwich/")
        url_1 = urlparse("https://github.com/jelmer/dulwich")
        url_2 = urlparse("https://github.com/jelmer")
        url_3 = urlparse("https://github.com")
        self.assertTrue(match_urls(url, url_1))
        self.assertTrue(match_urls(url, url_2))
        self.assertTrue(match_urls(url, url_3))

        non_matching = urlparse("https://git.sr.ht/")
        self.assertFalse(match_urls(url, non_matching))

    def test_match_partial_url(self):
        url = urlparse("https://github.com/jelmer/dulwich/")
        self.assertTrue(match_partial_url(url, "github.com"))
        self.assertFalse(match_partial_url(url, "github.com/jelmer/"))
        self.assertTrue(match_partial_url(url, "github.com/jelmer/dulwich"))
        self.assertFalse(match_partial_url(url, "github.com/jel"))
        self.assertFalse(match_partial_url(url, "github.com/jel/"))

    def test_urlmatch_credential_sections(self):
        config = ConfigDict()
        config.set((b"credential", "https://github.com"), b"helper", "foo")
        config.set((b"credential", "git.sr.ht"), b"helper", "foo")
        config.set(b"credential", b"helper", "bar")

        self.assertEqual(
            list(urlmatch_credential_sections(config, "https://github.com")), [
                (b"credential", b"https://github.com"),
                (b"credential",),
            ])

        self.assertEqual(
            list(urlmatch_credential_sections(config, "https://git.sr.ht")), [
                (b"credential", b"git.sr.ht"),
                (b"credential",),
            ])

        self.assertEqual(
            list(urlmatch_credential_sections(config, "missing_url")), [
                (b"credential",)])
