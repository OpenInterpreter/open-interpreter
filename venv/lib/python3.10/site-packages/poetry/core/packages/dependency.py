from __future__ import annotations

import os
import re
import warnings

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from typing import TypeVar

from packaging.utils import canonicalize_name

from poetry.core.constraints.generic import parse_constraint as parse_generic_constraint
from poetry.core.constraints.version import parse_constraint
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.specification import PackageSpecification
from poetry.core.packages.utils.utils import contains_group_without_marker
from poetry.core.packages.utils.utils import create_nested_marker
from poetry.core.packages.utils.utils import normalize_python_version_markers
from poetry.core.version.markers import parse_marker


if TYPE_CHECKING:
    from collections.abc import Iterable

    from packaging.utils import NormalizedName

    from poetry.core.constraints.version import VersionConstraint
    from poetry.core.packages.directory_dependency import DirectoryDependency
    from poetry.core.packages.file_dependency import FileDependency
    from poetry.core.version.markers import BaseMarker

    T = TypeVar("T", bound="Dependency")


class Dependency(PackageSpecification):
    def __init__(
        self,
        name: str,
        constraint: str | VersionConstraint,
        optional: bool = False,
        groups: Iterable[str] | None = None,
        allows_prereleases: bool = False,
        extras: Iterable[str] | None = None,
        source_type: str | None = None,
        source_url: str | None = None,
        source_reference: str | None = None,
        source_resolved_reference: str | None = None,
        source_subdirectory: str | None = None,
    ) -> None:
        from poetry.core.version.markers import AnyMarker

        super().__init__(
            name,
            source_type=source_type,
            source_url=source_url,
            source_reference=source_reference,
            source_resolved_reference=source_resolved_reference,
            source_subdirectory=source_subdirectory,
            features=extras,
        )

        self._constraint: VersionConstraint
        self._pretty_constraint: str
        self.constraint = constraint  # type: ignore[assignment]

        self._optional = optional

        if not groups:
            groups = [MAIN_GROUP]

        self._groups = frozenset(groups)
        self._allows_prereleases = allows_prereleases

        self._python_versions = "*"
        self._python_constraint = parse_constraint("*")
        self._transitive_python_versions: str | None = None
        self._transitive_python_constraint: VersionConstraint | None = None
        self._transitive_marker: BaseMarker | None = None

        self._in_extras: list[NormalizedName] = []

        self._activated = not self._optional

        self.is_root = False
        self._marker: BaseMarker = AnyMarker()
        self.source_name: str | None = None

    @property
    def name(self) -> NormalizedName:
        return self._name

    @property
    def constraint(self) -> VersionConstraint:
        return self._constraint

    @constraint.setter
    def constraint(self, constraint: str | VersionConstraint) -> None:
        if isinstance(constraint, str):
            self._constraint = parse_constraint(constraint)
        else:
            self._constraint = constraint

        self._pretty_constraint = str(constraint)

    def set_constraint(self, constraint: str | VersionConstraint) -> None:
        warnings.warn(
            (
                "Calling method 'set_constraint' is deprecated and will be removed. "
                "It has been replaced by the property 'constraint' for consistency."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        self.constraint = constraint  # type: ignore[assignment]

    @property
    def pretty_constraint(self) -> str:
        return self._pretty_constraint

    @property
    def pretty_name(self) -> str:
        return self._pretty_name

    @property
    def groups(self) -> frozenset[str]:
        return self._groups

    @property
    def python_versions(self) -> str:
        return self._python_versions

    @python_versions.setter
    def python_versions(self, value: str) -> None:
        self._python_versions = value
        self._python_constraint = parse_constraint(value)
        if not self._python_constraint.is_any():
            self._marker = self._marker.intersect(
                parse_marker(
                    create_nested_marker("python_version", self._python_constraint)
                )
            )

    @property
    def transitive_python_versions(self) -> str:
        if self._transitive_python_versions is None:
            return self._python_versions

        return self._transitive_python_versions

    @transitive_python_versions.setter
    def transitive_python_versions(self, value: str) -> None:
        self._transitive_python_versions = value
        self._transitive_python_constraint = parse_constraint(value)

    @property
    def marker(self) -> BaseMarker:
        return self._marker

    @marker.setter
    def marker(self, marker: str | BaseMarker) -> None:
        from poetry.core.constraints.version import parse_constraint
        from poetry.core.packages.utils.utils import convert_markers
        from poetry.core.version.markers import BaseMarker
        from poetry.core.version.markers import parse_marker

        if not isinstance(marker, BaseMarker):
            marker = parse_marker(marker)

        self._marker = marker

        markers = convert_markers(marker)

        if "extra" in markers:
            # If we have extras, the dependency is optional
            self.deactivate()

            for or_ in markers["extra"]:
                for op, extra in or_:
                    if op == "==":
                        self.in_extras.append(canonicalize_name(extra))
                    elif op == "" and "||" in extra:
                        for _extra in extra.split(" || "):
                            self.in_extras.append(canonicalize_name(_extra))

        # Recalculate python versions.
        self._python_versions = "*"
        if not contains_group_without_marker(markers, "python_version"):
            python_version_markers = markers["python_version"]
            self._python_versions = normalize_python_version_markers(
                python_version_markers
            )

        self._python_constraint = parse_constraint(self._python_versions)

    @property
    def transitive_marker(self) -> BaseMarker:
        if self._transitive_marker is None:
            return self.marker

        return self._transitive_marker

    @transitive_marker.setter
    def transitive_marker(self, value: BaseMarker) -> None:
        self._transitive_marker = value

    @property
    def python_constraint(self) -> VersionConstraint:
        return self._python_constraint

    @property
    def transitive_python_constraint(self) -> VersionConstraint:
        if self._transitive_python_constraint is None:
            return self._python_constraint

        return self._transitive_python_constraint

    @property
    def extras(self) -> frozenset[NormalizedName]:
        # extras activated in a dependency is the same as features
        return self._features

    @property
    def in_extras(self) -> list[NormalizedName]:
        return self._in_extras

    @property
    def base_pep_508_name(self) -> str:
        from poetry.core.constraints.version import Version
        from poetry.core.constraints.version import VersionUnion

        requirement = self.pretty_name

        if self.extras:
            extras = ",".join(sorted(self.extras))
            requirement += f"[{extras}]"

        constraint = self.constraint
        if isinstance(constraint, VersionUnion):
            if (
                constraint.excludes_single_version
                or constraint.excludes_single_wildcard_range
            ):
                # This branch is a short-circuit logic for special cases and
                # avoids having to split and parse constraint again. This has
                # no functional difference with the logic in the else branch.
                requirement += f" ({constraint})"
            else:
                constraints = ",".join(
                    str(parse_constraint(c)) for c in self.pretty_constraint.split(",")
                )
                requirement += f" ({constraints})"
        elif isinstance(constraint, Version):
            requirement += f" (=={constraint.text})"
        elif not constraint.is_any():
            requirement += f" ({str(constraint).replace(' ', '')})"

        return requirement

    def allows_prereleases(self) -> bool:
        return self._allows_prereleases

    def is_optional(self) -> bool:
        return self._optional

    def is_activated(self) -> bool:
        return self._activated

    def is_vcs(self) -> bool:
        return False

    def is_file(self) -> bool:
        return False

    def is_directory(self) -> bool:
        return False

    def is_url(self) -> bool:
        return False

    def to_pep_508(self, with_extras: bool = True) -> str:
        from poetry.core.packages.utils.utils import convert_markers

        requirement = self.base_pep_508_name

        markers = []
        has_extras = False
        if not self.marker.is_any():
            marker = self.marker
            if not with_extras:
                marker = marker.without_extras()

            # we re-check for any marker here since the without extra marker might
            # return an any marker again
            if not (marker.is_empty() or marker.is_any()):
                markers.append(str(marker))

            has_extras = "extra" in convert_markers(marker)
        else:
            # Python marker
            if self.python_versions != "*":
                python_constraint = self.python_constraint

                markers.append(
                    create_nested_marker("python_version", python_constraint)
                )

        in_extras = " || ".join(self._in_extras)
        if in_extras and with_extras and not has_extras:
            markers.append(
                create_nested_marker("extra", parse_generic_constraint(in_extras))
            )

        if markers:
            if len(markers) > 1:
                marker_str = " and ".join(f"({m})" for m in markers)
            else:
                marker_str = markers[0]
            requirement += f" ; {marker_str}"

        return requirement

    def activate(self) -> None:
        """
        Set the dependency as mandatory.
        """
        self._activated = True

    def deactivate(self) -> None:
        """
        Set the dependency as optional.
        """
        if not self._optional:
            self._optional = True

        self._activated = False

    def with_constraint(self: T, constraint: str | VersionConstraint) -> T:
        dependency = self.clone()
        dependency.constraint = constraint  # type: ignore[assignment]
        return dependency

    @classmethod
    def create_from_pep_508(
        cls, name: str, relative_to: Path | None = None
    ) -> Dependency:
        """
        Resolve a PEP-508 requirement string to a `Dependency` instance. If a
        `relative_to` path is specified, this is used as the base directory if the
        identified dependency is of file or directory type.
        """
        from poetry.core.packages.url_dependency import URLDependency
        from poetry.core.packages.utils.link import Link
        from poetry.core.packages.utils.utils import is_archive_file
        from poetry.core.packages.utils.utils import is_python_project
        from poetry.core.packages.utils.utils import is_url
        from poetry.core.packages.utils.utils import path_to_url
        from poetry.core.packages.utils.utils import strip_extras
        from poetry.core.packages.utils.utils import url_to_path
        from poetry.core.packages.vcs_dependency import VCSDependency
        from poetry.core.utils.patterns import wheel_file_re
        from poetry.core.vcs.git import ParsedUrl
        from poetry.core.version.requirements import Requirement

        # Removing comments
        parts = name.split(" #", 1)
        name = parts[0].strip()
        if len(parts) > 1:
            rest = parts[1]
            if " ;" in rest:
                name += " ;" + rest.split(" ;", 1)[1]

        req = Requirement(name)

        name = req.name
        link = None

        if is_url(name):
            link = Link(name)
        elif req.url:
            link = Link(req.url)
        else:
            path_str = os.path.normpath(os.path.abspath(name))
            p, extras = strip_extras(path_str)
            if os.path.isdir(p) and (os.path.sep in name or name.startswith(".")):
                if not is_python_project(Path(name)):
                    raise ValueError(
                        f"Directory {name!r} is not installable. File 'setup.[py|cfg]' "
                        "not found."
                    )
                link = Link(path_to_url(p))
            elif is_archive_file(p):
                link = Link(path_to_url(p))

        # it's a local file, dir, or url
        if link:
            is_file_uri = link.scheme == "file"
            is_relative_uri = is_file_uri and re.search(r"\.\./", link.url)

            # Handle relative file URLs
            if is_file_uri and is_relative_uri:
                path = Path(link.path)
                if relative_to:
                    path = relative_to / path
                link = Link(path_to_url(path))

            # wheel file
            version = None
            if link.is_wheel:
                m = wheel_file_re.match(link.filename)
                if not m:
                    raise ValueError(f"Invalid wheel name: {link.filename}")
                name = m.group("name")
                version = m.group("ver")

            dep: Dependency | None = None

            if link.scheme.startswith("git+"):
                url = ParsedUrl.parse(link.url)
                dep = VCSDependency(
                    name,
                    "git",
                    url.url,
                    rev=url.rev,
                    directory=url.subdirectory,
                    extras=req.extras,
                )
            elif link.scheme == "git":
                dep = VCSDependency(
                    name, "git", link.url_without_fragment, extras=req.extras
                )
            elif link.scheme in ("http", "https"):
                dep = URLDependency(
                    name,
                    link.url_without_fragment,
                    directory=link.subdirectory_fragment,
                    extras=req.extras,
                )
            elif is_file_uri:
                # handle RFC 8089 references
                path = url_to_path(req.url)
                dep = _make_file_or_dir_dep(
                    name=name,
                    path=path,
                    base=relative_to,
                    subdirectory=link.subdirectory_fragment,
                    extras=req.extras,
                )
            else:
                with suppress(ValueError):
                    # this is a local path not using the file URI scheme
                    dep = _make_file_or_dir_dep(
                        name=name,
                        path=Path(req.url),
                        base=relative_to,
                        extras=req.extras,
                    )

            if dep is None:
                dep = Dependency(name, version or "*", extras=req.extras)

            if version:
                dep._constraint = parse_constraint(version)
        else:
            constraint: VersionConstraint | str
            constraint = req.constraint if req.pretty_constraint else "*"
            dep = Dependency(name, constraint, extras=req.extras)

        if req.marker:
            dep.marker = req.marker

        return dep

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dependency):
            return NotImplemented

        # "constraint" is implicitly given for direct origin dependencies and might not
        # be set yet ("*"). Thus, it shouldn't be used to determine if two direct origin
        # dependencies are equal.
        # Calling is_direct_origin() for one dependency is sufficient because
        # super().__eq__() returns False for different origins.
        return super().__eq__(other) and (
            self._constraint == other.constraint or self.is_direct_origin()
        )

    def __hash__(self) -> int:
        # don't include _constraint in hash because it is mutable!
        return super().__hash__()

    def __str__(self) -> str:
        if self.is_root:
            return self._pretty_name
        if self.is_direct_origin():
            # adding version since this information is especially useful in debug output
            parts = [p.strip() for p in self.base_pep_508_name.split("@", 1)]
            return f"{parts[0]} ({self._pretty_constraint}) @ {parts[1]}"
        return self.base_pep_508_name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self}>"


def _make_file_or_dir_dep(
    name: str,
    path: Path,
    base: Path | None = None,
    subdirectory: str | None = None,
    extras: list[str] | None = None,
) -> FileDependency | DirectoryDependency | None:
    """
    Helper function to create a file or directoru dependency with the given arguments.
    If path is not a file or directory that exists, `None` is returned.
    """
    from poetry.core.packages.directory_dependency import DirectoryDependency
    from poetry.core.packages.file_dependency import FileDependency

    _path = path
    if not path.is_absolute() and base:
        # a base path was specified, so we should respect that
        _path = Path(base) / path

    if _path.is_file():
        return FileDependency(
            name, path, base=base, directory=subdirectory, extras=extras
        )
    elif _path.is_dir():
        if subdirectory:
            path = path / subdirectory
        return DirectoryDependency(name, path, base=base, extras=extras)

    return None
