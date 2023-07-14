from __future__ import annotations

import contextlib
import csv
import itertools
import json
import os
import threading

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING
from typing import Any

from cleo.io.null_io import NullIO
from poetry.core.packages.utils.link import Link

from poetry.installation.chef import Chef
from poetry.installation.chef import ChefBuildError
from poetry.installation.chooser import Chooser
from poetry.installation.operations import Install
from poetry.installation.operations import Uninstall
from poetry.installation.operations import Update
from poetry.installation.wheel_installer import WheelInstaller
from poetry.puzzle.exceptions import SolverProblemError
from poetry.utils._compat import decode
from poetry.utils.authenticator import Authenticator
from poetry.utils.cache import ArtifactCache
from poetry.utils.env import EnvCommandError
from poetry.utils.helpers import atomic_open
from poetry.utils.helpers import get_file_hash
from poetry.utils.helpers import pluralize
from poetry.utils.helpers import remove_directory
from poetry.utils.pip import pip_install


if TYPE_CHECKING:
    from cleo.io.io import IO
    from cleo.io.outputs.section_output import SectionOutput
    from poetry.core.masonry.builders.builder import Builder
    from poetry.core.packages.package import Package

    from poetry.config.config import Config
    from poetry.installation.operations.operation import Operation
    from poetry.repositories import RepositoryPool
    from poetry.utils.env import Env


