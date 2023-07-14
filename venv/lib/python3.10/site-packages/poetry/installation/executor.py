# -*- coding: utf-8 -*-
from __future__ import division

import itertools
import os
import threading

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from subprocess import CalledProcessError

from poetry.core.packages.file_dependency import FileDependency
from poetry.core.packages.utils.link import Link
from poetry.core.packages.utils.utils import url_to_path
from poetry.core.pyproject.toml import PyProjectTOML
from poetry.io.null_io import NullIO
from poetry.utils._compat import PY2
from poetry.utils._compat import WINDOWS
from poetry.utils._compat import OrderedDict
from poetry.utils._compat import Path
from poetry.utils._compat import cpu_count
from poetry.utils._compat import decode
from poetry.utils.env import EnvCommandError
from poetry.utils.helpers import safe_rmtree

from .authenticator import Authenticator
from .chef import Chef
from .chooser import Chooser
from .operations.install import Install
from .operations.operation import Operation
from .operations.uninstall import Uninstall
from .operations.update import Update


class Executor(object):
    def __init__(self, env, pool, config, io, parallel=None):
        self._env = env
        self._io = io
        self._dry_run = False
        self._enabled = True
        self._verbose = False
        self._authenticator = Authenticator(config, self._io)
        self._chef = Chef(config, self._env)
        self._chooser = Chooser(pool, self._env)

        if parallel is None:
            parallel = config.get("installer.parallel", True)

        if parallel and not (PY2 and WINDOWS):
            # This should be directly handled by ThreadPoolExecutor
            # however, on some systems the number of CPUs cannot be determined
            # (it raises a NotImplementedError), so, in this case, we assume
            # that the system only has one CPU.
            try:
                self._max_workers = cpu_count() + 4
            except NotImplementedError:
                self._max_workers = 5
        else:
            self._max_workers = 1

        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._total_operations = 0
        self._executed_operations = 0
        self._executed = {"install": 0, "update": 0, "uninstall": 0}
        self._skipped = {"install": 0, "update": 0, "uninstall": 0}
        self._sections = OrderedDict()
        self._lock = threading.Lock()
        self._shutdown = False

    @property
    def installations_count(self):  # type: () -> int
        return self._executed["install"]

    @property
    def updates_count(self):  # type: () -> int
        return self._executed["update"]

    @property
    def removals_count(self):  # type: () -> int
        return self._executed["uninstall"]

    def supports_fancy_output(self):  # type: () -> bool
        return self._io.supports_ansi() and not self._dry_run

    def disable(self):
        self._enabled = False

        return self

    def dry_run(self, dry_run=True):
        self._dry_run = dry_run

        return self

    def verbose(self, verbose=True):
        self._verbose = verbose

        return self

    def execute(self, operations):  # type: (Operation) -> int
        self._total_operations = len(operations)
        for job_type in self._executed:
            self._executed[job_type] = 0
            self._skipped[job_type] = 0

        if operations and (self._enabled or self._dry_run):
            self._display_summary(operations)

        # We group operations by priority
        groups = itertools.groupby(operations, key=lambda o: -o.priority)
        self._sections = OrderedDict()
        for _, group in groups:
            tasks = []
            serial_operations = []
            for operation in group:
                if self._shutdown:
                    break

                # Some operations are unsafe, we mus execute them serially in a group
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

        return 1 if self._shutdown else 0

    def _write(self, operation, line):
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
            section.output.clear()
            section.write(line)

    def _execute_operation(self, operation):
        try:
            if self.supports_fancy_output():
                if id(operation) not in self._sections:
                    if self._should_write_operation(operation):
                        with self._lock:
                            self._sections[id(operation)] = self._io.section()
                            self._sections[id(operation)].write_line(
                                "  <fg=blue;options=bold>•</> {message}: <fg=blue>Pending...</>".format(
                                    message=self.get_operation_message(operation),
                                ),
                            )
            else:
                if self._should_write_operation(operation):
                    if not operation.skipped:
                        self._io.write_line(
                            "  <fg=blue;options=bold>•</> {message}".format(
                                message=self.get_operation_message(operation),
                            ),
                        )
                    else:
                        self._io.write_line(
                            "  <fg=default;options=bold,dark>•</> {message}: "
                            "<fg=default;options=bold,dark>Skipped</> "
                            "<fg=default;options=dark>for the following reason:</> "
                            "<fg=default;options=bold,dark>{reason}</>".format(
                                message=self.get_operation_message(operation),
                                reason=operation.skip_reason,
                            )
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
                from clikit.ui.components.exception_trace import ExceptionTrace

                if not self.supports_fancy_output():
                    io = self._io
                else:
                    message = "  <error>•</error> {message}: <error>Failed</error>".format(
                        message=self.get_operation_message(operation, error=True),
                    )
                    self._write(operation, message)
                    io = self._sections.get(id(operation), self._io)

                with self._lock:
                    trace = ExceptionTrace(e)
                    trace.render(io)
                    io.write_line("")
            finally:
                with self._lock:
                    self._shutdown = True
        except KeyboardInterrupt:
            try:
                message = "  <warning>•</warning> {message}: <warning>Cancelled</warning>".format(
                    message=self.get_operation_message(operation, warning=True),
                )
                if not self.supports_fancy_output():
                    self._io.write_line(message)
                else:
                    self._write(operation, message)
            finally:
                with self._lock:
                    self._shutdown = True

    def _do_execute_operation(self, operation):
        method = operation.job_type

        operation_message = self.get_operation_message(operation)
        if operation.skipped:
            if self.supports_fancy_output():
                self._write(
                    operation,
                    "  <fg=default;options=bold,dark>•</> {message}: "
                    "<fg=default;options=bold,dark>Skipped</> "
                    "<fg=default;options=dark>for the following reason:</> "
                    "<fg=default;options=bold,dark>{reason}</>".format(
                        message=operation_message, reason=operation.skip_reason,
                    ),
                )

            self._skipped[operation.job_type] += 1

            return 0

        if not self._enabled or self._dry_run:
            self._io.write_line(
                "  <fg=blue;options=bold>•</> {message}".format(
                    message=operation_message,
                )
            )

            return 0

        result = getattr(self, "_execute_{}".format(method))(operation)

        if result != 0:
            return result

        message = "  <fg=green;options=bold>•</> {message}".format(
            message=self.get_operation_message(operation, done=True),
        )
        self._write(operation, message)

        self._increment_operations_count(operation, True)

        return result

    def _increment_operations_count(self, operation, executed):
        with self._lock:
            if executed:
                self._executed_operations += 1
                self._executed[operation.job_type] += 1
            else:
                self._skipped[operation.job_type] += 1

    def run_pip(self, *args, **kwargs):  # type: (...) -> int
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

    def get_operation_message(self, operation, done=False, error=False, warning=False):
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

        if operation.job_type == "install":
            return "<{}>Installing <{}>{}</{}> (<{}>{}</>)</>".format(
                base_tag,
                package_color,
                operation.package.name,
                package_color,
                operation_color,
                operation.package.full_pretty_version,
            )

        if operation.job_type == "uninstall":
            return "<{}>Removing <{}>{}</{}> (<{}>{}</>)</>".format(
                base_tag,
                package_color,
                operation.package.name,
                package_color,
                operation_color,
                operation.package.full_pretty_version,
            )

        if operation.job_type == "update":
            return "<{}>Updating <{}>{}</{}> (<{}>{}</{}> -> <{}>{}</>)</>".format(
                base_tag,
                package_color,
                operation.initial_package.name,
                package_color,
                source_operation_color,
                operation.initial_package.full_pretty_version,
                source_operation_color,
                operation_color,
                operation.target_package.full_pretty_version,
            )

        return ""

    def _display_summary(self, operations):
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
        self._io.write_line(
            "<b>Package operations</b>: "
            "<info>{}</> install{}, "
            "<info>{}</> update{}, "
            "<info>{}</> removal{}"
            "{}".format(
                installs,
                "" if installs == 1 else "s",
                updates,
                "" if updates == 1 else "s",
                uninstalls,
                "" if uninstalls == 1 else "s",
                ", <info>{}</> skipped".format(skipped)
                if skipped and self._verbose
                else "",
            )
        )
        self._io.write_line("")

    def _execute_install(self, operation):  # type: (Install) -> None
        return self._install(operation)

    def _execute_update(self, operation):  # type: (Update) -> None
        return self._update(operation)

    def _execute_uninstall(self, operation):  # type: (Uninstall) -> None
        message = "  <fg=blue;options=bold>•</> {message}: <info>Removing...</info>".format(
            message=self.get_operation_message(operation),
        )
        self._write(operation, message)

        return self._remove(operation)

    def _install(self, operation):
        package = operation.package
        if package.source_type == "directory":
            return self._install_directory(operation)

        if package.source_type == "git":
            return self._install_git(operation)

        if package.source_type == "file":
            archive = self._prepare_file(operation)
        elif package.source_type == "url":
            # archive = self._download_link(operation, Link(package.source_url))
            return self._pip_install(operation, package.source_url)
        else:
            # archive = self._download(operation)
            url = str(self._chooser.choose_for(package))
            return self._pip_install(operation, url)

        operation_message = self.get_operation_message(operation)
        message = "  <fg=blue;options=bold>•</> {message}: <info>Installing...</info>".format(
            message=operation_message,
        )
        self._write(operation, message)

        args = ["install", "--no-deps", str(archive)]
        if operation.job_type == "update":
            args.insert(2, "-U")

        return self.run_pip(*args)

    def _pip_install(self, operation, spec):
        operation_message = self.get_operation_message(operation)
        message = "  <fg=blue;options=bold>•</> {message}: <info>Installing...</info>".format(
            message=operation_message,
        )
        self._write(operation, message)

        args = ["install", "--no-deps", spec]

        return self.run_pip(*args)

    def _update(self, operation):
        return self._install(operation)

    def _remove(self, operation):
        package = operation.package

        # If we have a VCS package, remove its source directory
        if package.source_type == "git":
            src_dir = self._env.path / "src" / package.name
            if src_dir.exists():
                safe_rmtree(str(src_dir))

        try:
            return self.run_pip("uninstall", package.name, "-y")
        except CalledProcessError as e:
            if "not installed" in str(e):
                return 0

            raise

    def _prepare_file(self, operation):
        package = operation.package

        message = "  <fg=blue;options=bold>•</> {message}: <info>Preparing...</info>".format(
            message=self.get_operation_message(operation),
        )
        self._write(operation, message)

        archive = Path(package.source_url)
        if not Path(package.source_url).is_absolute() and package.root_dir:
            archive = package.root_dir / archive

        archive = self._chef.prepare(archive)

        return archive

    def _install_directory(self, operation):
        from poetry.factory import Factory

        package = operation.package
        operation_message = self.get_operation_message(operation)

        message = "  <fg=blue;options=bold>•</> {message}: <info>Building...</info>".format(
            message=operation_message,
        )
        self._write(operation, message)

        if package.root_dir:
            req = os.path.join(str(package.root_dir), package.source_url)
        else:
            req = os.path.realpath(package.source_url)

        args = ["install", "--no-deps", "-U"]

        pyproject = PyProjectTOML(os.path.join(req, "pyproject.toml"))

        if pyproject.is_poetry_project():
            # Even if there is a build system specified
            # some versions of pip (< 19.0.0) don't understand it
            # so we need to check the version of pip to know
            # if we can rely on the build system
            legacy_pip = self._env.pip_version < self._env.pip_version.__class__(
                19, 0, 0
            )
            package_poetry = Factory().create_poetry(pyproject.file.path.parent)

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
                    if package.develop:
                        args.append("-e")

                    args.append(req)

                    return self.run_pip(*args)

        if package.develop:
            args.append("-e")

        args.append(req)

        return self.run_pip(*args)

    def _install_git(self, operation):
        from poetry.core.vcs import Git

        package = operation.package
        operation_message = self.get_operation_message(operation)

        message = "  <fg=blue;options=bold>•</> {message}: <info>Cloning...</info>".format(
            message=operation_message,
        )
        self._write(operation, message)

        src_dir = self._env.path / "src" / package.name
        if src_dir.exists():
            safe_rmtree(str(src_dir))

        src_dir.parent.mkdir(exist_ok=True)

        git = Git()
        git.clone(package.source_url, src_dir)

        reference = package.source_resolved_reference
        if not reference:
            reference = package.source_reference

        git.checkout(reference, src_dir)

        # Now we just need to install from the source directory
        package._source_url = str(src_dir)

        return self._install_directory(operation)

    def _download(self, operation):  # type: (Operation) -> Path
        link = self._chooser.choose_for(operation.package)

        return self._download_link(operation, link)

    def _download_link(self, operation, link):
        package = operation.package

        archive = self._chef.get_cached_archive_for_link(link)
        if archive is link:
            # No cached distributions was found, so we download and prepare it
            try:
                archive = self._download_archive(operation, link)
            except BaseException:
                cache_directory = self._chef.get_cache_directory_for_link(link)
                cached_file = cache_directory.joinpath(link.filename)
                # We can't use unlink(missing_ok=True) because it's not available
                # in pathlib2 for Python 2.7
                if cached_file.exists():
                    cached_file.unlink()

                raise

            # TODO: Check readability of the created archive

            if not link.is_wheel:
                archive = self._chef.prepare(archive)

        if package.files:
            hashes = {f["hash"] for f in package.files}
            hash_types = {h.split(":")[0] for h in hashes}
            archive_hashes = set()
            archive_path = (
                url_to_path(archive.url) if isinstance(archive, Link) else archive
            )
            for hash_type in hash_types:
                archive_hashes.add(
                    "{}:{}".format(
                        hash_type,
                        FileDependency(package.name, archive_path).hash(hash_type),
                    )
                )

            if archive_hashes.isdisjoint(hashes):
                raise RuntimeError(
                    "Invalid hashes ({}) for {} using archive {}. Expected one of {}.".format(
                        ", ".join(sorted(archive_hashes)),
                        package,
                        archive_path.name,
                        ", ".join(sorted(hashes)),
                    )
                )

        return archive

    def _download_archive(self, operation, link):  # type: (Operation, Link) -> Path
        response = self._authenticator.request(
            "get", link.url, stream=True, io=self._sections.get(id(operation), self._io)
        )
        wheel_size = response.headers.get("content-length")
        operation_message = self.get_operation_message(operation)
        message = "  <fg=blue;options=bold>•</> {message}: <info>Downloading...</>".format(
            message=operation_message,
        )
        progress = None
        if self.supports_fancy_output():
            if wheel_size is None:
                self._write(operation, message)
            else:
                from clikit.ui.components.progress_bar import ProgressBar

                progress = ProgressBar(
                    self._sections[id(operation)].output, max=int(wheel_size)
                )
                progress.set_format(message + " <b>%percent%%</b>")

        if progress:
            with self._lock:
                progress.start()

        done = 0
        archive = self._chef.get_cache_directory_for_link(link) / link.filename
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("wb") as f:
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

    def _should_write_operation(self, operation):  # type: (Operation) -> bool
        if not operation.skipped:
            return True

        return self._dry_run or self._verbose
