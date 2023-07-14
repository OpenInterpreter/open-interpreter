from __future__ import annotations

import sys

from pathlib import Path


# this cannot presently be replaced with importlib.metadata.version as when building
# itself, poetry-core is not available as an installed distribution.
__version__ = "1.6.1"

__vendor_site__ = (Path(__file__).parent / "_vendor").as_posix()

if __vendor_site__ not in sys.path:
    sys.path.insert(0, __vendor_site__)
