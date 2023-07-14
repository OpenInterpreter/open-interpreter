import glob
import io
import os
import sys
import warnings

from .distribution import Distribution

class Installed(Distribution):

    def __init__(self, package, metadata_version=None):
        if isinstance(package, str):
            self.package_name = package
            try:
                __import__(package)
            except ImportError:
                package = None
            else:
                package = sys.modules[package]
        else:
            self.package_name = package.__name__
        self.package = package
        self.metadata_version = metadata_version
        self.extractMetadata()

    def read(self):
        opj = os.path.join
        if self.package is not None:
            package = self.package.__package__
            if package in ('', None):
                package = self.package.__name__
            egg_pattern = '%s*.egg-info' % package
            dist_pattern = '%s*.dist-info' % package
            pkg_file = getattr(self.package, '__file__', None)
            if pkg_file is not None:
                candidates = []
                def _add_candidate(where):
                    candidates.extend(glob.glob(where))
                for entry in sys.path:
                    if pkg_file.startswith(entry):
                        _add_candidate(opj(entry, 'EGG-INFO')) # egg?
                        _add_candidate(opj(entry, egg_pattern))
                        _add_candidate(opj(entry, dist_pattern))
                dir, name = os.path.split(self.package.__file__)
                _add_candidate(opj(dir, egg_pattern))
                _add_candidate(opj(dir, '..', egg_pattern))
                _add_candidate(opj(dir, dist_pattern))
                _add_candidate(opj(dir, '..', dist_pattern))
                for candidate in candidates:
                    if os.path.isdir(candidate):
                        if candidate.lower().endswith("egg-info"):
                            path = opj(candidate, 'PKG-INFO')
                        elif candidate.endswith("dist-info"):
                            path = opj(candidate, 'METADATA')
                        else:  # pragma: NO COVER
                            continue
                    else:
                        path = candidate
                    if os.path.exists(path):
                        with io.open(path, errors='ignore') as f:
                            return f.read()
        warnings.warn('No PKG-INFO found for package: %s' % self.package_name)
