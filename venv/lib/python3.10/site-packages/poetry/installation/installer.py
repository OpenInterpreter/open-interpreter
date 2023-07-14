from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from cleo.io.null_io import NullIO
from packaging.utils import canonicalize_name

from poetry.installation.executor import Executor
from poetry.installation.operations import Install
from poetry.installation.operations import Uninstall
from poetry.installation.operations import Update
from poetry.repositories import Repository
from poetry.repositories import RepositoryPool
from poetry.repositories.installed_repository import InstalledRepository
from poetry.repositories.lockfile_repository import LockfileRepository
from poetry.utils.extras import get_extra_package_names


if TYPE_CHECKING:
    from collections.abc import Iterable

    from cleo.io.io import IO
    from packaging.utils import NormalizedName
    from poetry.core.packages.path_dependency import PathDependency
    from poetry.core.packages.project_package import ProjectPackage

    from poetry.config.config import Config
    from poetry.installation.operations.operation import Operation
    from poetry.packages import Locker
    from poetry.utils.env import Env


class Installer:
    def __init__(
        self,
        io: IO,
        env: Env,
        package: ProjectPackage,
        locker: Locker,
        pool: RepositoryPool,
        config: Config,
        installed: Repository | None = None,
        executor: Executor | None = None,
        disable_cache: bool = False,
    ) -> None:
        self._io = io
        self._env = env
        self._package = package
        self._locker = locker
        self._pool = pool
        self._config = config

        self._dry_run = False
        self._requires_synchronization = False
        self._update = False
        self._verbose = False
        self._groups: Iterable[str] | None = None
        self._skip_directory = False
        self._lock = False

        self._whitelist: list[NormalizedName] = []

        self._extras: list[NormalizedName] = []

        if executor is None:
            executor = Executor(
                self._env, self._pool, config, self._io, disable_cache=disable_cache
            )

        self._executor = executor

        if installed is None:
            installed = self._get_installed()

        self._installed_repository = installed

    @property
    def executor(self) -> Executor:
        return self._executor

    def set_package(self, package: ProjectPackage) -> Installer:
        self._package = package

        return self

    def set_locker(self, locker: Locker) -> Installer:
        self._locker = locker

        return self

    def run(self) -> int:
        # Check if refresh
        if not self._update and self._lock and self._locker.is_locked():
            return self._do_refresh()

        # Force update if there is no lock file present
        if not self._update and not self._locker.is_locked():
            self._update = True

        if self.is_dry_run():
            self.verbose(True)

        return self._do_install()

    def dry_run(self, dry_run: bool = True) -> Installer:
        self._dry_run = dry_run
        self._executor.dry_run(dry_run)

        return self

    def is_dry_run(self) -> bool:
        return self._dry_run

    def requires_synchronization(
        self, requires_synchronization: bool = True
    ) -> Installer:
        self._requires_synchronization = requires_synchronization

        return self

    def verbose(self, verbose: bool = True) -> Installer:
        self._verbose = verbose
        self._executor.verbose(verbose)

        return self

    def is_verbose(self) -> bool:
        return self._verbose

    def only_groups(self, groups: Iterable[str]) -> Installer:
        self._groups = groups

        return self

    def update(self, update: bool = True) -> Installer:
        self._update = update

        return self

    def skip_directory(self, skip_directory: bool = False) -> Installer:
        self._skip_directory = skip_directory

        return self

    def lock(self, update: bool = True) -> Installer:
        """
        Prepare the installer for locking only.
        """
        self.update(update=update)
        self.execute_operations(False)
        self._lock = True

        return self

    def is_updating(self) -> bool:
        return self._update

    def execute_operations(self, execute: bool = True) -> Installer:
        if not execute:
            self._executor.disable()

        return self

    def whitelist(self, packages: Iterable[str]) -> Installer:
        self._whitelist = [canonicalize_name(p) for p in packages]

        return self

    def extras(self, extras: list[str]) -> Installer:
        self._extras = [canonicalize_name(extra) for extra in extras]

        return self

    def _do_refresh(self) -> int:
        from poetry.puzzle.solver import Solver

        # Checking extras
        for extra in self._extras:
            if extra not in self._package.extras:
                raise ValueError(f"Extra [{extra}] is not specified.")

        locked_repository = self._locker.locked_repository()
        solver = Solver(
            self._package,
            self._pool,
            locked_repository.packages,
            locked_repository.packages,
            self._io,
        )

        # Always re-solve directory dependencies, otherwise we can't determine
        # if anything has changed (and the lock file contains an invalid version).
        use_latest = [
            p.name for p in locked_repository.packages if p.source_type == "directory"
        ]

        with solver.provider.use_source_root(
            source_root=self._env.path.joinpath("src")
        ):
            ops = solver.solve(use_latest=use_latest).calculate_operations()

        lockfile_repo = LockfileRepository()
        self._populate_lockfile_repo(lockfile_repo, ops)

        self._write_lock_file(lockfile_repo, force=True)

        return 0

    def _do_install(self) -> int:
        from poetry.puzzle.solver import Solver

        locked_repository = Repository("poetry-locked")
        if self._update:
            if not self._lock and self._locker.is_locked():
                locked_repository = self._locker.locked_repository()

                # If no packages have been whitelisted (The ones we want to update),
                # we whitelist every package in the lock file.
                if not self._whitelist:
                    for pkg in locked_repository.packages:
                        self._whitelist.append(pkg.name)

            # Checking extras
            for extra in self._extras:
                if extra not in self._package.extras:
                    raise ValueError(f"Extra [{extra}] is not specified.")

            self._io.write_line("<info>Updating dependencies</>")
            solver = Solver(
                self._package,
                self._pool,
                self._installed_repository.packages,
                locked_repository.packages,
                self._io,
            )

            with solver.provider.use_source_root(
                source_root=self._env.path.joinpath("src")
            ):
                ops = solver.solve(use_latest=self._whitelist).calculate_operations()
        else:
            self._io.write_line("<info>Installing dependencies from lock file</>")

            locked_repository = self._locker.locked_repository()

            if not self._locker.is_fresh():
                self._io.write_error_line(
                    "<warning>"
                    "Warning: poetry.lock is not consistent with pyproject.toml. "
                    "You may be getting improper dependencies. "
                    "Run `poetry lock [--no-update]` to fix it."
                    "</warning>"
                )

            locker_extras = {
                canonicalize_name(extra)
                for extra in self._locker.lock_data.get("extras", {})
            }
            for extra in self._extras:
                if extra not in locker_extras:
                    raise ValueError(f"Extra [{extra}] is not specified.")

            # If we are installing from lock
            # Filter the operations by comparing it with what is
            # currently installed
            ops = self._get_operations_from_lock(locked_repository)

        lockfile_repo = LockfileRepository()
        self._populate_lockfile_repo(lockfile_repo, ops)

        if not self.executor.enabled:
            # If we are only in lock mode, no need to go any further
            self._write_lock_file(lockfile_repo)
            return 0

        if self._groups is not None:
            root = self._package.with_dependency_groups(list(self._groups), only=True)
        else:
            root = self._package.without_optional_dependency_groups()

        if self._io.is_verbose():
            self._io.write_line("")
            self._io.write_line(
                "<info>Finding the necessary packages for the current system</>"
            )

        # We resolve again by only using the lock file
        pool = RepositoryPool(ignore_repository_names=True, config=self._config)

        # Making a new repo containing the packages
        # newly resolved and the ones from the current lock file
        repo = Repository("poetry-repo")
        for package in lockfile_repo.packages + locked_repository.packages:
            if not package.is_direct_origin() and not repo.has_package(package):
                repo.add_package(package)

        pool.add_repository(repo)

        solver = Solver(
            root,
            pool,
            self._installed_repository.packages,
            locked_repository.packages,
            NullIO(),
        )
        # Everything is resolved at this point, so we no longer need
        # to load deferred dependencies (i.e. VCS, URL and path dependencies)
        solver.provider.load_deferred(False)

        with solver.use_environment(self._env):
            ops = solver.solve(use_latest=self._whitelist).calculate_operations(
                with_uninstalls=self._requires_synchronization,
                synchronize=self._requires_synchronization,
                skip_directory=self._skip_directory,
            )

        if not self._requires_synchronization:
            # If no packages synchronisation has been requested we need
            # to calculate the uninstall operations
            from poetry.puzzle.transaction import Transaction

            transaction = Transaction(
                locked_repository.packages,
                [(package, 0) for package in lockfile_repo.packages],
                installed_packages=self._installed_repository.packages,
                root_package=root,
            )

            ops = [
                op
                for op in transaction.calculate_operations(with_uninstalls=True)
                if op.job_type == "uninstall"
            ] + ops

        # We need to filter operations so that packages
        # not compatible with the current system,
        # or optional and not requested, are dropped
        self._filter_operations(ops, lockfile_repo)

        # Validate the dependencies
        for op in ops:
            dep = op.package.to_dependency()
            if dep.is_file() or dep.is_directory():
                dep = cast("PathDependency", dep)
                dep.validate(raise_error=True)

        # Execute operations
        status = self._execute(ops)

        if status == 0 and self._update:
            # Only write lock file when installation is success
            self._write_lock_file(lockfile_repo)

        return status

    def _write_lock_file(self, repo: LockfileRepository, force: bool = False) -> None:
        if not self.is_dry_run() and (force or self._update):
            updated_lock = self._locker.set_lock_data(self._package, repo.packages)

            if updated_lock:
                self._io.write_line("")
                self._io.write_line("<info>Writing lock file</>")

    def _execute(self, operations: list[Operation]) -> int:
        return self._executor.execute(operations)

    def _populate_lockfile_repo(
        self, repo: LockfileRepository, ops: Iterable[Operation]
    ) -> None:
        for op in ops:
            if isinstance(op, Uninstall):
                continue
            elif isinstance(op, Update):
                package = op.target_package
            else:
                package = op.package

            if not repo.has_package(package):
                repo.add_package(package)

    def _get_operations_from_lock(
        self, locked_repository: Repository
    ) -> list[Operation]:
        installed_repo = self._installed_repository
        ops: list[Operation] = []

        extra_packages = self._get_extra_packages(locked_repository)
        for locked in locked_repository.packages:
            is_installed = False
            for installed in installed_repo.packages:
                if locked.name == installed.name:
                    is_installed = True
                    if locked.optional and locked.name not in extra_packages:
                        # Installed but optional and not requested in extras
                        ops.append(Uninstall(locked))
                    elif locked.version != installed.version:
                        ops.append(Update(installed, locked))

            # If it's optional and not in required extras
            # we do not install
            if locked.optional and locked.name not in extra_packages:
                continue

            op = Install(locked)
            if is_installed:
                op.skip("Already installed")

            ops.append(op)

        return ops

    def _filter_operations(self, ops: Iterable[Operation], repo: Repository) -> None:
        extra_packages = self._get_extra_packages(repo)
        for op in ops:
            package = op.target_package if isinstance(op, Update) else op.package

            if op.job_type == "uninstall":
                continue

            if not self._env.is_valid_for_marker(package.marker):
                op.skip("Not needed for the current environment")
                continue

            # If a package is optional and not requested
            # in any extra we skip it
            if package.optional and package.name not in extra_packages:
                op.skip("Not required")

    def _get_extra_packages(self, repo: Repository) -> set[NormalizedName]:
        """
        Returns all package names required by extras.

        Maybe we just let the solver handle it?
        """
        extras: dict[NormalizedName, list[NormalizedName]]
        if self._update:
            extras = {k: [d.name for d in v] for k, v in self._package.extras.items()}
        else:
            raw_extras = self._locker.lock_data.get("extras", {})
            extras = {
                canonicalize_name(extra): [
                    canonicalize_name(dependency) for dependency in dependencies
                ]
                for extra, dependencies in raw_extras.items()
            }

        return get_extra_package_names(repo.packages, extras, self._extras)

    def _get_installed(self) -> InstalledRepository:
        return InstalledRepository.load(self._env)
