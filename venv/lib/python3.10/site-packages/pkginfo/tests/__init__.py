# requirements


def _checkSample(testcase, installed):
    try:
        import pkg_resources
    except ImportError: # pragma: NO COVER
        # no setuptools :(
        pass
    else:
        version = pkg_resources.require('pkginfo')[0].version
        testcase.assertEqual(installed.version, version)
    testcase.assertEqual(installed.name, 'pkginfo')
    testcase.assertEqual(installed.keywords,
                        'distribution sdist installed metadata' )
    testcase.assertEqual(list(installed.supported_platforms), [])

def _checkClassifiers(testcase, installed):
    testcase.assertEqual(list(installed.classifiers),
                         [
      'Intended Audience :: Developers',
      'License :: OSI Approved :: MIT License',
      'Operating System :: OS Independent',
      'Programming Language :: Python :: 3.6',
      'Programming Language :: Python :: 3.7',
      'Programming Language :: Python :: 3.8',
      'Programming Language :: Python :: 3.9',
      'Programming Language :: Python :: 3.10',
      'Programming Language :: Python :: Implementation :: CPython',
      'Programming Language :: Python :: Implementation :: PyPy',
      'Topic :: Software Development :: Libraries :: Python Modules',
      'Topic :: System :: Software Distribution',
    ])


def _defaultMetadataVersion():
    return '2.1'
