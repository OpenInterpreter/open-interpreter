# test_config.py -- Tests for reading and writing configuration files
# Copyright (C) 2011 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Tests for reading and writing configuration files."""

import os
import sys
from io import BytesIO
from unittest import skipIf
from unittest.mock import patch

from dulwich.tests import TestCase

from ..config import (ConfigDict, ConfigFile, StackedConfig,
                      _check_section_name, _check_variable_name, _escape_value,
                      _format_string, _parse_string, apply_instead_of,
                      parse_submodules)


class ConfigFileTests(TestCase):
    def from_file(self, text):
        return ConfigFile.from_file(BytesIO(text))

    def test_empty(self):
        ConfigFile()

    def test_eq(self):
        self.assertEqual(ConfigFile(), ConfigFile())

    def test_default_config(self):
        cf = self.from_file(
            b"""[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tlogallrefupdates = true
"""
        )
        self.assertEqual(
            ConfigFile(
                {
                    (b"core",): {
                        b"repositoryformatversion": b"0",
                        b"filemode": b"true",
                        b"bare": b"false",
                        b"logallrefupdates": b"true",
                    }
                }
            ),
            cf,
        )

    def test_from_file_empty(self):
        cf = self.from_file(b"")
        self.assertEqual(ConfigFile(), cf)

    def test_empty_line_before_section(self):
        cf = self.from_file(b"\n[section]\n")
        self.assertEqual(ConfigFile({(b"section",): {}}), cf)

    def test_comment_before_section(self):
        cf = self.from_file(b"# foo\n[section]\n")
        self.assertEqual(ConfigFile({(b"section",): {}}), cf)

    def test_comment_after_section(self):
        cf = self.from_file(b"[section] # foo\n")
        self.assertEqual(ConfigFile({(b"section",): {}}), cf)

    def test_comment_after_variable(self):
        cf = self.from_file(b"[section]\nbar= foo # a comment\n")
        self.assertEqual(ConfigFile({(b"section",): {b"bar": b"foo"}}), cf)

    def test_comment_character_within_value_string(self):
        cf = self.from_file(b'[section]\nbar= "foo#bar"\n')
        self.assertEqual(ConfigFile({(b"section",): {b"bar": b"foo#bar"}}), cf)

    def test_comment_character_within_section_string(self):
        cf = self.from_file(b'[branch "foo#bar"] # a comment\nbar= foo\n')
        self.assertEqual(ConfigFile({(b"branch", b"foo#bar"): {b"bar": b"foo"}}), cf)

    def test_closing_bracket_within_section_string(self):
        cf = self.from_file(b'[branch "foo]bar"] # a comment\nbar= foo\n')
        self.assertEqual(ConfigFile({(b"branch", b"foo]bar"): {b"bar": b"foo"}}), cf)

    def test_from_file_section(self):
        cf = self.from_file(b"[core]\nfoo = bar\n")
        self.assertEqual(b"bar", cf.get((b"core",), b"foo"))
        self.assertEqual(b"bar", cf.get((b"core", b"foo"), b"foo"))

    def test_from_file_multiple(self):
        cf = self.from_file(b"[core]\nfoo = bar\nfoo = blah\n")
        self.assertEqual([b"bar", b"blah"], list(cf.get_multivar((b"core",), b"foo")))
        self.assertEqual([], list(cf.get_multivar((b"core", ), b"blah")))

    def test_from_file_utf8_bom(self):
        text = "[core]\nfoo = b\u00e4r\n".encode("utf-8-sig")
        cf = self.from_file(text)
        self.assertEqual(b"b\xc3\xa4r", cf.get((b"core",), b"foo"))

    def test_from_file_section_case_insensitive_lower(self):
        cf = self.from_file(b"[cOre]\nfOo = bar\n")
        self.assertEqual(b"bar", cf.get((b"core",), b"foo"))
        self.assertEqual(b"bar", cf.get((b"core", b"foo"), b"foo"))

    def test_from_file_section_case_insensitive_mixed(self):
        cf = self.from_file(b"[cOre]\nfOo = bar\n")
        self.assertEqual(b"bar", cf.get((b"core",), b"fOo"))
        self.assertEqual(b"bar", cf.get((b"cOre", b"fOo"), b"fOo"))

    def test_from_file_with_mixed_quoted(self):
        cf = self.from_file(b'[core]\nfoo = "bar"la\n')
        self.assertEqual(b"barla", cf.get((b"core",), b"foo"))

    def test_from_file_section_with_open_brackets(self):
        self.assertRaises(ValueError, self.from_file, b"[core\nfoo = bar\n")

    def test_from_file_value_with_open_quoted(self):
        self.assertRaises(ValueError, self.from_file, b'[core]\nfoo = "bar\n')

    def test_from_file_with_quotes(self):
        cf = self.from_file(b"[core]\n" b'foo = " bar"\n')
        self.assertEqual(b" bar", cf.get((b"core",), b"foo"))

    def test_from_file_with_interrupted_line(self):
        cf = self.from_file(b"[core]\n" b"foo = bar\\\n" b" la\n")
        self.assertEqual(b"barla", cf.get((b"core",), b"foo"))

    def test_from_file_with_boolean_setting(self):
        cf = self.from_file(b"[core]\n" b"foo\n")
        self.assertEqual(b"true", cf.get((b"core",), b"foo"))

    def test_from_file_subsection(self):
        cf = self.from_file(b'[branch "foo"]\nfoo = bar\n')
        self.assertEqual(b"bar", cf.get((b"branch", b"foo"), b"foo"))

    def test_from_file_subsection_invalid(self):
        self.assertRaises(ValueError, self.from_file, b'[branch "foo]\nfoo = bar\n')

    def test_from_file_subsection_not_quoted(self):
        cf = self.from_file(b"[branch.foo]\nfoo = bar\n")
        self.assertEqual(b"bar", cf.get((b"branch", b"foo"), b"foo"))

    def test_write_preserve_multivar(self):
        cf = self.from_file(b"[core]\nfoo = bar\nfoo = blah\n")
        f = BytesIO()
        cf.write_to_file(f)
        self.assertEqual(b"[core]\n\tfoo = bar\n\tfoo = blah\n", f.getvalue())

    def test_write_to_file_empty(self):
        c = ConfigFile()
        f = BytesIO()
        c.write_to_file(f)
        self.assertEqual(b"", f.getvalue())

    def test_write_to_file_section(self):
        c = ConfigFile()
        c.set((b"core",), b"foo", b"bar")
        f = BytesIO()
        c.write_to_file(f)
        self.assertEqual(b"[core]\n\tfoo = bar\n", f.getvalue())

    def test_write_to_file_subsection(self):
        c = ConfigFile()
        c.set((b"branch", b"blie"), b"foo", b"bar")
        f = BytesIO()
        c.write_to_file(f)
        self.assertEqual(b'[branch "blie"]\n\tfoo = bar\n', f.getvalue())

    def test_same_line(self):
        cf = self.from_file(b"[branch.foo] foo = bar\n")
        self.assertEqual(b"bar", cf.get((b"branch", b"foo"), b"foo"))

    def test_quoted_newlines_windows(self):
        cf = self.from_file(
            b"[alias]\r\n"
            b"c = '!f() { \\\r\n"
            b" printf '[git commit -m \\\"%s\\\"]\\n' \\\"$*\\\" && \\\r\n"
            b" git commit -m \\\"$*\\\"; \\\r\n"
            b" }; f'\r\n")
        self.assertEqual(list(cf.sections()), [(b'alias', )])
        self.assertEqual(
            b'\'!f() { printf \'[git commit -m "%s"]\n\' '
            b'"$*" && git commit -m "$*"',
            cf.get((b"alias", ), b"c"))

    def test_quoted(self):
        cf = self.from_file(
            b"""[gui]
\tfontdiff = -family \\\"Ubuntu Mono\\\" -size 11 -overstrike 0
"""
        )
        self.assertEqual(
            ConfigFile(
                {
                    (b"gui",): {
                        b"fontdiff": b'-family "Ubuntu Mono" -size 11 -overstrike 0',
                    }
                }
            ),
            cf,
        )

    def test_quoted_multiline(self):
        cf = self.from_file(
            b"""[alias]
who = \"!who() {\\
  git log --no-merges --pretty=format:'%an - %ae' $@ | uniq -c | sort -rn;\\
};\\
who\"
"""
        )
        self.assertEqual(
            ConfigFile(
                {
                    (b"alias",): {
                        b"who": (
                            b"!who() {git log --no-merges --pretty=format:'%an - "
                            b"%ae' $@ | uniq -c | sort -rn;};who"
                        )
                    }
                }
            ),
            cf,
        )

    def test_set_hash_gets_quoted(self):
        c = ConfigFile()
        c.set(b"xandikos", b"color", b"#665544")
        f = BytesIO()
        c.write_to_file(f)
        self.assertEqual(b'[xandikos]\n\tcolor = "#665544"\n', f.getvalue())


