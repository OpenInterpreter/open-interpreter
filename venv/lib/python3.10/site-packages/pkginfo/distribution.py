import io
from email.parser import Parser

def _must_decode(value):
    if type(value) is bytes:
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('latin1')
    return value

must_decode = _must_decode # deprecated compatibility alias FBO twine.


def parse(fp):
    return Parser().parse(fp)
def get(msg, header):
    return _collapse_leading_ws(header, msg.get(header))
def get_all(msg, header):
    return [_collapse_leading_ws(header, x) for x in msg.get_all(header)]

def _collapse_leading_ws(header, txt):
    """
    ``Description`` header must preserve newlines; all others need not
    """
    if header.lower() == 'description':  # preserve newlines
        return '\n'.join([x[8:] if x.startswith(' ' * 8) else x
                          for x in txt.strip().splitlines()])
    else:
        return ' '.join([x.strip() for x in txt.splitlines()])


HEADER_ATTRS_1_0 = ( # PEP 241
    ('Metadata-Version', 'metadata_version', False),
    ('Name', 'name', False),
    ('Version', 'version', False),
    ('Platform', 'platforms', True),
    ('Supported-Platform', 'supported_platforms', True),
    ('Summary', 'summary', False),
    ('Description', 'description', False),
    ('Keywords', 'keywords', False),
    ('Home-Page', 'home_page', False),
    ('Author', 'author', False),
    ('Author-email', 'author_email', False),
    ('License', 'license', False),
)

HEADER_ATTRS_1_1 = HEADER_ATTRS_1_0 + ( # PEP 314
    ('Classifier', 'classifiers', True),
    ('Download-URL', 'download_url', False),
    ('Requires', 'requires', True),
    ('Provides', 'provides', True),
    ('Obsoletes', 'obsoletes', True),
)

HEADER_ATTRS_1_2 = HEADER_ATTRS_1_1 + ( # PEP 345
    ('Maintainer', 'maintainer', False),
    ('Maintainer-email', 'maintainer_email', False),
    ('Requires-Python', 'requires_python', False),
    ('Requires-External', 'requires_external', True),
    ('Requires-Dist', 'requires_dist', True),
    ('Provides-Dist', 'provides_dist', True),
    ('Obsoletes-Dist', 'obsoletes_dist', True),
    ('Project-URL', 'project_urls', True),
)

HEADER_ATTRS_2_0 = HEADER_ATTRS_1_2  #XXX PEP 426?

HEADER_ATTRS_2_1 = HEADER_ATTRS_1_2 + ( # PEP 566
    ('Provides-Extra', 'provides_extras', True),
    ('Description-Content-Type', 'description_content_type', False)
)

HEADER_ATTRS_2_2 = HEADER_ATTRS_2_1 + ( # PEP 643
    ('Dynamic', 'dynamic', True),
)

HEADER_ATTRS = {
    '1.0': HEADER_ATTRS_1_0,
    '1.1': HEADER_ATTRS_1_1,
    '1.2': HEADER_ATTRS_1_2,
    '2.0': HEADER_ATTRS_2_0,
    '2.1': HEADER_ATTRS_2_1,
    '2.2': HEADER_ATTRS_2_2,
}

class Distribution(object):
    metadata_version = None
    # version 1.0
    name = None
    version = None
    platforms = ()
    supported_platforms = ()
    summary = None
    description = None
    keywords = None
    home_page = None
    download_url = None
    author = None
    author_email = None
    license = None
    # version 1.1
    classifiers = ()
    requires = ()
    provides = ()
    obsoletes = ()
    # version 1.2
    maintainer = None
    maintainer_email = None
    requires_python = None
    requires_external = ()
    requires_dist = ()
    provides_dist = ()
    obsoletes_dist = ()
    project_urls = ()
    # version 2.1
    provides_extras = ()
    description_content_type = None
    # version 2.2
    dynamic = ()

    def extractMetadata(self):
        data = self.read()
        self.parse(data)

    def read(self):
        raise NotImplementedError

    def _getHeaderAttrs(self):
        return HEADER_ATTRS.get(self.metadata_version, [])

    def parse(self, data):
        fp = io.StringIO(_must_decode(data))
        msg = parse(fp)

        if 'Metadata-Version' in msg and self.metadata_version is None:
            value = get(msg, 'Metadata-Version')
            metadata_version = self.metadata_version = value

        for header_name, attr_name, multiple in self._getHeaderAttrs():

            if attr_name == 'metadata_version':
                continue

            if header_name in msg:
                if multiple:
                    values = get_all(msg, header_name)
                    setattr(self, attr_name, values)
                else:
                    value = get(msg, header_name)
                    if value != 'UNKNOWN':
                        setattr(self, attr_name, value)

        body = msg.get_payload()
        if body:
            setattr(self, 'description', body)

    def __iter__(self):
        for header_name, attr_name, multiple in self._getHeaderAttrs():
            yield attr_name

    iterkeys = __iter__
