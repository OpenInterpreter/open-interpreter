import json
import logging
import os
import re

from copy import deepcopy
from hashlib import sha256
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import Union

from tomlkit import array
from tomlkit import document
from tomlkit import inline_table
from tomlkit import item
from tomlkit import table
from tomlkit.exceptions import TOMLKitError

import poetry.repositories

from poetry.core.packages import dependency_from_pep_508
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.package import Package
from poetry.core.semver import parse_constraint
from poetry.core.semver.version import Version
from poetry.core.toml.file import TOMLFile
from poetry.core.version.markers import parse_marker
from poetry.core.version.requirements import InvalidRequirement
from poetry.packages import DependencyPackage
from poetry.utils._compat import OrderedDict
from poetry.utils._compat import Path
from poetry.utils.extras import get_extra_package_names


logger = logging.getLogger(__name__)


class Locker(object):

    _VERSION = "1.1"

    _relevant_keys = ["dependencies", "dev-dependencies", "source", "extras"]

    def __init__(self, lock, local_config):  # type: (Path, dict) -> None
        self._lock = TOMLFile(lock)
        self._local_config = local_config
        self._lock_data = None
        self._content_hash = self._get_content_hash()

    @property
    def lock(self):  # type: () -> TOMLFile
        return self._lock

    @property
    def lock_data(self):
        if self._lock_data is None:
            self._lock_data = self._get_lock_data()

        return self._lock_data

    def is_locked(self):  # type: () -> bool
        """
        Checks whether the locker has been locked (lockfile found).
        """
        if not self._lock.exists():
            return False

        return "package" in self.lock_data

    def is_fresh(self):  # type: () -> bool
        """
        Checks whether the lock file is still up to date with the current hash.
        """
        lock = self._lock.read()
        metadata = lock.get("metadata", {})

        if "content-hash" in metadata:
            return self._content_hash == lock["metadata"]["content-hash"]

        return False

    def locked_repository(
        self, with_dev_reqs=False
    ):  # type: (bool) -> poetry.repositories.Repository
        """
        Searches and returns a repository of locked packages.
        """
        from poetry.factory import Factory

        if not self.is_locked():
            return poetry.repositories.Repository()

        lock_data = self.lock_data
        packages = poetry.repositories.Repository()

        if with_dev_reqs:
            locked_packages = lock_data["package"]
        else:
            locked_packages = [
                p for p in lock_data["package"] if p["category"] == "main"
            ]

        if not locked_packages:
            return packages

        for info in locked_packages:
            source = info.get("source", {})
            source_type = source.get("type")
            url = source.get("url")
            if source_type in ["directory", "file"]:
                url = self._lock.path.parent.joinpath(url).resolve().as_posix()

            package = Package(
                info["name"],
                info["version"],
                info["version"],
                source_type=source_type,
                source_url=url,
                source_reference=source.get("reference"),
                source_resolved_reference=source.get("resolved_reference"),
            )
            package.description = info.get("description", "")
            package.category = info["category"]
            package.optional = info["optional"]
            if "hashes" in lock_data["metadata"]:
                # Old lock so we create dummy files from the hashes
                package.files = [
                    {"name": h, "hash": h}
                    for h in lock_data["metadata"]["hashes"][info["name"]]
                ]
            else:
                package.files = lock_data["metadata"]["files"][info["name"]]

            package.python_versions = info["python-versions"]
            extras = info.get("extras", {})
            if extras:
                for name, deps in extras.items():
                    package.extras[name] = []

                    for dep in deps:
                        try:
                            dependency = dependency_from_pep_508(dep)
                        except InvalidRequirement:
                            # handle lock files with invalid PEP 508
                            m = re.match(r"^(.+?)(?:\[(.+?)])?(?:\s+\((.+)\))?$", dep)
                            dep_name = m.group(1)
                            extras = m.group(2) or ""
                            constraint = m.group(3) or "*"
                            dependency = Dependency(
                                dep_name, constraint, extras=extras.split(",")
                            )
                        package.extras[name].append(dependency)

            if "marker" in info:
                package.marker = parse_marker(info["marker"])
            else:
                # Compatibility for old locks
                if "requirements" in info:
                    dep = Dependency("foo", "0.0.0")
                    for name, value in info["requirements"].items():
                        if name == "python":
                            dep.python_versions = value
                        elif name == "platform":
                            dep.platform = value

                    split_dep = dep.to_pep_508(False).split(";")
                    if len(split_dep) > 1:
                        package.marker = parse_marker(split_dep[1].strip())

            for dep_name, constraint in info.get("dependencies", {}).items():

                root_dir = self._lock.path.parent
                if package.source_type == "directory":
                    # root dir should be the source of the package relative to the lock path
                    root_dir = Path(package.source_url)

                if isinstance(constraint, list):
                    for c in constraint:
                        package.add_dependency(
                            Factory.create_dependency(dep_name, c, root_dir=root_dir)
                        )

                    continue

                package.add_dependency(
                    Factory.create_dependency(dep_name, constraint, root_dir=root_dir)
                )

            if "develop" in info:
                package.develop = info["develop"]

            packages.add_package(package)

        return packages

    @staticmethod
    def __get_locked_package(
        _dependency, packages_by_name
    ):  # type: (Dependency, Dict[str, List[Package]]) -> Optional[Package]
        """
        Internal helper to identify corresponding locked package using dependency
        version constraints.
        """
        for _package in packages_by_name.get(_dependency.name, []):
            if _dependency.constraint.allows(_package.version):
                return _package
        return None

    @classmethod
    def __walk_dependency_level(
        cls,
        dependencies,
        level,
        pinned_versions,
        packages_by_name,
        project_level_dependencies,
        nested_dependencies,
    ):  # type: (List[Dependency], int,  bool, Dict[str, List[Package]], Set[str], Dict[Tuple[str, str], Dependency]) -> Dict[Tuple[str, str], Dependency]
        if not dependencies:
            return nested_dependencies

        next_level_dependencies = []

        for requirement in dependencies:
            key = (requirement.name, requirement.pretty_constraint)
            locked_package = cls.__get_locked_package(requirement, packages_by_name)

            if locked_package:
                # create dependency from locked package to retain dependency metadata
                # if this is not done, we can end-up with incorrect nested dependencies
                marker = requirement.marker
                requirement = locked_package.to_dependency()
                requirement.marker = requirement.marker.intersect(marker)

                key = (requirement.name, requirement.pretty_constraint)

                if pinned_versions:
                    requirement.set_constraint(
                        locked_package.to_dependency().constraint
                    )

                for require in locked_package.requires:
                    if require.marker.is_empty():
                        require.marker = requirement.marker
                    else:
                        require.marker = require.marker.intersect(requirement.marker)

                    require.marker = require.marker.intersect(locked_package.marker)

                    if key not in nested_dependencies:
                        next_level_dependencies.append(require)

            if requirement.name in project_level_dependencies and level == 0:
                # project level dependencies take precedence
                continue

            if not locked_package:
                # we make a copy to avoid any side-effects
                requirement = deepcopy(requirement)

            if key not in nested_dependencies:
                nested_dependencies[key] = requirement
            else:
                nested_dependencies[key].marker = nested_dependencies[
                    key
                ].marker.intersect(requirement.marker)

        return cls.__walk_dependency_level(
            dependencies=next_level_dependencies,
            level=level + 1,
            pinned_versions=pinned_versions,
            packages_by_name=packages_by_name,
            project_level_dependencies=project_level_dependencies,
            nested_dependencies=nested_dependencies,
        )

    @classmethod
    def get_project_dependencies(
        cls, project_requires, locked_packages, pinned_versions=False, with_nested=False
    ):  # type: (List[Dependency], List[Package], bool, bool) -> Iterable[Dependency]
        # group packages entries by name, this is required because requirement might use different constraints
        packages_by_name = {}
        for pkg in locked_packages:
            if pkg.name not in packages_by_name:
                packages_by_name[pkg.name] = []
            packages_by_name[pkg.name].append(pkg)

        project_level_dependencies = set()
        dependencies = []

        for dependency in project_requires:
            dependency = deepcopy(dependency)
            locked_package = cls.__get_locked_package(dependency, packages_by_name)
            if locked_package:
                locked_dependency = locked_package.to_dependency()
                locked_dependency.marker = dependency.marker.intersect(
                    locked_package.marker
                )

                if not pinned_versions:
                    locked_dependency.set_constraint(dependency.constraint)

                dependency = locked_dependency

            project_level_dependencies.add(dependency.name)
            dependencies.append(dependency)

        if not with_nested:
            # return only with project level dependencies
            return dependencies

        nested_dependencies = cls.__walk_dependency_level(
            dependencies=dependencies,
            level=0,
            pinned_versions=pinned_versions,
            packages_by_name=packages_by_name,
            project_level_dependencies=project_level_dependencies,
            nested_dependencies=dict(),
        )

        # Merge same dependencies using marker union
        for requirement in dependencies:
            key = (requirement.name, requirement.pretty_constraint)
            if key not in nested_dependencies:
                nested_dependencies[key] = requirement
            else:
                nested_dependencies[key].marker = nested_dependencies[key].marker.union(
                    requirement.marker
                )

        return sorted(nested_dependencies.values(), key=lambda x: x.name.lower())

    def get_project_dependency_packages(
        self, project_requires, dev=False, extras=None
    ):  # type: (List[Dependency], bool, Optional[Union[bool, Sequence[str]]]) -> Iterator[DependencyPackage]
        repository = self.locked_repository(with_dev_reqs=dev)

        # Build a set of all packages required by our selected extras
        extra_package_names = (
            None if (isinstance(extras, bool) and extras is True) else ()
        )

        if extra_package_names is not None:
            extra_package_names = set(
                get_extra_package_names(
                    repository.packages, self.lock_data.get("extras", {}), extras or (),
                )
            )

        # If a package is optional and we haven't opted in to it, do not select
        selected = []
        for dependency in project_requires:
            try:
                package = repository.find_packages(dependency=dependency)[0]
            except IndexError:
                continue

            if extra_package_names is not None and (
                package.optional and package.name not in extra_package_names
            ):
                # a package is locked as optional, but is not activated via extras
                continue

            selected.append(dependency)

        for dependency in self.get_project_dependencies(
            project_requires=selected,
            locked_packages=repository.packages,
            with_nested=True,
        ):
            try:
                package = repository.find_packages(dependency=dependency)[0]
            except IndexError:
                continue

            for extra in dependency.extras:
                package.requires_extras.append(extra)

            yield DependencyPackage(dependency=dependency, package=package)

    def set_lock_data(self, root, packages):  # type: (...) -> bool
        files = table()
        packages = self._lock_packages(packages)
        # Retrieving hashes
        for package in packages:
            if package["name"] not in files:
                files[package["name"]] = []

            for f in package["files"]:
                file_metadata = inline_table()
                for k, v in sorted(f.items()):
                    file_metadata[k] = v

                files[package["name"]].append(file_metadata)

            if files[package["name"]]:
                files[package["name"]] = item(files[package["name"]]).multiline(True)

            del package["files"]

        lock = document()
        lock["package"] = packages

        if root.extras:
            lock["extras"] = {
                extra: [dep.pretty_name for dep in deps]
                for extra, deps in sorted(root.extras.items())
            }

        lock["metadata"] = OrderedDict(
            [
                ("lock-version", self._VERSION),
                ("python-versions", root.python_versions),
                ("content-hash", self._content_hash),
                ("files", files),
            ]
        )

        if not self.is_locked() or lock != self.lock_data:
            self._write_lock_data(lock)

            return True

        return False

    def _write_lock_data(self, data):
        self.lock.write(data)

        # Checking lock file data consistency
        if data != self.lock.read():
            raise RuntimeError("Inconsistent lock file data.")

        self._lock_data = None

    def _get_content_hash(self):  # type: () -> str
        """
        Returns the sha256 hash of the sorted content of the pyproject file.
        """
        content = self._local_config

        relevant_content = {}
        for key in self._relevant_keys:
            relevant_content[key] = content.get(key)

        content_hash = sha256(
            json.dumps(relevant_content, sort_keys=True).encode()
        ).hexdigest()

        return content_hash

    def _get_lock_data(self):  # type: () -> dict
        if not self._lock.exists():
            raise RuntimeError("No lockfile found. Unable to read locked packages")

        try:
            lock_data = self._lock.read()
        except TOMLKitError as e:
            raise RuntimeError("Unable to read the lock file ({}).".format(e))

        lock_version = Version.parse(lock_data["metadata"].get("lock-version", "1.0"))
        current_version = Version.parse(self._VERSION)
        # We expect the locker to be able to read lock files
        # from the same semantic versioning range
        accepted_versions = parse_constraint(
            "^{}".format(Version(current_version.major, 0))
        )
        lock_version_allowed = accepted_versions.allows(lock_version)
        if lock_version_allowed and current_version < lock_version:
            logger.warning(
                "The lock file might not be compatible with the current version of Poetry.\n"
                "Upgrade Poetry to ensure the lock file is read properly or, alternatively, "
                "regenerate the lock file with the `poetry lock` command."
            )
        elif not lock_version_allowed:
            raise RuntimeError(
                "The lock file is not compatible with the current version of Poetry.\n"
                "Upgrade Poetry to be able to read the lock file or, alternatively, "
                "regenerate the lock file with the `poetry lock` command."
            )

        return lock_data

    def _lock_packages(
        self, packages
    ):  # type: (List['poetry.packages.Package']) -> list
        locked = []

        for package in sorted(packages, key=lambda x: x.name):
            spec = self._dump_package(package)

            locked.append(spec)

        return locked

    def _dump_package(self, package):  # type: (Package) -> dict
        dependencies = OrderedDict()
        for dependency in sorted(package.requires, key=lambda d: d.name):
            if dependency.pretty_name not in dependencies:
                dependencies[dependency.pretty_name] = []

            constraint = inline_table()

            if dependency.is_directory() or dependency.is_file():
                constraint["path"] = dependency.path.as_posix()

                if dependency.is_directory() and dependency.develop:
                    constraint["develop"] = True
            elif dependency.is_url():
                constraint["url"] = dependency.url
            elif dependency.is_vcs():
                constraint[dependency.vcs] = dependency.source

                if dependency.branch:
                    constraint["branch"] = dependency.branch
                elif dependency.tag:
                    constraint["tag"] = dependency.tag
                elif dependency.rev:
                    constraint["rev"] = dependency.rev
            else:
                constraint["version"] = str(dependency.pretty_constraint)

            if dependency.extras:
                constraint["extras"] = sorted(dependency.extras)

            if dependency.is_optional():
                constraint["optional"] = True

            if not dependency.marker.is_any():
                constraint["markers"] = str(dependency.marker)

            dependencies[dependency.pretty_name].append(constraint)

        # All the constraints should have the same type,
        # but we want to simplify them if it's possible
        for dependency, constraints in tuple(dependencies.items()):
            if all(
                len(constraint) == 1 and "version" in constraint
                for constraint in constraints
            ):
                dependencies[dependency] = [
                    constraint["version"] for constraint in constraints
                ]

        data = OrderedDict(
            [
                ("name", package.pretty_name),
                ("version", package.pretty_version),
                ("description", package.description or ""),
                ("category", package.category),
                ("optional", package.optional),
                ("python-versions", package.python_versions),
                ("files", sorted(package.files, key=lambda x: x["file"])),
            ]
        )

        if dependencies:
            data["dependencies"] = table()
            for k, constraints in dependencies.items():
                if len(constraints) == 1:
                    data["dependencies"][k] = constraints[0]
                else:
                    data["dependencies"][k] = array().multiline(True)
                    for constraint in constraints:
                        data["dependencies"][k].append(constraint)

        if package.extras:
            extras = {}
            for name, deps in package.extras.items():
                # TODO: This should use dep.to_pep_508() once this is fixed
                # https://github.com/python-poetry/poetry-core/pull/102
                extras[name] = [
                    dep.base_pep_508_name if not dep.constraint.is_any() else dep.name
                    for dep in deps
                ]

            data["extras"] = extras

        if package.source_url:
            url = package.source_url
            if package.source_type in ["file", "directory"]:
                # The lock file should only store paths relative to the root project
                url = Path(
                    os.path.relpath(
                        Path(url).as_posix(), self._lock.path.parent.as_posix()
                    )
                ).as_posix()

            data["source"] = OrderedDict()

            if package.source_type:
                data["source"]["type"] = package.source_type

            data["source"]["url"] = url

            if package.source_reference:
                data["source"]["reference"] = package.source_reference

            if package.source_resolved_reference:
                data["source"]["resolved_reference"] = package.source_resolved_reference

            if package.source_type in ["directory", "git"]:
                data["develop"] = package.develop

        return data


class NullLocker(Locker):
    def set_lock_data(self, root, packages):  # type: (Package, List[Package]) -> None
        pass
