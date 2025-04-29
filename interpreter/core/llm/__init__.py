from importlib import metadata

_VERSION = "dev"


def __get_version():
    try:
        version = metadata.version("open-interpreter")
    except metadata.PackageNotFoundError:
        version = _VERSION
    return version


__version__ = __get_version()