"""
Create a dist_info directory
As defined in the wheel specification
"""

import os
import re
import warnings
from inspect import cleandoc

from distutils.core import Command
from distutils import log
from setuptools.extern import packaging


class dist_info(Command):

    description = 'create a .dist-info directory'

    user_options = [
        ('egg-base=', 'e', "directory containing .egg-info directories"
                           " (default: top of the source tree)"),
    ]

    def initialize_options(self):
        self.egg_base = None

    def finalize_options(self):
        pass

    def run(self):
        egg_info = self.get_finalized_command('egg_info')
        egg_info.egg_base = self.egg_base
        egg_info.finalize_options()
        egg_info.run()
        name = _safe(self.distribution.get_name())
        version = _version(self.distribution.get_version())
        base = self.egg_base or os.curdir
        dist_info_dir = os.path.join(base, f"{name}-{version}.dist-info")
        log.info("creating '{}'".format(os.path.abspath(dist_info_dir)))

        bdist_wheel = self.get_finalized_command('bdist_wheel')
        bdist_wheel.egg2dist(egg_info.egg_info, dist_info_dir)


def _safe(component: str) -> str:
    """Escape a component used to form a wheel name according to PEP 491"""
    return re.sub(r"[^\w\d.]+", "_", component)


def _version(version: str) -> str:
    """Convert an arbitrary string to a version string."""
    v = version.replace(' ', '.')
    try:
        return str(packaging.version.Version(v)).replace("-", "_")
    except packaging.version.InvalidVersion:
        msg = f"""Invalid version: {version!r}.
        !!\n\n
        ###################
        # Invalid version #
        ###################
        {version!r} is not valid according to PEP 440.\n
        Please make sure specify a valid version for your package.
        Also note that future releases of setuptools may halt the build process
        if an invalid version is given.
        \n\n!!
        """
        warnings.warn(cleandoc(msg))
        return _safe(v).strip("_")
