"""Extensions to the 'distutils' for large or complex distributions"""

import functools
import os
import re
import warnings

import _distutils_hack.override  # noqa: F401

import distutils.core
from distutils.errors import DistutilsOptionError
from distutils.util import convert_path as _convert_path

from ._deprecation_warning import SetuptoolsDeprecationWarning

import setuptools.version
from setuptools.extension import Extension
from setuptools.dist import Distribution
from setuptools.depends import Require
from setuptools.discovery import PackageFinder, PEP420PackageFinder
from . import monkey
from . import logging


__all__ = [
    'setup',
    'Distribution',
    'Command',
    'Extension',
    'Require',
    'SetuptoolsDeprecationWarning',
    'find_packages',
    'find_namespace_packages',
]

__version__ = setuptools.version.__version__

bootstrap_install_from = None


find_packages = PackageFinder.find
find_namespace_packages = PEP420PackageFinder.find


def _install_setup_requires(attrs):
    # Note: do not use `setuptools.Distribution` directly, as
    # our PEP 517 backend patch `distutils.core.Distribution`.
    class MinimalDistribution(distutils.core.Distribution):
        """
        A minimal version of a distribution for supporting the
        fetch_build_eggs interface.
        """

        def __init__(self, attrs):
            _incl = 'dependency_links', 'setup_requires'
            filtered = {k: attrs[k] for k in set(_incl) & set(attrs)}
            super().__init__(filtered)
            # Prevent accidentally triggering discovery with incomplete set of attrs
            self.set_defaults._disable()

        def _get_project_config_files(self, filenames=None):
            """Ignore ``pyproject.toml``, they are not related to setup_requires"""
            try:
                cfg, toml = super()._split_standard_project_metadata(filenames)
                return cfg, ()
            except Exception:
                return filenames, ()

        def finalize_options(self):
            """
            Disable finalize_options to avoid building the working set.
            Ref #2158.
            """

    dist = MinimalDistribution(attrs)

    # Honor setup.cfg's options.
    dist.parse_config_files(ignore_option_errors=True)
    if dist.setup_requires:
        dist.fetch_build_eggs(dist.setup_requires)


def setup(**attrs):
    # Make sure we have any requirements needed to interpret 'attrs'.
    logging.configure()
    _install_setup_requires(attrs)
    return distutils.core.setup(**attrs)


setup.__doc__ = distutils.core.setup.__doc__


_Command = monkey.get_unpatched(distutils.core.Command)


class Command(_Command):
    __doc__ = _Command.__doc__

    command_consumes_arguments = False

    def __init__(self, dist, **kw):
        """
        Construct the command for dist, updating
        vars(self) with any keyword parameters.
        """
        super().__init__(dist)
        vars(self).update(kw)

    def _ensure_stringlike(self, option, what, default=None):
        val = getattr(self, option)
        if val is None:
            setattr(self, option, default)
            return default
        elif not isinstance(val, str):
            raise DistutilsOptionError(
                "'%s' must be a %s (got `%s`)" % (option, what, val)
            )
        return val

    def ensure_string_list(self, option):
        r"""Ensure that 'option' is a list of strings.  If 'option' is
        currently a string, we split it either on /,\s*/ or /\s+/, so
        "foo bar baz", "foo,bar,baz", and "foo,   bar baz" all become
        ["foo", "bar", "baz"].
        """
        val = getattr(self, option)
        if val is None:
            return
        elif isinstance(val, str):
            setattr(self, option, re.split(r',\s*|\s+', val))
        else:
            if isinstance(val, list):
                ok = all(isinstance(v, str) for v in val)
            else:
                ok = False
            if not ok:
                raise DistutilsOptionError(
                    "'%s' must be a list of strings (got %r)" % (option, val)
                )

    def reinitialize_command(self, command, reinit_subcommands=0, **kw):
        cmd = _Command.reinitialize_command(self, command, reinit_subcommands)
        vars(cmd).update(kw)
        return cmd


def _find_all_simple(path):
    """
    Find all files under 'path'
    """
    results = (
        os.path.join(base, file)
        for base, dirs, files in os.walk(path, followlinks=True)
        for file in files
    )
    return filter(os.path.isfile, results)


def findall(dir=os.curdir):
    """
    Find all files under 'dir' and return the list of full filenames.
    Unless dir is '.', return full filenames with dir prepended.
    """
    files = _find_all_simple(dir)
    if dir == os.curdir:
        make_rel = functools.partial(os.path.relpath, start=dir)
        files = map(make_rel, files)
    return list(files)


@functools.wraps(_convert_path)
def convert_path(pathname):
    from inspect import cleandoc

    msg = """
    The function `convert_path` is considered internal and not part of the public API.
    Its direct usage by 3rd-party packages is considered deprecated and the function
    may be removed in the future.
    """
    warnings.warn(cleandoc(msg), SetuptoolsDeprecationWarning)
    return _convert_path(pathname)


class sic(str):
    """Treat this string as-is (https://en.wikipedia.org/wiki/Sic)"""


# Apply monkey patches
monkey.patch_all()
