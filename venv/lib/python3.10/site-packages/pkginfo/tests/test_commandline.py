import collections
import io
import json as json_module
import sys
import unittest

class Test__parse_options(unittest.TestCase):

    def _callFUT(self, args):
        from pkginfo.commandline import _parse_options
        return _parse_options(args)

    def test_empty(self):
        from pkginfo.commandline import __doc__ as usage

        firstline = usage.splitlines()[0]
        buf = io.StringIO()

        with _Monkey(sys, stderr=buf):
            self.assertRaises(SystemExit, self._callFUT, [])
        self.assertTrue(firstline in buf.getvalue())

    def test_nonempty(self):
        options, args = self._callFUT(['foo'])
        self.assertEqual(args, ['foo'])

class BaseTests(unittest.TestCase):

    def _getTargetClass(self):
        from pkginfo.commandline import Base

        return Base

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___init___defaults(self):
        base = self._makeOne(_Options(fields=()))
        self.assertTrue(base._fields is None)

    def test___init___w_fields(self):
        fields = object()
        base = self._makeOne(_Options(fields=fields))
        self.assertTrue(base._fields is fields)

class _FormatterBase(object):

    def _capture_output(self, func, *args, **kw):
        buf = io.StringIO()

        with _Monkey(sys, stdout=buf):
            func(*args, **kw)
        return buf.getvalue()

    def _no_output(self, simple, meta):
        with _Monkey(sys, stdout=object()):  # raise if write
            simple(meta)

class SimpleTests(unittest.TestCase, _FormatterBase):

    def _getTargetClass(self):
        from pkginfo.commandline import Simple
        return Simple

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___init___(self):
        simple = self._makeOne(_Options(fields=None, skip=True))
        self.assertTrue(simple._skip)

    def test___call___w_empty_fields(self):
        simple = self._makeOne(_Options(fields=(), skip=False))
        meta = _Meta()
        self._no_output(simple, meta)

    def test___call___w_skip_and_value_None_no_fields(self):
        simple = self._makeOne(_Options(fields=(), skip=True))
        meta = _Meta(foo=None)
        self._no_output(simple, meta)

    def test___call___w_skip_and_value_empty_tuple_explicit_fields(self):
        simple = self._makeOne(_Options(fields=('foo',), skip=True))
        meta = _Meta(foo=(), bar='Bar')
        self._no_output(simple, meta)

    def test___call___w_skip_but_values_explicit_fields(self):
        simple = self._makeOne(_Options(fields=('foo',), skip=True))
        meta = _Meta(foo='Foo')
        output = self._capture_output(simple, meta)
        self.assertEqual(output, 'foo: Foo\n')

class SingleLineTests(unittest.TestCase, _FormatterBase):

    def _getTargetClass(self):
        from pkginfo.commandline import SingleLine

        return SingleLine

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___init___(self):
        single = self._makeOne(
            _Options(fields=None, item_delim='I', sequence_delim='S'))
        self.assertEqual(single._item_delim, 'I')
        self.assertEqual(single._sequence_delim, 'S')

    def test___call__wo_fields_wo_list(self):
        single = self._makeOne(
            _Options(fields=(), item_delim='|',
                     sequence_delim=object()))  # raise if used
        meta = _Meta(foo='Foo', bar='Bar')
        output = self._capture_output(single, meta)
        self.assertEqual(output, 'Bar|Foo\n')

    def test___call__w_fields_w_list(self):
        single = self._makeOne(
            _Options(fields=('foo', 'bar'), item_delim='|',
                     sequence_delim='*'))
        meta = _Meta(foo='Foo', bar=['Bar1', 'Bar2'], baz='Baz')
        output = self._capture_output(single, meta)
        self.assertEqual(output, 'Foo|Bar1*Bar2\n')

class CSVTests(unittest.TestCase, _FormatterBase):

    def _getTargetClass(self):
        from pkginfo.commandline import CSV

        return CSV

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___init___(self):
        csv = self._makeOne(
            _Options(fields=None, sequence_delim='S'))
        self.assertEqual(csv._sequence_delim, 'S')

    def test___call__wo_fields_wo_list(self):
        meta = _Meta(foo='Foo', bar='Bar')
        csv = self._makeOne(
            _Options(fields=None,
                     sequence_delim=object()))  # raise if used
        output = self._capture_output(csv, meta)
        self.assertEqual(output, 'bar,foo\r\nBar,Foo\r\n')

    def test___call__w_fields_w_list(self):
        meta = _Meta(foo='Foo', bar=['Bar1', 'Bar2'], baz='Baz')
        csv = self._makeOne(
            _Options(fields=('foo', 'bar'), item_delim='|',
                     sequence_delim='*'))
        output = self._capture_output(csv, meta)
        self.assertEqual(output, 'foo,bar\r\nFoo,Bar1*Bar2\r\n')

