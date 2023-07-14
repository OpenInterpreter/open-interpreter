import unittest

class Test__must_decode(unittest.TestCase):

    def _callFUT(self, arg):
        from pkginfo.distribution import _must_decode
        return _must_decode(arg)

    def test_w_bytes_latin1(self):
        TO_ENCODE = u'\u00C9'  # capital E w/ acute accent
        encoded = TO_ENCODE.encode("latin-1")
        decoded = self._callFUT(encoded)
        self.assertEqual(decoded, TO_ENCODE)

    def test_w_bytes_utf8(self):
        TO_ENCODE = u'\u00C9'  # capital E w/ acute accent
        encoded = TO_ENCODE.encode("utf-8")
        decoded = self._callFUT(encoded)
        self.assertEqual(decoded, TO_ENCODE)

    def test_w_unicode(self):
        ARG = u'\u00C9'  # capital E w/ acute accent
        decoded = self._callFUT(ARG)
        self.assertEqual(decoded, ARG)

    def test_w_object(self):
        ARG = object()
        decoded = self._callFUT(ARG)
        self.assertIs(decoded, ARG)

class DistributionTests(unittest.TestCase):

    def _getTargetClass(self):
        from pkginfo.distribution import Distribution
        return Distribution

    def _makeOne(self, metadata_version='1.0'):
        dist = self._getTargetClass()()
        if metadata_version is not None:
            dist.metadata_version = metadata_version
        return dist

    def test_ctor_defaults(self):
        sdist = self._makeOne(None)
        self.assertEqual(sdist.metadata_version, None)
        # version 1.0
        self.assertEqual(sdist.name, None)
        self.assertEqual(sdist.version, None)
        self.assertEqual(sdist.platforms, ())
        self.assertEqual(sdist.supported_platforms, ())
        self.assertEqual(sdist.summary, None)
        self.assertEqual(sdist.description, None)
        self.assertEqual(sdist.keywords, None)
        self.assertEqual(sdist.home_page, None)
        self.assertEqual(sdist.download_url, None)
        self.assertEqual(sdist.author, None)
        self.assertEqual(sdist.author_email, None)
        self.assertEqual(sdist.license, None)
        # version 1.1
        self.assertEqual(sdist.classifiers, ())
        self.assertEqual(sdist.requires, ())
        self.assertEqual(sdist.provides, ())
        self.assertEqual(sdist.obsoletes, ())
        # version 1.2
        self.assertEqual(sdist.maintainer, None)
        self.assertEqual(sdist.maintainer_email, None)
        self.assertEqual(sdist.requires_python, None)
        self.assertEqual(sdist.requires_external, ())
        self.assertEqual(sdist.requires_dist, ())
        self.assertEqual(sdist.provides_dist, ())
        self.assertEqual(sdist.obsoletes_dist, ())
        self.assertEqual(sdist.project_urls, ())
        # version 2.1
        self.assertEqual(sdist.provides_extras, ())
        self.assertEqual(sdist.description_content_type, None)
        # version 2.2
        self.assertEqual(sdist.dynamic, ())

    def test_extractMetadata_raises_NotImplementedError(self):
        # 'extractMetadata' calls 'read', which subclasses must override.
        dist = self._makeOne(None)
        self.assertRaises(NotImplementedError, dist.extractMetadata)

    def test_read_raises_NotImplementedError(self):
        # Subclasses must override 'read'.
        dist = self._makeOne(None)
        self.assertRaises(NotImplementedError, dist.read)

    def test_parse_given_unicode(self):
        dist = self._makeOne()
        dist.parse(u'Metadata-Version: 1.0\nName: lp722928_c3') # no raise

    def test_parse_Metadata_Version_1_0(self):
        from pkginfo.distribution import HEADER_ATTRS_1_0
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 1.0')
        self.assertEqual(dist.metadata_version, '1.0')
        self.assertEqual(list(dist),
                         [x[1] for x in HEADER_ATTRS_1_0])

    def test_parse_Metadata_Version_1_1(self):
        from pkginfo.distribution import HEADER_ATTRS_1_1
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 1.1')
        self.assertEqual(dist.metadata_version, '1.1')
        self.assertEqual(list(dist),
                         [x[1] for x in HEADER_ATTRS_1_1])

    def test_parse_Metadata_Version_1_2(self):
        from pkginfo.distribution import HEADER_ATTRS_1_2
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 1.2')
        self.assertEqual(dist.metadata_version, '1.2')
        self.assertEqual(list(dist),
                         [x[1] for x in HEADER_ATTRS_1_2])

    def test_parse_Metadata_Version_2_1(self):
        from pkginfo.distribution import HEADER_ATTRS_2_1
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 2.1')
        self.assertEqual(dist.metadata_version, '2.1')
        self.assertEqual(list(dist),
                         [x[1] for x in HEADER_ATTRS_2_1])

    def test_parse_Metadata_Version_2_2(self):
        from pkginfo.distribution import HEADER_ATTRS_2_2
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 2.2')
        self.assertEqual(dist.metadata_version, '2.2')
        self.assertEqual(list(dist),
                         [x[1] for x in HEADER_ATTRS_2_2])

    def test_parse_Metadata_Version_unknown(self):
        dist = self._makeOne(None)
        dist.parse('Metadata-Version: 1.3')
        self.assertEqual(dist.metadata_version, '1.3')
        self.assertEqual(list(dist), [])

    def test_parse_Metadata_Version_override(self):
        dist = self._makeOne('1.2')
        dist.parse('Metadata-Version: 1.0')
        self.assertEqual(dist.metadata_version, '1.2')

    def test_parse_Name(self):
        dist = self._makeOne()
        dist.parse('Name: foobar')
        self.assertEqual(dist.name, 'foobar')

    def test_parse_Version(self):
        dist = self._makeOne()
        dist.parse('Version: 2.1.3b5')
        self.assertEqual(dist.version, '2.1.3b5')

    def test_parse_Platform_single(self):
        dist = self._makeOne()
        dist.parse('Platform: Plan9')
        self.assertEqual(list(dist.platforms), ['Plan9'])

    def test_parse_Platform_multiple(self):
        dist = self._makeOne()
        dist.parse('Platform: Plan9\nPlatform: AIX')
        self.assertEqual(list(dist.platforms), ['Plan9', 'AIX'])

    def test_parse_Supported_Platform_single(self):
        dist = self._makeOne()
        dist.parse('Supported-Platform: Plan9')
        self.assertEqual(list(dist.supported_platforms), ['Plan9'])

    def test_parse_Supported_Platform_multiple(self):
        dist = self._makeOne()
        dist.parse('Supported-Platform: i386-win32\n'
                   'Supported-Platform: RedHat 7.2')
        self.assertEqual(list(dist.supported_platforms),
                        ['i386-win32', 'RedHat 7.2'])

    def test_parse_Summary(self):
        dist = self._makeOne()
        dist.parse('Summary: Package for foo')
        self.assertEqual(dist.summary, 'Package for foo')

    def test_parse_Description(self):
        dist = self._makeOne()
        dist.parse('Description: This package enables integration with '
                   'foo servers.')
        self.assertEqual(dist.description,
                         'This package enables integration with '
                         'foo servers.')

    def test_parse_Description_multiline(self):
        dist = self._makeOne()
        dist.parse('Description: This package enables integration with\n'
                   '        foo servers.')
        self.assertEqual(dist.description,
                         'This package enables integration with\n'
                         'foo servers.')

    def test_parse_Description_in_payload(self):
        dist = self._makeOne()
        dist.parse('Foo: Bar\n'
                   '\n'
                   'This package enables integration with\n'
                   'foo servers.')
        self.assertEqual(dist.description,
                         'This package enables integration with\n'
                         'foo servers.')

    def test_parse_Keywords(self):
        dist = self._makeOne()
        dist.parse('Keywords: bar foo qux')
        self.assertEqual(dist.keywords, 'bar foo qux')

    def test_parse_Home_page(self):
        dist = self._makeOne()
        dist.parse('Home-page: http://example.com/package')
        self.assertEqual(dist.home_page, 'http://example.com/package')

    def test_parse_Author(self):
        dist = self._makeOne()
        dist.parse('Author: J. Phredd Bloggs')
        self.assertEqual(dist.author, 'J. Phredd Bloggs')

    def test_parse_Author_Email(self):
        dist = self._makeOne()
        dist.parse('Author-email: phreddy@example.com')
        self.assertEqual(dist.author_email, 'phreddy@example.com')

    def test_parse_License(self):
        dist = self._makeOne()
        dist.parse('License: Poetic')
        self.assertEqual(dist.license, 'Poetic')

    # Metadata version 1.1, defined in PEP 314.
    def test_parse_Classifier_single(self):
        dist = self._makeOne('1.1')
        dist.parse('Classifier: Some :: Silly Thing')
        self.assertEqual(list(dist.classifiers), ['Some :: Silly Thing'])

    def test_parse_Classifier_multiple(self):
        dist = self._makeOne('1.1')
        dist.parse('Classifier: Some :: Silly Thing\n'
                   'Classifier: Or :: Other')
        self.assertEqual(list(dist.classifiers),
                         ['Some :: Silly Thing', 'Or :: Other'])

    def test_parse_Download_URL(self):
        dist = self._makeOne('1.1')
        dist.parse('Download-URL: '
                   'http://example.com/package/mypackage-0.1.zip')
        self.assertEqual(dist.download_url,
                         'http://example.com/package/mypackage-0.1.zip')

    def test_parse_Requires_single_wo_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Requires: SpanishInquisition')
        self.assertEqual(list(dist.requires), ['SpanishInquisition'])

    def test_parse_Requires_single_w_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Requires: SpanishInquisition (>=1.3)')
        self.assertEqual(list(dist.requires), ['SpanishInquisition (>=1.3)'])

    def test_parse_Requires_multiple(self):
        dist = self._makeOne('1.1')
        dist.parse('Requires: SpanishInquisition\n'
                   'Requires: SillyWalks (1.4)\n'
                   'Requires: kniggits (>=2.3,<3.0)')
        self.assertEqual(list(dist.requires),
                         ['SpanishInquisition',
                          'SillyWalks (1.4)',
                          'kniggits (>=2.3,<3.0)',
                         ])

    def test_parse_Provides_single_wo_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Provides: SillyWalks')
        self.assertEqual(list(dist.provides), ['SillyWalks'])

    def test_parse_Provides_single_w_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Provides: SillyWalks (1.4)')
        self.assertEqual(list(dist.provides), ['SillyWalks (1.4)'])

    def test_parse_Provides_multiple(self):
        dist = self._makeOne('1.1')
        dist.parse('Provides: SillyWalks\n'
                   'Provides: DeadlyJoke (3.1.4)')
        self.assertEqual(list(dist.provides),
                         ['SillyWalks',
                          'DeadlyJoke (3.1.4)',
                         ])

    def test_parse_Obsoletes_single_no_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Obsoletes: SillyWalks')
        self.assertEqual(list(dist.obsoletes), ['SillyWalks'])

    def test_parse_Obsoletes_single_w_version(self):
        dist = self._makeOne('1.1')
        dist.parse('Obsoletes: SillyWalks (<=1.3)')
        self.assertEqual(list(dist.obsoletes), ['SillyWalks (<=1.3)'])

    def test_parse_Obsoletes_multiple(self):
        dist = self._makeOne('1.1')
        dist.parse('Obsoletes: kniggits\n'
                   'Obsoletes: SillyWalks (<=2.0)')
        self.assertEqual(list(dist.obsoletes),
                         ['kniggits',
                          'SillyWalks (<=2.0)',
                         ])


    # Metadata version 1.2, defined in PEP 345.
    def test_parse_Maintainer(self):
        dist = self._makeOne(metadata_version='1.2')
        dist.parse('Maintainer: J. Phredd Bloggs')
        self.assertEqual(dist.maintainer, 'J. Phredd Bloggs')

    def test_parse_Maintainer_Email(self):
        dist = self._makeOne(metadata_version='1.2')
        dist.parse('Maintainer-email: phreddy@example.com')
        self.assertEqual(dist.maintainer_email, 'phreddy@example.com')

    def test_parse_Requires_Python_single_spec(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-Python: >2.4')
        self.assertEqual(dist.requires_python, '>2.4')

    def test_parse_Requires_External_single_wo_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-External: libfoo')
        self.assertEqual(list(dist.requires_external), ['libfoo'])

    def test_parse_Requires_External_single_w_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-External: libfoo (>=1.3)')
        self.assertEqual(list(dist.requires_external), ['libfoo (>=1.3)'])

    def test_parse_Requires_External_multiple(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-External: libfoo\n'
                   'Requires-External: libbar (1.4)\n'
                   'Requires-External: libbaz (>=2.3,<3.0)')
        self.assertEqual(list(dist.requires_external),
                         ['libfoo',
                          'libbar (1.4)',
                          'libbaz (>=2.3,<3.0)',
                         ])


    def test_parse_Requires_Dist_single_wo_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-Dist: SpanishInquisition')
        self.assertEqual(list(dist.requires_dist), ['SpanishInquisition'])

    def test_parse_Requires_Dist_single_w_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Requires-Dist: SpanishInquisition (>=1.3)')
        self.assertEqual(list(dist.requires_dist),
                         ['SpanishInquisition (>=1.3)'])

    def test_parse_Requires_Dist_single_w_env_marker(self):
        dist = self._makeOne('1.2')
        dist.parse("Requires-Dist: SpanishInquisition; "
                        "python_version == '1.4'")
        self.assertEqual(list(dist.requires_dist),
                         ["SpanishInquisition; python_version == '1.4'"])

    def test_parse_Requires_Dist_multiple(self):
        dist = self._makeOne('1.2')
        dist.parse("Requires-Dist: SpanishInquisition\n"
                   "Requires-Dist: SillyWalks; python_version == '1.4'\n"
                   "Requires-Dist: kniggits (>=2.3,<3.0)")
        self.assertEqual(list(dist.requires_dist),
                         ["SpanishInquisition",
                          "SillyWalks; python_version == '1.4'",
                          "kniggits (>=2.3,<3.0)",
                         ])

    def test_parse_Provides_Dist_single_wo_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Provides-Dist: SillyWalks')
        self.assertEqual(list(dist.provides_dist), ['SillyWalks'])

    def test_parse_Provides_Dist_single_w_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Provides-Dist: SillyWalks (1.4)')
        self.assertEqual(list(dist.provides_dist), ['SillyWalks (1.4)'])

    def test_parse_Provides_Dist_single_w_env_marker(self):
        dist = self._makeOne('1.2')
        dist.parse("Provides-Dist: SillyWalks; sys.platform == 'os2'")
        self.assertEqual(list(dist.provides_dist),
                         ["SillyWalks; sys.platform == 'os2'"])

    def test_parse_Provides_Dist_multiple(self):
        dist = self._makeOne('1.2')
        dist.parse("Provides-Dist: SillyWalks\n"
                   "Provides-Dist: SpanishInquisition; sys.platform == 'os2'\n"
                   "Provides-Dist: DeadlyJoke (3.1.4)")
        self.assertEqual(list(dist.provides_dist),
                         ["SillyWalks",
                          "SpanishInquisition; sys.platform == 'os2'",
                          "DeadlyJoke (3.1.4)",
                         ])

    def test_parse_Obsoletes_Dist_single_no_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Obsoletes-Dist: SillyWalks')
        self.assertEqual(list(dist.obsoletes_dist), ['SillyWalks'])

    def test_parse_Obsoletes_Dist_single_w_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Obsoletes-Dist: SillyWalks (<=1.3)')
        self.assertEqual(list(dist.obsoletes_dist), ['SillyWalks (<=1.3)'])

    def test_parse_Obsoletes_Dist_single_w_env_marker(self):
        dist = self._makeOne('1.2')
        dist.parse("Obsoletes-Dist: SillyWalks; sys.platform == 'os2'")
        self.assertEqual(list(dist.obsoletes_dist),
                         ["SillyWalks; sys.platform == 'os2'"])

    def test_parse_Obsoletes_Dist_multiple(self):
        dist = self._makeOne('1.2')
        dist.parse("Obsoletes-Dist: kniggits\n"
                   "Obsoletes-Dist: SillyWalks; sys.platform == 'os2'\n"
                   "Obsoletes-Dist: DeadlyJoke (<=2.0)\n"
                  )
        self.assertEqual(list(dist.obsoletes_dist),
                         ["kniggits",
                          "SillyWalks; sys.platform == 'os2'",
                          "DeadlyJoke (<=2.0)",
                         ])

    def test_parse_Project_URL_single_no_version(self):
        dist = self._makeOne('1.2')
        dist.parse('Project-URL: Bug tracker, http://bugs.example.com/grail')
        self.assertEqual(list(dist.project_urls),
                         ['Bug tracker, http://bugs.example.com/grail'])

    def test_parse_Project_URL_multiple(self):
        dist = self._makeOne('1.2')
        dist.parse('Project-URL: Bug tracker, http://bugs.example.com/grail\n'
                   'Project-URL: Repository, http://svn.example.com/grail')
        self.assertEqual(list(dist.project_urls),
                         ['Bug tracker, http://bugs.example.com/grail',
                          'Repository, http://svn.example.com/grail',
                         ])

    # Metadata version 2.1, defined in PEP 566.
    def test_parse_Provides_Extra_single(self):
        dist = self._makeOne('2.1')
        dist.parse('Provides-Extra: pdf')
        self.assertEqual(list(dist.provides_extras), ['pdf'])

    def test_parse_Provides_Extra_multiple(self):
        dist = self._makeOne('2.1')
        dist.parse('Provides-Extra: pdf\n'
                   'Provides-Extra: tex')
        self.assertEqual(list(dist.provides_extras), ['pdf', 'tex'])

    def test_parse_Distribution_Content_Type_single(self):
        dist = self._makeOne('2.1')
        dist.parse('Description-Content-Type: text/plain')
        self.assertEqual(dist.description_content_type, 'text/plain')

    # Metadata version 2.2, defined in PEP 643.
    def test_parse_Dynamic_single(self):
        dist = self._makeOne('2.2')
        dist.parse('Dynamic: Platforms')
        self.assertEqual(list(dist.dynamic), ['Platforms'])

    def test_parse_Dynamic_multiple(self):
        dist = self._makeOne('2.2')
        dist.parse('Dynamic: Platforms\n'
                   'Dynamic: Supported-Platforms')
        self.assertEqual(list(dist.dynamic),
                         ['Platforms', 'Supported-Platforms'])
