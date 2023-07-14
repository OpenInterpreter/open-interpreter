from __future__ import annotations

import re

from packaging.version import VERSION_PATTERN


COMPLETE_VERSION = re.compile(VERSION_PATTERN, re.VERBOSE | re.IGNORECASE)

CARET_CONSTRAINT = re.compile(
    rf"^\^(?P<version>{VERSION_PATTERN})$", re.VERBOSE | re.IGNORECASE
)
TILDE_CONSTRAINT = re.compile(
    rf"^~(?!=)\s*(?P<version>{VERSION_PATTERN})$", re.VERBOSE | re.IGNORECASE
)
TILDE_PEP440_CONSTRAINT = re.compile(
    rf"^~=\s*(?P<version>{VERSION_PATTERN})$", re.VERBOSE | re.IGNORECASE
)
X_CONSTRAINT = re.compile(
    r"^(?P<op>!=|==)?\s*v?(?P<version>(\d+)(?:\.(\d+))?(?:\.(\d+))?)(?:\.[xX*])+$"
)

# note that we also allow technically incorrect version patterns with astrix (eg: 3.5.*)
# as this is supported by pip and appears in metadata within python packages
BASIC_CONSTRAINT = re.compile(
    rf"^(?P<op><>|!=|>=?|<=?|==?)?\s*(?P<version>{VERSION_PATTERN}|dev)(?P<wildcard>\.\*)?$",
    re.VERBOSE | re.IGNORECASE,
)