class ConfigDictTests(TestCase):
    def test_get_set(self):
        cd = ConfigDict()
        self.assertRaises(KeyError, cd.get, b"foo", b"core")
        cd.set((b"core",), b"foo", b"bla")
        self.assertEqual(b"bla", cd.get((b"core",), b"foo"))
        cd.set((b"core",), b"foo", b"bloe")
        self.assertEqual(b"bloe", cd.get((b"core",), b"foo"))

    def test_get_boolean(self):
        cd = ConfigDict()
        cd.set((b"core",), b"foo", b"true")
        self.assertTrue(cd.get_boolean((b"core",), b"foo"))
        cd.set((b"core",), b"foo", b"false")
        self.assertFalse(cd.get_boolean((b"core",), b"foo"))
        cd.set((b"core",), b"foo", b"invalid")
        self.assertRaises(ValueError, cd.get_boolean, (b"core",), b"foo")

    def test_dict(self):
        cd = ConfigDict()
        cd.set((b"core",), b"foo", b"bla")
        cd.set((b"core2",), b"foo", b"bloe")

        self.assertEqual([(b"core",), (b"core2",)], list(cd.keys()))
        self.assertEqual(cd[(b"core",)], {b"foo": b"bla"})

        cd[b"a"] = b"b"
        self.assertEqual(cd[b"a"], b"b")

    def test_items(self):
        cd = ConfigDict()
        cd.set((b"core",), b"foo", b"bla")
        cd.set((b"core2",), b"foo", b"bloe")

        self.assertEqual([(b"foo", b"bla")], list(cd.items((b"core",))))

    def test_items_nonexistant(self):
        cd = ConfigDict()
        cd.set((b"core2",), b"foo", b"bloe")

        self.assertEqual([], list(cd.items((b"core",))))

    def test_sections(self):
        cd = ConfigDict()
        cd.set((b"core2",), b"foo", b"bloe")

        self.assertEqual([(b"core2",)], list(cd.sections()))


