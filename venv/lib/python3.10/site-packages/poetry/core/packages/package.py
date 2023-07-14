from __future__ import annotations

import copy
import re
import warnings

from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import TypeVar

from poetry.core.constraints.version import parse_constraint
from poetry.core.constraints.version.exceptions import ParseConstraintError
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.specification import PackageSpecification
from poetry.core.packages.utils.utils import create_nested_marker
from poetry.core.version.exceptions import InvalidVersion
from poetry.core.version.markers import parse_marker


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path

    from packaging.utils import NormalizedName

    from poetry.core.constraints.version import Version
    from poetry.core.constraints.version import VersionConstraint
    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.dependency_group import DependencyGroup
    from poetry.core.spdx.license import License
    from poetry.core.version.markers import BaseMarker

    T = TypeVar("T", bound="Package")

AUTHOR_REGEX = re.compile(
    r"(?u)^(?P<name>[- .,\w\d'’\"():&]+)(?: <(?P<email>.+?)>)?$"  # noqa: RUF001
)


class Package(PackageSpecification):
    AVAILABLE_PYTHONS = {
        "2",
        "2.7",
        "3",
        "3.4",
        "3.5",
        "3.6",
        "3.7",
        "3.8",
        "3.9",
        "3.10",
        "3.11",
    }

    def __init__(
        self,
        name: str,
        version: str | Version,
        pretty_version: str | None = None,
        source_type: str | None = None,
        source_url: str | None = None,
        source_reference: str | None = None,
        source_resolved_reference: str | None = None,
        source_subdirectory: str | None = None,
        features: Iterable[str] | None = None,
        develop: bool = False,
        yanked: str | bool = False,
    ) -> None:
        """
        Creates a new in memory package.
        """
        from poetry.core.version.markers import AnyMarker

        if pretty_version is not None:
            warnings.warn(
                (
                    "The `pretty_version` parameter is deprecated and will be removed"
                    " in a future release."
                ),
                DeprecationWarning,
                stacklevel=2,
            )

        super().__init__(
            name,
            source_type=source_type,
            source_url=source_url,
            source_reference=source_reference,
            source_resolved_reference=source_resolved_reference,
            source_subdirectory=source_subdirectory,
            features=features,
        )

        self._set_version(version)

        self.description = ""

        self._authors: list[str] = []
        self._maintainers: list[str] = []

        self.homepage: str | None = None
        self.repository_url: str | None = None
        self.documentation_url: str | None = None
        self.keywords: list[str] = []
        self._license: License | None = None
        self.readmes: tuple[Path, ...] = ()

        self.extras: dict[NormalizedName, list[Dependency]] = {}

        self._dependency_groups: dict[str, DependencyGroup] = {}

        # Category is heading towards deprecation.
        self._category = "main"
        self.files: list[dict[str, str]] = []
        self.optional = False

        self.classifiers: list[str] = []

        self._python_versions = "*"
        self._python_constraint = parse_constraint("*")
        self._python_marker: BaseMarker = AnyMarker()

        self.marker: BaseMarker = AnyMarker()

        self.root_dir: Path | None = None

        self.develop = develop

        self._yanked = yanked

    @property
    def name(self) -> NormalizedName:
        return self._name

    @property
    def pretty_name(self) -> str:
        return self._pretty_name

    @property
    def version(self) -> Version:
        return self._version

    @property
    def pretty_version(self) -> str:
        return self._version.text

    @property
    def unique_name(self) -> str:
        if self.is_root():
            return self._name

        return self.complete_name + "-" + self._version.text

    @property
    def pretty_string(self) -> str:
        return self.pretty_name + " " + self.pretty_version

    @property
    def full_pretty_version(self) -> str:
        if self.source_type in ("file", "directory", "url"):
            return f"{self.pretty_version} {self.source_url}"

        if self.source_type not in ("hg", "git"):
            return self.pretty_version

        ref: str | None
        if self.source_resolved_reference and len(self.source_resolved_reference) == 40:
            ref = self.source_resolved_reference[0:7]
            return f"{self.pretty_version} {ref}"

        # if source reference is a sha1 hash -- truncate
        if self.source_reference and len(self.source_reference) == 40:
            return f"{self.pretty_version} {self.source_reference[0:7]}"

        ref = self._source_resolved_reference or self._source_reference
        return f"{self.pretty_version} {ref}"

    @property
    def authors(self) -> list[str]:
        return self._authors

    @property
    def author_name(self) -> str | None:
        return self._get_author()["name"]

    @property
    def author_email(self) -> str | None:
        return self._get_author()["email"]

    @property
    def maintainers(self) -> list[str]:
        return self._maintainers

    @property
    def maintainer_name(self) -> str | None:
        return self._get_maintainer()["name"]

    @property
    def maintainer_email(self) -> str | None:
        return self._get_maintainer()["email"]

    @property
    def requires(self) -> list[Dependency]:
        """
        Returns the main dependencies
        """
        if not self._dependency_groups or MAIN_GROUP not in self._dependency_groups:
            return []

        return self._dependency_groups[MAIN_GROUP].dependencies

    @property
    def all_requires(
        self,
    ) -> list[Dependency]:
        """
        Returns the main dependencies and group dependencies.
        """
        return [
            dependency
            for group in self._dependency_groups.values()
            for dependency in group.dependencies
        ]

    def _set_version(self, version: str | Version) -> None:
        from poetry.core.constraints.version import Version

        if not isinstance(version, Version):
            try:
                version = Version.parse(version)
            except InvalidVersion:
                raise InvalidVersion(
                    f"Invalid version '{version}' on package {self.name}"
                )

        self._version = version

    def _get_author(self) -> dict[str, str | None]:
        if not self._authors:
            return {"name": None, "email": None}

        m = AUTHOR_REGEX.match(self._authors[0])

        if m is None:
            raise ValueError(
                "Invalid author string. Must be in the format: "
                "John Smith <john@example.com>"
            )

        name = m.group("name")
        email = m.group("email")

        return {"name": name, "email": email}

    def _get_maintainer(self) -> dict[str, str | None]:
        if not self._maintainers:
            return {"name": None, "email": None}

        m = AUTHOR_REGEX.match(self._maintainers[0])

        if m is None:
            raise ValueError(
                "Invalid maintainer string. Must be in the format: "
                "John Smith <john@example.com>"
            )

        name = m.group("name")
        email = m.group("email")

        return {"name": name, "email": email}

    @property
    def python_versions(self) -> str:
        return self._python_versions

    @python_versions.setter
    def python_versions(self, value: str) -> None:
        try:
            constraint = parse_constraint(value)
        except ParseConstraintError:
            raise ParseConstraintError(f"Invalid python versions '{value}' on {self}")

        self._python_versions = value
        self._python_constraint = constraint
        self._python_marker = parse_marker(
            create_nested_marker("python_version", self._python_constraint)
        )

    @property
    def python_constraint(self) -> VersionConstraint:
        return self._python_constraint

    @property
    def python_marker(self) -> BaseMarker:
        return self._python_marker

    @property
    def license(self) -> License | None:
        return self._license

    @license.setter
    def license(self, value: str | License | None) -> None:
        from poetry.core.spdx.helpers import license_by_id
        from poetry.core.spdx.license import License

        if value is None or isinstance(value, License):
            self._license = value
        else:
            self._license = license_by_id(value)

    @property
    def all_classifiers(self) -> list[str]:
        from poetry.core.constraints.version import Version

        classifiers = copy.copy(self.classifiers)

        # Automatically set python classifiers
        if self.python_versions == "*":
            python_constraint = parse_constraint("~2.7 || ^3.4")
        else:
            python_constraint = self.python_constraint

        python_classifier_prefix = "Programming Language :: Python"
        python_classifiers = []

        # we sort python versions by sorting an int tuple of (major, minor) version
        # to ensure we sort 3.10 after 3.9
        for version in sorted(
            self.AVAILABLE_PYTHONS, key=lambda x: tuple(map(int, x.split(".")))
        ):
            if len(version) == 1:
                constraint = parse_constraint(version + ".*")
            else:
                constraint = Version.parse(version)

            if python_constraint.allows_any(constraint):
                classifier = f"{python_classifier_prefix} :: {version}"
                if classifier not in python_classifiers:
                    python_classifiers.append(classifier)

        # Automatically set license classifiers
        if self.license:
            classifiers.append(self.license.classifier)

        # Sort classifiers and insert python classifiers at the right location. We do
        # it like this so that 3.10 is sorted after 3.9.
        sorted_classifiers = []
        python_classifiers_inserted = False
        for classifier in sorted(set(classifiers) - set(python_classifiers)):
            if (
                not python_classifiers_inserted
                and classifier > python_classifier_prefix
            ):
                sorted_classifiers.extend(python_classifiers)
                python_classifiers_inserted = True
            sorted_classifiers.append(classifier)

        if not python_classifiers_inserted:
            sorted_classifiers.extend(python_classifiers)

        return sorted_classifiers

    @property
    def urls(self) -> dict[str, str]:
        urls = {}

        if self.homepage:
            urls["Homepage"] = self.homepage

        if self.repository_url:
            urls["Repository"] = self.repository_url

        if self.documentation_url:
            urls["Documentation"] = self.documentation_url

        return urls

    @property
    def category(self) -> str:
        warnings.warn(
            "`category` is deprecated and will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._category

    @category.setter
    def category(self, category: str) -> None:
        warnings.warn(
            "Setting `category` is deprecated and will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._category = category

    @property
    def readme(self) -> Path | None:
        warnings.warn(
            (
                "`readme` is deprecated: you are getting only the first readme file."
                " Please use the plural form `readmes`."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return next(iter(self.readmes), None)

    @readme.setter
    def readme(self, path: Path) -> None:
        warnings.warn(
            (
                "`readme` is deprecated. Please assign a tuple to the plural form"
                " `readmes`."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        self.readmes = (path,)

    @property
    def yanked(self) -> bool:
        return isinstance(self._yanked, str) or bool(self._yanked)

    @property
    def yanked_reason(self) -> str:
        if isinstance(self._yanked, str):
            return self._yanked
        return ""

    def is_prerelease(self) -> bool:
        return self._version.is_unstable()

    def is_root(self) -> bool:
        return False

    def dependency_group_names(self, include_optional: bool = False) -> set[str]:
        return {
            name
            for name, group in self._dependency_groups.items()
            if not group.is_optional() or include_optional
        }

    def add_dependency_group(self, group: DependencyGroup) -> None:
        self._dependency_groups[group.name] = group

    def has_dependency_group(self, name: str) -> bool:
        return name in self._dependency_groups

    def dependency_group(self, name: str) -> DependencyGroup:
        if not self.has_dependency_group(name):
            raise ValueError(f'The dependency group "{name}" does not exist.')

        return self._dependency_groups[name]

    def add_dependency(
        self,
        dependency: Dependency,
    ) -> Dependency:
        from poetry.core.packages.dependency_group import DependencyGroup

        for group_name in dependency.groups:
            if group_name not in self._dependency_groups:
                # Dynamically add the dependency group
                self.add_dependency_group(DependencyGroup(group_name))

            self._dependency_groups[group_name].add_dependency(dependency)

        return dependency

    def without_dependency_groups(self: T, groups: Collection[str]) -> T:
        """
        Returns a clone of the package with the given dependency groups excluded.
        """
        package = self.clone()

        for group_name in groups:
            if group_name in package._dependency_groups:
                del package._dependency_groups[group_name]

        return package

    def without_optional_dependency_groups(self: T) -> T:
        """
        Returns a clone of the package without optional dependency groups.
        """
        package = self.clone()

        for group_name, group in self._dependency_groups.items():
            if group.is_optional():
                del package._dependency_groups[group_name]

        return package

    def with_dependency_groups(
        self: T, groups: Collection[str], only: bool = False
    ) -> T:
        """
        Returns a clone of the package with the given dependency groups opted in.

        Note that it will return all dependencies across all groups
        more the given, optional, groups.

        If `only` is set to True, then only the given groups will be selected.
        """
        package = self.clone()

        for group_name, group in self._dependency_groups.items():
            if (only or group.is_optional()) and group_name not in groups:
                del package._dependency_groups[group_name]

        return package

    def to_dependency(self) -> Dependency:
        from pathlib import Path

        from poetry.core.packages.dependency import Dependency
        from poetry.core.packages.directory_dependency import DirectoryDependency
        from poetry.core.packages.file_dependency import FileDependency
        from poetry.core.packages.url_dependency import URLDependency
        from poetry.core.packages.vcs_dependency import VCSDependency

        dep: Dependency
        if self.source_type == "directory":
            assert self._source_url is not None
            dep = DirectoryDependency(
                self._name,
                Path(self._source_url),
                groups=list(self._dependency_groups.keys()),
                optional=self.optional,
                base=self.root_dir,
                develop=self.develop,
                extras=self.features,
            )
        elif self.source_type == "file":
            assert self._source_url is not None
            dep = FileDependency(
                self._name,
                Path(self._source_url),
                directory=self.source_subdirectory,
                groups=list(self._dependency_groups.keys()),
                optional=self.optional,
                base=self.root_dir,
                extras=self.features,
            )
        elif self.source_type == "url":
            assert self._source_url is not None
            dep = URLDependency(
                self._name,
                self._source_url,
                directory=self.source_subdirectory,
                groups=list(self._dependency_groups.keys()),
                optional=self.optional,
                extras=self.features,
            )
        elif self.source_type == "git":
            assert self._source_url is not None
            dep = VCSDependency(
                self._name,
                self.source_type,
                self._source_url,
                rev=self.source_reference,
                resolved_rev=self.source_resolved_reference,
                directory=self.source_subdirectory,
                groups=list(self._dependency_groups.keys()),
                optional=self.optional,
                develop=self.develop,
                extras=self.features,
            )
        else:
            dep = Dependency(self._name, self._version, extras=self.features)

        if not self.marker.is_any():
            dep.marker = self.marker

        if not self.python_constraint.is_any():
            dep.python_versions = self.python_versions

        if not self.is_direct_origin():
            return dep

        return dep.with_constraint(self._version)

    @contextmanager
    def with_python_versions(self, python_versions: str) -> Iterator[None]:
        original_python_versions = self.python_versions

        self.python_versions = python_versions

        yield

        self.python_versions = original_python_versions

    def satisfies(
        self, dependency: Dependency, ignore_source_type: bool = False
    ) -> bool:
        """
        Helper method to check if this package satisfies a given dependency.

        This is determined by assessing if this instance provides the package specified
        by the given dependency. Further, version and source types are checked.
        """
        if self.name != dependency.name:
            return False

        if not dependency.constraint.allows(self.version):
            return False

        if not (ignore_source_type or self.source_satisfies(dependency)):
            return False

        return True

    def source_satisfies(self, dependency: Dependency) -> bool:
        """Determine whether this package's source satisfies the given dependency."""
        if dependency.source_type is None:
            if dependency.source_name is None:
                # The dependency doesn't care about the source, so this package
                # certainly satisfies it.
                return True

            # The dependency specifies a source_name but not a type: it wants either
            # pypi or a legacy repository.
            #
            # - If this package has no source type then it's from pypi, so it
            #   matches if and only if that's what the dependency wants
            # - Else this package is a match if and only if it is from the desired
            #   repository
            if self.source_type is None:
                return dependency.source_name.lower() == "pypi"

            return (
                self.source_type == "legacy"
                and self.source_reference is not None
                and self.source_reference.lower() == dependency.source_name.lower()
            )

        # The dependency specifies a source: this package matches if and only if it is
        # from that source.
        return dependency.is_same_source_as(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Package):
            return NotImplemented

        return super().__eq__(other) and self._version == other.version

    def __hash__(self) -> int:
        return super().__hash__() ^ hash(self._version)

    def __str__(self) -> str:
        return f"{self.complete_name} ({self.full_pretty_version})"

    def __repr__(self) -> str:
        args = [repr(self._name), repr(self._version.text)]

        if self._features:
            args.append(f"features={self._features!r}")

        if self._source_type:
            args.append(f"source_type={self._source_type!r}")
            args.append(f"source_url={self._source_url!r}")

            if self._source_reference:
                args.append(f"source_reference={self._source_reference!r}")

            if self._source_resolved_reference:
                args.append(
                    f"source_resolved_reference={self._source_resolved_reference!r}"
                )
            if self._source_subdirectory:
                args.append(f"source_subdirectory={self._source_subdirectory!r}")

        args_str = ", ".join(args)
        return f"Package({args_str})"