class INITests(unittest.TestCase, _FormatterBase):

    def _getTargetClass(self):
        from pkginfo.commandline import INI

        return INI

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___call___duplicate(self):
        ini = self._makeOne(_Options(fields=('foo',)))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        ini._parser.add_section('foo-0.1')
        self.assertRaises(ValueError, ini, meta)

    def test___call___wo_fields_wo_list(self):
        ini = self._makeOne(_Options(fields=None))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        ini(meta)
        cp = ini._parser
        self.assertEqual(cp.sections(), ['foo-0.1'])
        self.assertEqual(sorted(cp.options('foo-0.1')),
                         ['foo', 'name', 'version'])
        self.assertEqual(cp.get('foo-0.1', 'name'), 'foo')
        self.assertEqual(cp.get('foo-0.1', 'version'), '0.1')
        self.assertEqual(cp.get('foo-0.1', 'foo'), 'Foo')

    def test___call___w_fields_w_list(self):
        ini = self._makeOne(_Options(fields=('foo', 'bar')))
        meta = _Meta(name='foo', version='0.1',
                     foo='Foo', bar=['Bar1', 'Bar2'], baz='Baz')
        ini(meta)
        cp = ini._parser
        self.assertEqual(cp.sections(), ['foo-0.1'])
        self.assertEqual(sorted(cp.options('foo-0.1')), ['bar', 'foo'])
        self.assertEqual(cp.get('foo-0.1', 'foo'), 'Foo')
        self.assertEqual(cp.get('foo-0.1', 'bar'), 'Bar1\n\tBar2')

class JSONtests(unittest.TestCase, _FormatterBase):

    def _getTargetClass(self):
        from pkginfo.commandline import JSON

        return JSON

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test___call___duplicate_with_meta_and_fields(self):
        json = self._makeOne(_Options(fields=('name',)))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        json._mapping['name'] = 'foo'
        self.assertRaises(ValueError, json, meta)

    def test___call___duplicate_with_meta_wo_fields(self):
        json = self._makeOne(_Options(fields=None))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        json._mapping['name'] = 'foo'
        self.assertRaises(ValueError, json, meta)

    def test___call___wo_fields_wo_list(self):

        json = self._makeOne(_Options(fields=None))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        json(meta)
        expected = collections.OrderedDict([
            ('foo', 'Foo'), ('name', 'foo'), ('version', '0.1')])
        self.assertEqual(expected, json._mapping)

    def test___call___w_fields_w_list(self):
        json = self._makeOne(_Options(fields=('foo', 'bar')))
        meta = _Meta(name='foo', version='0.1',
                     foo='Foo', bar=['Bar1', 'Bar2'], baz='Baz')
        json(meta)
        expected = collections.OrderedDict([
            ('foo', 'Foo'), ('bar', ['Bar1', 'Bar2'])])
        self.assertEqual(expected, json._mapping)

    def test___call___output(self):
        json = self._makeOne(_Options(fields=None))
        meta = _Meta(name='foo', version='0.1', foo='Foo')
        json(meta)
        output = self._capture_output(json.finish)
        output = json_module.loads(
            output, object_pairs_hook=collections.OrderedDict)
        expected = collections.OrderedDict([
            ('foo', 'Foo'), ('name', 'foo'), ('version', '0.1')])
        self.assertEqual(expected, output)

class Test_main(unittest.TestCase):

    def _callFUT(self, args, monkey='simple'):
        from pkginfo.commandline import main
        from pkginfo.commandline import _FORMATTERS

        before = _FORMATTERS[monkey]
        dummy = _Formatter()
        _FORMATTERS[monkey] = lambda *options: dummy
        try:
            main(args)
        finally:
            _FORMATTERS[monkey] = before
        return dummy

    def test_w_mising_dist(self):
        from pkginfo import commandline as MUT

        def _get_metadata(path_or_module, md_version):
            self.assertEqual(path_or_module, 'foo')
            self.assertEqual(md_version, None)
            return None
        with _Monkey(MUT, get_metadata=_get_metadata):
            formatter = self._callFUT(['foo'])
        self.assertEqual(formatter._called_with, [])
        self.assertTrue(formatter._finished)

    def test_w_dist_wo_download_url(self):
        from pkginfo import commandline as MUT

        meta = _Meta(download_url=None)
        def _get_metadata(path_or_module, md_version):
            self.assertEqual(path_or_module, '/path/to/foo')
            self.assertEqual(md_version, None)
            return meta
        with _Monkey(MUT, get_metadata=_get_metadata):
            formatter = self._callFUT(
                ['-d', 'http://example.com', '/path/to/foo'])
        self.assertEqual(formatter._called_with, [meta])
        self.assertTrue(formatter._finished)
        self.assertEqual(meta.download_url, 'http://example.com/foo')

    def test_w_dist_w_download_url(self):
        from pkginfo import commandline as MUT

        meta = _Meta(download_url='http://example.com/dist/foo')
        def _get_metadata(path_or_module, md_version):
            self.assertEqual(path_or_module, '/path/to/foo')
            self.assertEqual(md_version, None)
            return meta
        with _Monkey(MUT, get_metadata=_get_metadata):
            formatter = self._callFUT(
                ['-d', 'http://example.com', '/path/to/foo'])
        self.assertEqual(formatter._called_with, [meta])
        self.assertTrue(formatter._finished)
        self.assertEqual(meta.download_url, 'http://example.com/dist/foo')

class _Options(object):

    def __init__(self, **kw):
        for k in kw:
            self.__dict__[k] = kw[k]

class _Meta(object):

    def __init__(self, **kw):
        for k in kw:
            self.__dict__[k] = kw[k]

    def __iter__(self):
        return iter(sorted(self.__dict__))

class _Monkey(object):
    # context-manager for replacing module names in the scope of a test.

    def __init__(self, module, **kw):
        self.module = module
        self.to_restore = dict([(key, getattr(module, key)) for key in kw])
        for key, value in kw.items():
            setattr(module, key, value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for key, value in self.to_restore.items():
            setattr(self.module, key, value)

class _Formatter(object):

    _finished = False

    def __init__(self):
        self._called_with = []

    def __call__(self, meta):
        self._called_with.append(meta)

    def finish(self):
        self._finished = True
