from __future__ import annotations

import re
import warnings

from typing import TYPE_CHECKING
from typing import NewType
from typing import cast


if TYPE_CHECKING:
    from packaging.utils import NormalizedName


DistributionName = NewType("DistributionName", str)


def normalize_file_permissions(st_mode: int) -> int:
    """
    Normalizes the permission bits in the st_mode field from stat to 644/755

    Popular VCSs only track whether a file is executable or not. The exact
    permissions can vary on systems with different umasks. Normalising
    to 644 (non executable) or 755 (executable) makes builds more reproducible.
    """
    # Set 644 permissions, leaving higher bits of st_mode unchanged
    new_mode = (st_mode | 0o644) & ~0o133
    if st_mode & 0o100:
        new_mode |= 0o111  # Executable: 644 -> 755

    return new_mode


def escape_version(version: str) -> str:
    """
    Escaped version in wheel filename. Doesn't exactly follow
    the escaping specification in :pep:`427#escaping-and-unicode`
    because this conflicts with :pep:`440#local-version-identifiers`.
    """
    warnings.warn(
        "escape_version() is deprecated. Use Version.parse().to_string() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return re.sub(r"[^\w\d.+]+", "_", version, flags=re.UNICODE)


def escape_name(name: str) -> str:
    """
    Escaped wheel name as specified in https://packaging.python.org/en/latest/specifications/binary-distribution-format/#escaping-and-unicode.
    This function should only be used for the generation of artifact names,
    and not to normalize or filter existing artifact names.
    """
    warnings.warn(
        (
            "escape_name() is deprecated. Use packaging.utils.canonicalize_name() and"
            " distribution_name() instead."
        ),
        DeprecationWarning,
        stacklevel=2,
    )
    return re.sub(r"[-_.]+", "_", name, flags=re.UNICODE).lower()


def distribution_name(name: NormalizedName) -> DistributionName:
    """
    A normalized name, but with "-" replaced by "_". This is used in various places:

    https://packaging.python.org/en/latest/specifications/binary-distribution-format/#escaping-and-unicode

    In distribution names ... This is equivalent to PEP 503 normalisation followed by
    replacing - with _.

    https://packaging.python.org/en/latest/specifications/source-distribution-format/#source-distribution-file-name

    ... {name} is normalised according to the same rules as for binary distributions

    https://packaging.python.org/en/latest/specifications/recording-installed-packages/#the-dist-info-directory

    This directory is named as {name}-{version}.dist-info, with name and version fields
    corresponding to Core metadata specifications. Both fields must be normalized
    (see PEP 503 and PEP 440 for the definition of normalization for each field
    respectively), and replace dash (-) characters with underscore (_) characters ...
    """
    distribution_name = name.replace("-", "_")
    return cast("DistributionName", distribution_name)