class StackedConfigTests(TestCase):
    def test_default_backends(self):
        StackedConfig.default_backends()

    @skipIf(sys.platform != "win32", "Windows specific config location.")
    def test_windows_config_from_path(self):
        from ..config import get_win_system_paths

        install_dir = os.path.join("C:", "foo", "Git")
        self.overrideEnv("PATH", os.path.join(install_dir, "cmd"))
        with patch("os.path.exists", return_value=True):
            paths = set(get_win_system_paths())
        self.assertEqual(
            {
                os.path.join(os.environ.get("PROGRAMDATA"), "Git", "config"),
                os.path.join(install_dir, "etc", "gitconfig"),
            },
            paths,
        )

    @skipIf(sys.platform != "win32", "Windows specific config location.")
    def test_windows_config_from_reg(self):
        import winreg

        from ..config import get_win_system_paths

        self.overrideEnv("PATH", None)
        install_dir = os.path.join("C:", "foo", "Git")
        with patch("winreg.OpenKey"):
            with patch(
                "winreg.QueryValueEx",
                return_value=(install_dir, winreg.REG_SZ),
            ):
                paths = set(get_win_system_paths())
        self.assertEqual(
            {
                os.path.join(os.environ.get("PROGRAMDATA"), "Git", "config"),
                os.path.join(install_dir, "etc", "gitconfig"),
            },
            paths,
        )


