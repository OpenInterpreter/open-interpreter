# test_line_ending.py -- Tests for the line ending functions
# encoding: utf-8
# Copyright (C) 2018-2019 Boris Feld <boris.feld@comet.ml>
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

"""Tests for the line ending conversion."""

from dulwich.tests import TestCase

from ..line_ending import (convert_crlf_to_lf, convert_lf_to_crlf,
                           get_checkin_filter_autocrlf,
                           get_checkout_filter_autocrlf, normalize_blob)
from ..objects import Blob


class LineEndingConversion(TestCase):
    """Test the line ending conversion functions in various cases"""

    def test_convert_crlf_to_lf_no_op(self):
        self.assertEqual(convert_crlf_to_lf(b"foobar"), b"foobar")

    def test_convert_crlf_to_lf(self):
        self.assertEqual(convert_crlf_to_lf(b"line1\r\nline2"), b"line1\nline2")

    def test_convert_crlf_to_lf_mixed(self):
        self.assertEqual(convert_crlf_to_lf(b"line1\r\n\nline2"), b"line1\n\nline2")

    def test_convert_lf_to_crlf_no_op(self):
        self.assertEqual(convert_lf_to_crlf(b"foobar"), b"foobar")

    def test_convert_lf_to_crlf(self):
        self.assertEqual(convert_lf_to_crlf(b"line1\nline2"), b"line1\r\nline2")

    def test_convert_lf_to_crlf_mixed(self):
        self.assertEqual(convert_lf_to_crlf(b"line1\r\n\nline2"), b"line1\r\n\r\nline2")


class GetLineEndingAutocrlfFilters(TestCase):
    def test_get_checkin_filter_autocrlf_default(self):
        checkin_filter = get_checkin_filter_autocrlf(b"false")

        self.assertEqual(checkin_filter, None)

    def test_get_checkin_filter_autocrlf_true(self):
        checkin_filter = get_checkin_filter_autocrlf(b"true")

        self.assertEqual(checkin_filter, convert_crlf_to_lf)

    def test_get_checkin_filter_autocrlf_input(self):
        checkin_filter = get_checkin_filter_autocrlf(b"input")

        self.assertEqual(checkin_filter, convert_crlf_to_lf)

    def test_get_checkout_filter_autocrlf_default(self):
        checkout_filter = get_checkout_filter_autocrlf(b"false")

        self.assertEqual(checkout_filter, None)

    def test_get_checkout_filter_autocrlf_true(self):
        checkout_filter = get_checkout_filter_autocrlf(b"true")

        self.assertEqual(checkout_filter, convert_lf_to_crlf)

    def test_get_checkout_filter_autocrlf_input(self):
        checkout_filter = get_checkout_filter_autocrlf(b"input")

        self.assertEqual(checkout_filter, None)


class NormalizeBlobTestCase(TestCase):
    def test_normalize_to_lf_no_op(self):
        base_content = b"line1\nline2"
        base_sha = "f8be7bb828880727816015d21abcbc37d033f233"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_crlf_to_lf, binary_detection=False
        )

        self.assertEqual(filtered_blob.as_raw_chunks(), [base_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), base_sha)

    def test_normalize_to_lf(self):
        base_content = b"line1\r\nline2"
        base_sha = "3a1bd7a52799fe5cf6411f1d35f4c10bacb1db96"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_crlf_to_lf, binary_detection=False
        )

        normalized_content = b"line1\nline2"
        normalized_sha = "f8be7bb828880727816015d21abcbc37d033f233"

        self.assertEqual(filtered_blob.as_raw_chunks(), [normalized_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), normalized_sha)

    def test_normalize_to_lf_binary(self):
        base_content = b"line1\r\nline2\0"
        base_sha = "b44504193b765f7cd79673812de8afb55b372ab2"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_crlf_to_lf, binary_detection=True
        )

        self.assertEqual(filtered_blob.as_raw_chunks(), [base_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), base_sha)

    def test_normalize_to_crlf_no_op(self):
        base_content = b"line1\r\nline2"
        base_sha = "3a1bd7a52799fe5cf6411f1d35f4c10bacb1db96"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_lf_to_crlf, binary_detection=False
        )

        self.assertEqual(filtered_blob.as_raw_chunks(), [base_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), base_sha)

    def test_normalize_to_crlf(self):
        base_content = b"line1\nline2"
        base_sha = "f8be7bb828880727816015d21abcbc37d033f233"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_lf_to_crlf, binary_detection=False
        )

        normalized_content = b"line1\r\nline2"
        normalized_sha = "3a1bd7a52799fe5cf6411f1d35f4c10bacb1db96"

        self.assertEqual(filtered_blob.as_raw_chunks(), [normalized_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), normalized_sha)

    def test_normalize_to_crlf_binary(self):
        base_content = b"line1\r\nline2\0"
        base_sha = "b44504193b765f7cd79673812de8afb55b372ab2"

        base_blob = Blob()
        base_blob.set_raw_string(base_content)

        self.assertEqual(base_blob.as_raw_chunks(), [base_content])
        self.assertEqual(base_blob.sha().hexdigest(), base_sha)

        filtered_blob = normalize_blob(
            base_blob, convert_lf_to_crlf, binary_detection=True
        )

        self.assertEqual(filtered_blob.as_raw_chunks(), [base_content])
        self.assertEqual(filtered_blob.sha().hexdigest(), base_sha)