class Executor:
    def __init__(
        self,
        env: Env,
        pool: RepositoryPool,
        config: Config,
        io: IO,
        parallel: bool | None = None,
        disable_cache: bool = False,
    ) -> None:
        self._env = env
        self._io = io
        self._dry_run = False
        self._enabled = True
        self._verbose = False
        self._wheel_installer = WheelInstaller(self._env)
        self._use_modern_installation = config.get(
            "installer.modern-installation", True
        )

        if parallel is None:
            parallel = config.get("installer.parallel", True)

        if parallel:
            self._max_workers = self._get_max_workers(
                desired_max_workers=config.get("installer.max-workers")
            )
        else:
            self._max_workers = 1

        self._artifact_cache = ArtifactCache(cache_dir=config.artifacts_cache_directory)
        self._authenticator = Authenticator(
            config, self._io, disable_cache=disable_cache, pool_size=self._max_workers
        )
        self._chef = Chef(self._artifact_cache, self._env, pool)
        self._chooser = Chooser(pool, self._env, config)

        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._total_operations = 0
        self._executed_operations = 0
        self._executed = {"install": 0, "update": 0, "uninstall": 0}
        self._skipped = {"install": 0, "update": 0, "uninstall": 0}
        self._sections: dict[int, SectionOutput] = {}
        self._yanked_warnings: list[str] = []
        self._lock = threading.Lock()
        self._shutdown = False
        self._hashes: dict[str, str] = {}

    @property
    def installations_count(self) -> int:
        return self._executed["install"]

    @property
    def updates_count(self) -> int:
        return self._executed["update"]

    @property
    def removals_count(self) -> int:
        return self._executed["uninstall"]

    @property
    def enabled(self) -> bool:
        return self._enabled

    def supports_fancy_output(self) -> bool:
        return self._io.output.is_decorated() and not self._dry_run

    def disable(self) -> Executor:
        self._enabled = False

        return self

    def dry_run(self, dry_run: bool = True) -> Executor:
        self._dry_run = dry_run

        return self

    def verbose(self, verbose: bool = True) -> Executor:
        self._verbose = verbose

        return self

    def enable_bytecode_compilation(self, enable: bool = True) -> None:
        self._wheel_installer.enable_bytecode_compilation(enable)

    def pip_install(
        self, req: Path, upgrade: bool = False, editable: bool = False
    ) -> int:
        try:
            pip_install(req, self._env, upgrade=upgrade, editable=editable)
        except EnvCommandError as e:
            output = decode(e.e.output)
            if (
                "KeyboardInterrupt" in output
                or "ERROR: Operation cancelled by user" in output
            ):
                return -2
            raise

        return 0

    def execute(self, operations: list[Operation]) -> int:
        self._total_operations = len(operations)
        for job_type in self._executed:
            self._executed[job_type] = 0
            self._skipped[job_type] = 0

        if operations and (self._enabled or self._dry_run):
            self._display_summary(operations)

        self._sections = {}
        self._yanked_warnings = []

        # pip has to be installed first without parallelism if we install via pip
        for i, op in enumerate(operations):
            if op.package.name == "pip":
                wait([self._executor.submit(self._execute_operation, op)])
                del operations[i]
                break

        # We group operations by priority
        groups = itertools.groupby(operations, key=lambda o: -o.priority)
        for _, group in groups:
            tasks = []
            serial_operations = []
            for operation in group:
                if self._shutdown:
                    break

                # Some operations are unsafe, we must execute them serially in a group
                # https://github.com/python-poetry/poetry/issues/3086
                # https://github.com/python-poetry/poetry/issues/2658
                #
                # We need to explicitly check source type here, see:
                # https://github.com/python-poetry/poetry-core/pull/98
                is_parallel_unsafe = operation.job_type == "uninstall" or (
                    operation.package.develop
                    and operation.package.source_type in {"directory", "git"}
                )
                if not operation.skipped and is_parallel_unsafe:
                    serial_operations.append(operation)
                    continue

                tasks.append(self._executor.submit(self._execute_operation, operation))

            try:
                wait(tasks)

                for operation in serial_operations:
                    wait([self._executor.submit(self._execute_operation, operation)])

            except KeyboardInterrupt:
                self._shutdown = True

            if self._shutdown:
                # Cancelling further tasks from being executed
                [task.cancel() for task in tasks]
                self._executor.shutdown(wait=True)

                break

        for warning in self._yanked_warnings:
            self._io.write_error_line(f"<warning>Warning: {warning}</warning>")
        for path, issues in self._wheel_installer.invalid_wheels.items():
            formatted_issues = "\n".join(issues)
            warning = (
                f"Validation of the RECORD file of {path.name} failed."
                " Please report to the maintainers of that package so they can fix"
                f" their build process. Details:\n{formatted_issues}\n"
            )
            self._io.write_error_line(f"<warning>Warning: {warning}</warning>")

        return 1 if self._shutdown else 0

    @staticmethod
    def _get_max_workers(desired_max_workers: int | None = None) -> int:
        # This should be directly handled by ThreadPoolExecutor
        # however, on some systems the number of CPUs cannot be determined
        # (it raises a NotImplementedError), so, in this case, we assume
        # that the system only has one CPU.
        try:
            default_max_workers = (os.cpu_count() or 1) + 4
        except NotImplementedError:
            default_max_workers = 5

        if desired_max_workers is None:
            return default_max_workers
        return min(default_max_workers, desired_max_workers)

    def _write(self, operation: Operation, line: str) -> None:
        if not self.supports_fancy_output() or not self._should_write_operation(
            operation
        ):
            return

        if self._io.is_debug():
            with self._lock:
                section = self._sections[id(operation)]
                section.write_line(line)

            return

        with self._lock:
            section = self._sections[id(operation)]
            section.clear()
            section.write(line)

    def _execute_operation(self, operation: Operation) -> None:
        try:
            op_message = self.get_operation_message(operation)
            if self.supports_fancy_output():
                if id(operation) not in self._sections and self._should_write_operation(
                    operation
                ):
                    with self._lock:
                        self._sections[id(operation)] = self._io.section()
                        self._sections[id(operation)].write_line(
                            f"  <fg=blue;options=bold>•</> {op_message}:"
                            " <fg=blue>Pending...</>"
                        )
            else:
                if self._should_write_operation(operation):
                    if not operation.skipped:
                        self._io.write_line(
                            f"  <fg=blue;options=bold>•</> {op_message}"
                        )
                    else:
                        self._io.write_line(
                            f"  <fg=default;options=bold,dark>•</> {op_message}: "
                            "<fg=default;options=bold,dark>Skipped</> "
                            "<fg=default;options=dark>for the following reason:</> "
                            f"<fg=default;options=bold,dark>{operation.skip_reason}</>"
                        )

            try:
                result = self._do_execute_operation(operation)
            except EnvCommandError as e:
                if e.e.returncode == -2:
                    result = -2
                else:
                    raise

            # If we have a result of -2 it means a KeyboardInterrupt
            # in the any python subprocess, so we raise a KeyboardInterrupt
            # error to be picked up by the error handler.
            if result == -2:
                raise KeyboardInterrupt
        except Exception as e:
            try:
                from cleo.ui.exception_trace import ExceptionTrace

                io: IO | SectionOutput
                if not self.supports_fancy_output():
                    io = self._io
                else:
                    message = (
                        "  <error>•</error>"
                        f" {self.get_operation_message(operation, error=True)}:"
                        " <error>Failed</error>"
                    )
                    self._write(operation, message)
                    io = self._sections.get(id(operation), self._io)

                with self._lock:
                    trace = ExceptionTrace(e)
                    trace.render(io)
                    if isinstance(e, ChefBuildError):
                        pkg = operation.package
                        pip_command = "pip wheel --use-pep517"
                        if pkg.develop:
                            requirement = pkg.source_url
                            pip_command += " --editable"
                        else:
                            requirement = (
                                pkg.to_dependency().to_pep_508().split(";")[0].strip()
                            )
                        io.write_line("")
                        io.write_line(
                            "<info>"
                            "Note: This error originates from the build backend,"
                            " and is likely not a problem with poetry"
                            f" but with {pkg.pretty_name} ({pkg.full_pretty_version})"
                            " not supporting PEP 517 builds. You can verify this by"
                            f" running '{pip_command} \"{requirement}\"'."
                            "</info>"
                        )
                    elif isinstance(e, SolverProblemError):
                        pkg = operation.package
                        io.write_line("")
                        io.write_line(
                            "<error>"
                            "Cannot resolve build-system.requires"
                            f" for {pkg.pretty_name}."
                            "</error>"
                        )
                    io.write_line("")
            finally:
                with self._lock:
                    self._shutdown = True
        except KeyboardInterrupt:
            try:
                message = (
                    "  <warning>•</warning>"
                    f" {self.get_operation_message(operation, warning=True)}:"
                    " <warning>Cancelled</warning>"
                )
                if not self.supports_fancy_output():
                    self._io.write_line(message)
                else:
                    self._write(operation, message)
            finally:
                with self._lock:
                    self._shutdown = True

    def _do_execute_operation(self, operation: Operation) -> int:
        method = operation.job_type

        operation_message = self.get_operation_message(operation)
        if operation.skipped:
            if self.supports_fancy_output():
                self._write(
                    operation,
                    (
                        f"  <fg=default;options=bold,dark>•</> {operation_message}: "
                        "<fg=default;options=bold,dark>Skipped</> "
                        "<fg=default;options=dark>for the following reason:</> "
                        f"<fg=default;options=bold,dark>{operation.skip_reason}</>"
                    ),
                )

            self._skipped[operation.job_type] += 1

            return 0

        if not self._enabled or self._dry_run:
            return 0

        result: int = getattr(self, f"_execute_{method}")(operation)

        if result != 0:
            return result

        operation_message = self.get_operation_message(operation, done=True)
        message = f"  <fg=green;options=bold>•</> {operation_message}"
        self._write(operation, message)

        self._increment_operations_count(operation, True)

        return result

    def _increment_operations_count(self, operation: Operation, executed: bool) -> None:
        with self._lock:
            if executed:
                self._executed_operations += 1
                self._executed[operation.job_type] += 1
            else:
                self._skipped[operation.job_type] += 1

    def run_pip(self, *args: Any, **kwargs: Any) -> int:
        try:
            self._env.run_pip(*args, **kwargs)
        except EnvCommandError as e:
            output = decode(e.e.output)
            if (
                "KeyboardInterrupt" in output
                or "ERROR: Operation cancelled by user" in output
            ):
                return -2

            raise

        return 0

    def get_operation_message(
        self,
        operation: Operation,
        done: bool = False,
        error: bool = False,
        warning: bool = False,
    ) -> str:
        base_tag = "fg=default"
        operation_color = "c2"
        source_operation_color = "c2"
        package_color = "c1"

        if error:
            operation_color = "error"
        elif warning:
            operation_color = "warning"
        elif done:
            operation_color = "success"

        if operation.skipped:
            base_tag = "fg=default;options=dark"
            operation_color += "_dark"
            source_operation_color += "_dark"
            package_color += "_dark"

        if isinstance(operation, Install):
            return (
                f"<{base_tag}>Installing"
                f" <{package_color}>{operation.package.name}</{package_color}>"
                f" (<{operation_color}>{operation.package.full_pretty_version}</>)</>"
            )

        if isinstance(operation, Uninstall):
            return (
                f"<{base_tag}>Removing"
                f" <{package_color}>{operation.package.name}</{package_color}>"
                f" (<{operation_color}>{operation.package.full_pretty_version}</>)</>"
            )

        if isinstance(operation, Update):
            return (
                f"<{base_tag}>Updating"
                f" <{package_color}>{operation.initial_package.name}</{package_color}> "
                f"(<{source_operation_color}>"
                f"{operation.initial_package.full_pretty_version}"
                f"</{source_operation_color}> -> <{operation_color}>"
                f"{operation.target_package.full_pretty_version}</>)</>"
            )
        return ""

    def _display_summary(self, operations: list[Operation]) -> None:
        installs = 0
        updates = 0
        uninstalls = 0
        skipped = 0
        for op in operations:
            if op.skipped:
                skipped += 1
                continue

            if op.job_type == "install":
                installs += 1
            elif op.job_type == "update":
                updates += 1
            elif op.job_type == "uninstall":
                uninstalls += 1

        if not installs and not updates and not uninstalls and not self._verbose:
            self._io.write_line("")
            self._io.write_line("No dependencies to install or update")

            return

        self._io.write_line("")
        self._io.write("<b>Package operations</b>: ")
        self._io.write(f"<info>{installs}</> install{pluralize(installs)}, ")
        self._io.write(f"<info>{updates}</> update{pluralize(updates)}, ")
        self._io.write(f"<info>{uninstalls}</> removal{pluralize(uninstalls)}")
        if skipped and self._verbose:
            self._io.write(f", <info>{skipped}</> skipped")
        self._io.write_line("")
        self._io.write_line("")

    def _execute_install(self, operation: Install | Update) -> int:
        status_code = self._install(operation)

        self._save_url_reference(operation)

        return status_code

    def _execute_update(self, operation: Install | Update) -> int:
        status_code = self._update(operation)

        self._save_url_reference(operation)

        return status_code

    def _execute_uninstall(self, operation: Uninstall) -> int:
        op_msg = self.get_operation_message(operation)
        message = f"  <fg=blue;options=bold>•</> {op_msg}: <info>Removing...</info>"
        self._write(operation, message)

        return self._remove(operation.package)

    def _install(self, operation: Install | Update) -> int:
        package = operation.package
        if package.source_type == "directory" and not self._use_modern_installation:
            return self._install_directory_without_wheel_installer(operation)

        cleanup_archive: bool = False
        if package.source_type == "git":
            archive = self._prepare_git_archive(operation)
            cleanup_archive = operation.package.develop
        elif package.source_type == "file":
            archive = self._prepare_archive(operation)
        elif package.source_type == "directory":
            archive = self._prepare_archive(operation)
            cleanup_archive = True
        elif package.source_type == "url":
            assert package.source_url is not None
            archive = self._download_link(operation, Link(package.source_url))
        else:
            archive = self._download(operation)

        operation_message = self.get_operation_message(operation)
        message = (
            f"  <fg=blue;options=bold>•</> {operation_message}:"
            " <info>Installing...</info>"
        )
        self._write(operation, message)

        if not self._use_modern_installation:
            return self.pip_install(archive, upgrade=operation.job_type == "update")

        try:
            if operation.job_type == "update":
                # Uninstall first
                # TODO: Make an uninstaller and find a way to rollback in case
                # the new package can't be installed
                assert isinstance(operation, Update)
                self._remove(operation.initial_package)

            self._wheel_installer.install(archive)
        finally:
            if cleanup_archive:
                archive.unlink()

        return 0

    def _update(self, operation: Install | Update) -> int:
        return self._install(operation)

    def _remove(self, package: Package) -> int:
        # If we have a VCS package, remove its source directory
        if package.source_type == "git":
            src_dir = self._env.path / "src" / package.name
            if src_dir.exists():
                remove_directory(src_dir, force=True)

        try:
            return self.run_pip("uninstall", package.name, "-y")
        except CalledProcessError as e:
            if "not installed" in str(e):
                return 0

            raise

    def _prepare_archive(
        self, operation: Install | Update, *, output_dir: Path | None = None
    ) -> Path:
        package = operation.package
        operation_message = self.get_operation_message(operation)

        message = (
            f"  <fg=blue;options=bold>•</> {operation_message}:"
            " <info>Preparing...</info>"
        )
        self._write(operation, message)

        assert package.source_url is not None
        archive = Path(package.source_url)
        if package.source_subdirectory:
            archive = archive / package.source_subdirectory
        if not Path(package.source_url).is_absolute() and package.root_dir:
            archive = package.root_dir / archive

        self._populate_hashes_dict(archive, package)

        return self._chef.prepare(
            archive, editable=package.develop, output_dir=output_dir
        )

    def _prepare_git_archive(self, operation: Install | Update) -> Path:
        from poetry.vcs.git import Git

        package = operation.package
        assert package.source_url is not None

        if package.source_resolved_reference and not package.develop:
            # Only cache git archives when we know precise reference hash,
            # otherwise we might get stale archives
            cached_archive = self._artifact_cache.get_cached_archive_for_git(
                package.source_url,
                package.source_resolved_reference,
                package.source_subdirectory,
                env=self._env,
            )
            if cached_archive is not None:
                return cached_archive

        operation_message = self.get_operation_message(operation)

        message = (
            f"  <fg=blue;options=bold>•</> {operation_message}: <info>Cloning...</info>"
        )
        self._write(operation, message)

        source = Git.clone(
            url=package.source_url,
            source_root=self._env.path / "src",
            revision=package.source_resolved_reference or package.source_reference,
        )

        # Now we just need to install from the source directory
        original_url = package.source_url
        package._source_url = str(source.path)

        output_dir = None
        if package.source_resolved_reference and not package.develop:
            output_dir = self._artifact_cache.get_cache_directory_for_git(
                original_url,
                package.source_resolved_reference,
                package.source_subdirectory,
            )

        archive = self._prepare_archive(operation, output_dir=output_dir)
        if not package.develop:
            package._source_url = original_url

        if output_dir is not None and output_dir.is_dir():
            # Mark directories with cached git packages, to distinguish from
            # "normal" cache
            (output_dir / ".created_from_git_dependency").touch()

        return archive

    def _install_directory_without_wheel_installer(
        self, operation: Install | Update
    ) -> int:
        from poetry.factory import Factory
        from poetry.pyproject.toml import PyProjectTOML

        package = operation.package
        operation_message = self.get_operation_message(operation)

        message = (
            f"  <fg=blue;options=bold>•</> {operation_message}:"
            " <info>Building...</info>"
        )
        self._write(operation, message)

        assert package.source_url is not None
        if package.root_dir:
            req = package.root_dir / package.source_url
        else:
            req = Path(package.source_url).resolve(strict=False)

        if package.source_subdirectory:
            req /= package.source_subdirectory

        pyproject = PyProjectTOML(req / "pyproject.toml")

        package_poetry = None
        if pyproject.is_poetry_project():
            with contextlib.suppress(RuntimeError):
                package_poetry = Factory().create_poetry(pyproject.file.path.parent)

        if package_poetry is not None:
            # Even if there is a build system specified
            # some versions of pip (< 19.0.0) don't understand it
            # so we need to check the version of pip to know
            # if we can rely on the build system
            legacy_pip = (
                self._env.pip_version
                < self._env.pip_version.__class__.from_parts(19, 0, 0)
            )

            builder: Builder
            if package.develop and not package_poetry.package.build_script:
                from poetry.masonry.builders.editable import EditableBuilder

                # This is a Poetry package in editable mode
                # we can use the EditableBuilder without going through pip
                # to install it, unless it has a build script.
                builder = EditableBuilder(package_poetry, self._env, NullIO())
                builder.build()

                return 0
            elif legacy_pip or package_poetry.package.build_script:
                from poetry.core.masonry.builders.sdist import SdistBuilder

                # We need to rely on creating a temporary setup.py
                # file since the version of pip does not support
                # build-systems
                # We also need it for non-PEP-517 packages
                builder = SdistBuilder(package_poetry)
                with builder.setup_py():
                    return self.pip_install(req, upgrade=True, editable=package.develop)

        return self.pip_install(req, upgrade=True, editable=package.develop)

    def _download(self, operation: Install | Update) -> Path:
        link = self._chooser.choose_for(operation.package)

        if link.yanked:
            # Store yanked warnings in a list and print after installing, so they can't
            # be overlooked. Further, printing them in the concerning section would have
            # the risk of overwriting the warning, so it is only briefly visible.
            message = (
                f"The file chosen for install of {operation.package.pretty_name} "
                f"{operation.package.pretty_version} ({link.show_url}) is yanked."
            )
            if link.yanked_reason:
                message += f" Reason for being yanked: {link.yanked_reason}"
            self._yanked_warnings.append(message)

        return self._download_link(operation, link)

    def _download_link(self, operation: Install | Update, link: Link) -> Path:
        package = operation.package

        output_dir = self._artifact_cache.get_cache_directory_for_link(link)
        # Try to get cached original package for the link provided
        original_archive = self._artifact_cache.get_cached_archive_for_link(
            link, strict=True
        )
        if original_archive is None:
            # No cached original distributions was found, so we download and prepare it
            try:
                original_archive = self._download_archive(operation, link)
            except BaseException:
                cache_directory = self._artifact_cache.get_cache_directory_for_link(
                    link
                )
                cached_file = cache_directory.joinpath(link.filename)
                # We can't use unlink(missing_ok=True) because it's not available
                # prior to Python 3.8
                if cached_file.exists():
                    cached_file.unlink()

                raise

        # Get potential higher prioritized cached archive, otherwise it will fall back
        # to the original archive.
        archive = self._artifact_cache.get_cached_archive_for_link(
            link,
            strict=False,
            env=self._env,
        )
        if archive is None:
            # Since we previously downloaded an archive, we now should have
            # something cached that we can use here. The only case in which
            # archive is None is if the original archive is not valid for the
            # current environment.
            raise RuntimeError(
                f"Package {link.url} cannot be installed in the current environment"
                f" {self._env.marker_env}"
            )

        if archive.suffix != ".whl":
            message = (
                f"  <fg=blue;options=bold>•</> {self.get_operation_message(operation)}:"
                " <info>Preparing...</info>"
            )
            self._write(operation, message)

            archive = self._chef.prepare(archive, output_dir=output_dir)

        # Use the original archive to provide the correct hash.
        self._populate_hashes_dict(original_archive, package)

        return archive

    def _populate_hashes_dict(self, archive: Path, package: Package) -> None:
        if package.files and archive.name in {f["file"] for f in package.files}:
            archive_hash = self._validate_archive_hash(archive, package)
            self._hashes[package.name] = archive_hash

    @staticmethod
    def _validate_archive_hash(archive: Path, package: Package) -> str:
        archive_hash: str = "sha256:" + get_file_hash(archive)
        known_hashes = {f["hash"] for f in package.files if f["file"] == archive.name}

        if archive_hash not in known_hashes:
            raise RuntimeError(
                f"Hash for {package} from archive {archive.name} not found in"
                f" known hashes (was: {archive_hash})"
            )

        return archive_hash

    def _download_archive(self, operation: Install | Update, link: Link) -> Path:
        response = self._authenticator.request(
            "get", link.url, stream=True, io=self._sections.get(id(operation), self._io)
        )
        wheel_size = response.headers.get("content-length")
        operation_message = self.get_operation_message(operation)
        message = (
            f"  <fg=blue;options=bold>•</> {operation_message}: <info>Downloading...</>"
        )
        progress = None
        if self.supports_fancy_output():
            if wheel_size is None:
                self._write(operation, message)
            else:
                from cleo.ui.progress_bar import ProgressBar

                progress = ProgressBar(
                    self._sections[id(operation)], max=int(wheel_size)
                )
                progress.set_format(message + " <b>%percent%%</b>")

        if progress:
            with self._lock:
                self._sections[id(operation)].clear()
                progress.start()

        done = 0
        archive = (
            self._artifact_cache.get_cache_directory_for_link(link) / link.filename
        )
        archive.parent.mkdir(parents=True, exist_ok=True)
        with atomic_open(archive) as f:
            for chunk in response.iter_content(chunk_size=4096):
                if not chunk:
                    break

                done += len(chunk)

                if progress:
                    with self._lock:
                        progress.set_progress(done)

                f.write(chunk)

        if progress:
            with self._lock:
                progress.finish()

        return archive

    def _should_write_operation(self, operation: Operation) -> bool:
        return (
            not operation.skipped or self._dry_run or self._verbose or not self._enabled
        )

    def _save_url_reference(self, operation: Operation) -> None:
        """
        Create and store a PEP-610 `direct_url.json` file, if needed.
        """
        if operation.job_type not in {"install", "update"}:
            return

        package = operation.package

        if not package.source_url or package.source_type == "legacy":
            # Since we are installing from our own distribution cache
            # pip will write a `direct_url.json` file pointing to the cache
            # distribution.
            # That's not what we want, so we remove the direct_url.json file,
            # if it exists.
            for (
                direct_url_json
            ) in self._env.site_packages.find_distribution_direct_url_json_files(
                distribution_name=package.name, writable_only=True
            ):
                # We can't use unlink(missing_ok=True) because it's not always available
                if direct_url_json.exists():
                    direct_url_json.unlink()
            return

        url_reference: dict[str, Any] | None = None

        if package.source_type == "git" and not package.develop:
            url_reference = self._create_git_url_reference(package)
        elif package.source_type in ("directory", "git"):
            url_reference = self._create_directory_url_reference(package)
        elif package.source_type == "url":
            url_reference = self._create_url_url_reference(package)
        elif package.source_type == "file":
            url_reference = self._create_file_url_reference(package)

        if url_reference:
            for dist in self._env.site_packages.distributions(
                name=package.name, writable_only=True
            ):
                dist_path = dist._path  # type: ignore[attr-defined]
                assert isinstance(dist_path, Path)
                url = dist_path / "direct_url.json"
                url.write_text(json.dumps(url_reference), encoding="utf-8")

                record = dist_path / "RECORD"
                if record.exists():
                    with record.open(mode="a", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        path = url.relative_to(record.parent.parent)
                        writer.writerow([str(path), "", ""])

    def _create_git_url_reference(self, package: Package) -> dict[str, Any]:
        reference = {
            "url": package.source_url,
            "vcs_info": {
                "vcs": "git",
                "requested_revision": package.source_reference,
                "commit_id": package.source_resolved_reference,
            },
        }
        if package.source_subdirectory:
            reference["subdirectory"] = package.source_subdirectory

        return reference

    def _create_url_url_reference(self, package: Package) -> dict[str, Any]:
        archive_info = self._get_archive_info(package)

        return {"url": package.source_url, "archive_info": archive_info}

    def _create_file_url_reference(self, package: Package) -> dict[str, Any]:
        archive_info = self._get_archive_info(package)

        assert package.source_url is not None
        return {
            "url": Path(package.source_url).as_uri(),
            "archive_info": archive_info,
        }

    def _create_directory_url_reference(self, package: Package) -> dict[str, Any]:
        dir_info = {}

        if package.develop:
            dir_info["editable"] = True

        assert package.source_url is not None
        return {
            "url": Path(package.source_url).as_uri(),
            "dir_info": dir_info,
        }

    def _get_archive_info(self, package: Package) -> dict[str, Any]:
        """
        Create dictionary `archive_info` for file `direct_url.json`.

        Specification: https://packaging.python.org/en/latest/specifications/direct-url
        (it supersedes PEP 610)

        :param package: This must be a poetry package instance.
        """
        archive_info = {}

        if package.name in self._hashes:
            algorithm, value = self._hashes[package.name].split(":")
            archive_info["hashes"] = {algorithm: value}

        return archive_info