class EscapeValueTests(TestCase):
    def test_nothing(self):
        self.assertEqual(b"foo", _escape_value(b"foo"))

    def test_backslash(self):
        self.assertEqual(b"foo\\\\", _escape_value(b"foo\\"))

    def test_newline(self):
        self.assertEqual(b"foo\\n", _escape_value(b"foo\n"))


class FormatStringTests(TestCase):
    def test_quoted(self):
        self.assertEqual(b'" foo"', _format_string(b" foo"))
        self.assertEqual(b'"\\tfoo"', _format_string(b"\tfoo"))

    def test_not_quoted(self):
        self.assertEqual(b"foo", _format_string(b"foo"))
        self.assertEqual(b"foo bar", _format_string(b"foo bar"))


class ParseStringTests(TestCase):
    def test_quoted(self):
        self.assertEqual(b" foo", _parse_string(b'" foo"'))
        self.assertEqual(b"\tfoo", _parse_string(b'"\\tfoo"'))

    def test_not_quoted(self):
        self.assertEqual(b"foo", _parse_string(b"foo"))
        self.assertEqual(b"foo bar", _parse_string(b"foo bar"))

    def test_nothing(self):
        self.assertEqual(b"", _parse_string(b""))

    def test_tab(self):
        self.assertEqual(b"\tbar\t", _parse_string(b"\\tbar\\t"))

    def test_newline(self):
        self.assertEqual(b"\nbar\t", _parse_string(b"\\nbar\\t\t"))

    def test_quote(self):
        self.assertEqual(b'"foo"', _parse_string(b'\\"foo\\"'))


class CheckVariableNameTests(TestCase):
    def test_invalid(self):
        self.assertFalse(_check_variable_name(b"foo "))
        self.assertFalse(_check_variable_name(b"bar,bar"))
        self.assertFalse(_check_variable_name(b"bar.bar"))

    def test_valid(self):
        self.assertTrue(_check_variable_name(b"FOO"))
        self.assertTrue(_check_variable_name(b"foo"))
        self.assertTrue(_check_variable_name(b"foo-bar"))


class CheckSectionNameTests(TestCase):
    def test_invalid(self):
        self.assertFalse(_check_section_name(b"foo "))
        self.assertFalse(_check_section_name(b"bar,bar"))

    def test_valid(self):
        self.assertTrue(_check_section_name(b"FOO"))
        self.assertTrue(_check_section_name(b"foo"))
        self.assertTrue(_check_section_name(b"foo-bar"))
        self.assertTrue(_check_section_name(b"bar.bar"))


class SubmodulesTests(TestCase):
    def testSubmodules(self):
        cf = ConfigFile.from_file(
            BytesIO(
                b"""\
[submodule "core/lib"]
\tpath = core/lib
\turl = https://github.com/phhusson/QuasselC.git
"""
            )
        )
        got = list(parse_submodules(cf))
        self.assertEqual(
            [
                (
                    b"core/lib",
                    b"https://github.com/phhusson/QuasselC.git",
                    b"core/lib",
                )
            ],
            got,
        )


class ApplyInsteadOfTests(TestCase):
    def test_none(self):
        config = ConfigDict()
        self.assertEqual(
            'https://example.com/', apply_instead_of(config, 'https://example.com/'))

    def test_apply(self):
        config = ConfigDict()
        config.set(
            ('url', 'https://samba.org/'), 'insteadOf', 'https://example.com/')
        self.assertEqual(
            'https://samba.org/',
            apply_instead_of(config, 'https://example.com/'))

    def test_apply_multiple(self):
        config = ConfigDict()
        config.set(
            ('url', 'https://samba.org/'), 'insteadOf', 'https://blah.com/')
        config.set(
            ('url', 'https://samba.org/'), 'insteadOf', 'https://example.com/')
        self.assertEqual(
            [b'https://blah.com/', b'https://example.com/'],
            list(config.get_multivar(('url', 'https://samba.org/'), 'insteadOf')))
        self.assertEqual(
            'https://samba.org/',
            apply_instead_of(config, 'https://example.com/'))
