from __future__ import annotations

import copy

from typing import TYPE_CHECKING
from typing import TypeVar

from packaging.utils import canonicalize_name


if TYPE_CHECKING:
    from collections.abc import Iterable

    from packaging.utils import NormalizedName

    T = TypeVar("T", bound="PackageSpecification")


class PackageSpecification:
    def __init__(
        self,
        name: str,
        source_type: str | None = None,
        source_url: str | None = None,
        source_reference: str | None = None,
        source_resolved_reference: str | None = None,
        source_subdirectory: str | None = None,
        features: Iterable[str] | None = None,
    ) -> None:
        from packaging.utils import canonicalize_name

        self._pretty_name = name
        self._name = canonicalize_name(name)
        self._source_type = source_type
        self._source_url = source_url
        self._source_reference = source_reference
        self._source_resolved_reference = source_resolved_reference
        self._source_subdirectory = source_subdirectory

        if not features:
            features = []

        self._features = frozenset(canonicalize_name(feature) for feature in features)

    @property
    def name(self) -> NormalizedName:
        return self._name

    @property
    def pretty_name(self) -> str:
        return self._pretty_name

    @property
    def complete_name(self) -> str:
        name: str = self._name

        if self._features:
            features = ",".join(sorted(self._features))
            name = f"{name}[{features}]"

        return name

    @property
    def source_type(self) -> str | None:
        return self._source_type

    @property
    def source_url(self) -> str | None:
        return self._source_url

    @property
    def source_reference(self) -> str | None:
        return self._source_reference

    @property
    def source_resolved_reference(self) -> str | None:
        return self._source_resolved_reference

    @property
    def source_subdirectory(self) -> str | None:
        return self._source_subdirectory

    @property
    def features(self) -> frozenset[NormalizedName]:
        return self._features

    def is_direct_origin(self) -> bool:
        return self._source_type in [
            "directory",
            "file",
            "url",
            "git",
        ]

    def provides(self, other: PackageSpecification) -> bool:
        """
        Helper method to determine if this package provides the given specification.

        This determination is made to be true, if the names are the same and this
        package provides all features required by the other specification.

        Source type checks are explicitly ignored here as this is not of interest.
        """
        return self.name == other.name and self.features.issuperset(other.features)

    def is_same_source_as(self, other: PackageSpecification) -> bool:
        if self._source_type != other.source_type:
            return False

        if not self._source_type:
            # both packages are of source type None
            # no need to check further
            return True

        if (
            self._source_url or other.source_url
        ) and self._source_url != other.source_url:
            return False

        if (
            self._source_subdirectory or other.source_subdirectory
        ) and self._source_subdirectory != other.source_subdirectory:
            return False

        # We check the resolved reference first:
        # if they match we assume equality regardless
        # of their source reference.
        # This is important when comparing a resolved branch VCS
        # dependency to a direct commit reference VCS dependency
        if (
            self._source_resolved_reference
            and other.source_resolved_reference
            and self._source_resolved_reference == other.source_resolved_reference
        ):
            return True

        if self._source_reference or other.source_reference:
            # special handling for packages with references
            if not (self._source_reference and other.source_reference):
                # case: one reference is defined and is non-empty, but other is not
                return False

            if not (
                self._source_reference == other.source_reference
                or self._source_reference.startswith(other.source_reference)
                or other.source_reference.startswith(self._source_reference)
            ):
                # case: both references defined, but one is not equal to or a short
                # representation of the other
                return False

            if (
                self._source_resolved_reference
                and other.source_resolved_reference
                and self._source_resolved_reference != other.source_resolved_reference
            ):
                return False

        return True

    def is_same_package_as(self, other: PackageSpecification) -> bool:
        if other.complete_name != self.complete_name:
            return False

        return self.is_same_source_as(other)

    def clone(self: T) -> T:
        return copy.deepcopy(self)

    def with_features(self: T, features: Iterable[str]) -> T:
        package = self.clone()

        package._features = frozenset(
            canonicalize_name(feature) for feature in features
        )

        return package

    def without_features(self: T) -> T:
        return self.with_features([])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageSpecification):
            return NotImplemented
        return self.is_same_package_as(other)

    def __hash__(self) -> int:
        result = hash(self.complete_name)  # complete_name includes features

        if self._source_type:
            # Don't include _source_reference and _source_resolved_reference in hash
            # because two specs can be equal even if these attributes are not equal.
            # (They must still meet certain conditions. See is_same_source_as().)
            result ^= (
                hash(self._source_type)
                ^ hash(self._source_url)
                ^ hash(self._source_subdirectory)
            )

        return result

    def __str__(self) -> str:
        raise NotImplementedError
