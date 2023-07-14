from __future__ import annotations

from poetry.core.version.pep440.segments import LocalSegmentType
from poetry.core.version.pep440.segments import Release
from poetry.core.version.pep440.segments import ReleaseTag
from poetry.core.version.pep440.version import PEP440Version


__all__ = ("LocalSegmentType", "Release", "ReleaseTag", "PEP440Version")
