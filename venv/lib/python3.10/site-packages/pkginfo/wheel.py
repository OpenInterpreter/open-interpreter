import io
import os
import zipfile


from .distribution import Distribution
from .distribution import parse


class Wheel(Distribution):

    def __init__(self, filename, metadata_version=None):
        self.filename = filename
        self.metadata_version = metadata_version
        self.extractMetadata()

    def read(self):
        fqn = os.path.abspath(os.path.normpath(self.filename))
        if not os.path.exists(fqn):
            raise ValueError('No such file: %s' % fqn)

        if fqn.endswith('.whl'):
            archive = zipfile.ZipFile(fqn)
            names = archive.namelist()

            def read_file(name):
                return archive.read(name)

            close = archive.close

        elif fqn.endswith('.dist-info'):
            names = [os.path.join(fqn, p) for p in os.listdir(fqn)]

            def read_file(name):
                with io.open(name, mode='rb') as inf:
                    return inf.read()

            close = lambda : None

        else:
            raise ValueError('Not a known wheel archive format or '
                             'installed .dist-info: %s' % fqn)

        try:
            tuples = [x.split('/') for x in names if 'METADATA' in x]
            schwarz = sorted([(len(x), x) for x in tuples])
            for path in [x[1] for x in schwarz]:
                candidate = '/'.join(path)
                data = read_file(candidate)
                if b'Metadata-Version' in data:
                    return data
        finally:
            close()

        raise ValueError('No METADATA in archive: %s' % fqn)
