"""AutoImport module for rope."""
from .pickle import AutoImport as _PickleAutoImport
from .sqlite import AutoImport as _SqliteAutoImport

AutoImport = _PickleAutoImport

__all__ = ["AutoImport"]
