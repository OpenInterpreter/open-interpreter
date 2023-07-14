from __future__ import annotations

import contextlib
import csv
import hashlib
import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from base64 import urlsafe_b64encode
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from typing import TextIO

import packaging.tags

from poetry.core import __version__
from poetry.core.constraints.version import parse_constraint
from poetry.core.masonry.builders.builder import Builder
from poetry.core.masonry.builders.sdist import SdistBuilder
from poetry.core.masonry.utils.helpers import distribution_name
from poetry.core.masonry.utils.helpers import normalize_file_permissions
from poetry.core.masonry.utils.package_include import PackageInclude
from poetry.core.utils.helpers import decode
from poetry.core.utils.helpers import temporary_directory


if TYPE_CHECKING:
    from collections.abc import Iterator

    from packaging.utils import NormalizedName

    from poetry.core.poetry import Poetry

wheel_file_template = """\
Wheel-Version: 1.0
Generator: poetry-core {version}
Root-Is-Purelib: {pure_lib}
Tag: {tag}
"""

logger = logging.getLogger(__name__)


class WheelBuilder(Builder):
    format = "wheel"

    def __init__(
        self,
        poetry: Poetry,
        original: Path | None = None,
        executable: Path | None = None,
        editable: bool = False,
        metadata_directory: Path | None = None,
    ) -> None:
        super().__init__(poetry, executable=executable)

        self._records: list[tuple[str, str, int]] = []
        self._original_path = self._path
        if original:
            self._original_path = original.parent
        self._editable = editable
        self._metadata_directory = metadata_directory

    @classmethod
    def make_in(
        cls,
        poetry: Poetry,
        directory: Path | None = None,
        original: Path | None = None,
        executable: Path | None = None,
        editable: bool = False,
        metadata_directory: Path | None = None,
    ) -> str:
        wb = WheelBuilder(
            poetry,
            original=original,
            executable=executable,
            editable=editable,
            metadata_directory=metadata_directory,
        )
        wb.build(target_dir=directory)

        return wb.wheel_filename

    @classmethod
    def make(cls, poetry: Poetry, executable: Path | None = None) -> None:
        """Build a wheel in the dist/ directory, and optionally upload it."""
        cls.make_in(poetry, executable=executable)

    def build(
        self,
        target_dir: Path | None = None,
    ) -> Path:
        logger.info("Building wheel")

        target_dir = target_dir or self.default_target_dir
        if not target_dir.exists():
            target_dir.mkdir()

        fd, temp_path = tempfile.mkstemp(suffix=".whl")

        st_mode = os.stat(temp_path).st_mode
        new_mode = normalize_file_permissions(st_mode)
        os.chmod(temp_path, new_mode)

        with os.fdopen(fd, "w+b") as fd_file, zipfile.ZipFile(
            fd_file, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            if self._editable:
                self._build(zip_file)
                self._add_pth(zip_file)
            elif self._poetry.package.build_should_generate_setup():
                self._copy_module(zip_file)
                self._build(zip_file)
            else:
                self._build(zip_file)
                self._copy_module(zip_file)

            self._copy_file_scripts(zip_file)

            if self._metadata_directory is None:
                with temporary_directory() as temp_dir:
                    metadata_directory = self.prepare_metadata(Path(temp_dir))
                    self._copy_dist_info(zip_file, metadata_directory)
            else:
                self._copy_dist_info(zip_file, self._metadata_directory)

            self._write_record(zip_file)

        wheel_path = target_dir / self.wheel_filename
        if wheel_path.exists():
            wheel_path.unlink()
        shutil.move(temp_path, str(wheel_path))

        logger.info(f"Built {self.wheel_filename}")
        return wheel_path

    def _add_pth(self, wheel: zipfile.ZipFile) -> None:
        paths = set()
        for include in self._module.includes:
            if isinstance(include, PackageInclude) and (
                include.is_module() or include.is_package()
            ):
                paths.add(include.base.resolve().as_posix())

        content = ""
        for path in paths:
            content += path + os.linesep

        pth_file = Path(self._module.name).with_suffix(".pth")

        with self._write_to_zip(wheel, str(pth_file)) as f:
            f.write(content)

    def _build(self, wheel: zipfile.ZipFile) -> None:
        if self._package.build_script:
            if not self._poetry.package.build_should_generate_setup():
                # Since we have a build script but no setup.py generation is required,
                # we assume that the build script will build and copy the files
                # directly.
                # That way they will be picked up when adding files to the wheel.
                current_path = Path.cwd()
                try:
                    os.chdir(self._path)
                    self._run_build_script(self._package.build_script)
                finally:
                    os.chdir(current_path)
            else:
                with SdistBuilder(poetry=self._poetry).setup_py() as setup:
                    # We need to place ourselves in the temporary
                    # directory in order to build the package
                    current_path = Path.cwd()
                    try:
                        os.chdir(self._path)
                        self._run_build_command(setup)
                    finally:
                        os.chdir(current_path)

                    build_dir = self._path / "build"
                    libs: list[Path] = list(build_dir.glob("lib.*"))
                    if not libs:
                        # The result of building the extensions
                        # does not exist, this may due to conditional
                        # builds, so we assume that it's okay
                        return

                    lib = libs[0]

                    for pkg in sorted(lib.glob("**/*")):
                        if pkg.is_dir() or self.is_excluded(pkg):
                            continue

                        rel_path = pkg.relative_to(lib)

                        if rel_path.as_posix() in wheel.namelist():
                            continue

                        logger.debug(f"Adding: {rel_path}")

                        self._add_file(wheel, pkg, rel_path)

    def _copy_file_scripts(self, wheel: zipfile.ZipFile) -> None:
        file_scripts = self.convert_script_files()

        for abs_path in file_scripts:
            self._add_file(
                wheel,
                abs_path,
                Path(self.wheel_data_folder) / "scripts" / abs_path.name,
            )

    def _run_build_command(self, setup: Path) -> None:
        subprocess.check_call(
            [
                self.executable.as_posix(),
                str(setup),
                "build",
                "-b",
                str(self._path / "build"),
            ]
        )

    def _run_build_script(self, build_script: str) -> None:
        logger.debug(f"Executing build script: {build_script}")
        subprocess.check_call([self.executable.as_posix(), build_script])

    def _copy_module(self, wheel: zipfile.ZipFile) -> None:
        to_add = self.find_files_to_add()

        # Walk the files and compress them,
        # sorting everything so the order is stable.
        for file in sorted(to_add, key=lambda x: x.path):
            self._add_file(wheel, file.path, file.relative_to_source_root())

    def prepare_metadata(self, metadata_directory: Path) -> Path:
        dist_info = metadata_directory / self.dist_info
        dist_info.mkdir(parents=True, exist_ok=True)

        if (
            "scripts" in self._poetry.local_config
            or "plugins" in self._poetry.local_config
        ):
            with (dist_info / "entry_points.txt").open(
                "w", encoding="utf-8", newline="\n"
            ) as f:
                self._write_entry_points(f)

        with (dist_info / "WHEEL").open("w", encoding="utf-8", newline="\n") as f:
            self._write_wheel_file(f)

        with (dist_info / "METADATA").open("w", encoding="utf-8", newline="\n") as f:
            self._write_metadata_file(f)

        license_files = set()
        for base in ("COPYING", "LICENSE"):
            license_files.add(self._path / base)
            license_files.update(self._path.glob(base + ".*"))

        license_files.update(self._path.joinpath("LICENSES").glob("**/*"))

        for license_file in license_files:
            if not license_file.is_file():
                logger.debug(f"Skipping: {license_file.as_posix()}")
                continue

            dest = dist_info / license_file.relative_to(self._path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(license_file, dest)

        return dist_info

    def _write_record(self, wheel: zipfile.ZipFile) -> None:
        # Write a record of the files in the wheel
        with self._write_to_zip(wheel, self.dist_info + "/RECORD") as f:
            record = StringIO()

            csv_writer = csv.writer(
                record,
                delimiter=csv.excel.delimiter,
                quotechar=csv.excel.quotechar,
                lineterminator="\n",
            )
            for path, hash, size in self._records:
                csv_writer.writerow((path, f"sha256={hash}", size))

            # RECORD itself is recorded with no hash or size
            csv_writer.writerow((self.dist_info + "/RECORD", "", ""))

            f.write(record.getvalue())

    def _copy_dist_info(self, wheel: zipfile.ZipFile, source: Path) -> None:
        dist_info = Path(self.dist_info)
        for file in sorted(source.glob("**/*")):
            if not file.is_file():
                continue

            rel_path = file.relative_to(source)
            target = dist_info / rel_path
            self._add_file(wheel, file, target)

    @property
    def dist_info(self) -> str:
        return self.dist_info_name(self._package.name, self._meta.version)

    @property
    def wheel_data_folder(self) -> str:
        name = distribution_name(self._package.name)
        return f"{name}-{self._meta.version}.data"

    @property
    def wheel_filename(self) -> str:
        name = distribution_name(self._package.name)
        version = self._meta.version
        return f"{name}-{version}-{self.tag}.whl"

    def supports_python2(self) -> bool:
        return self._package.python_constraint.allows_any(
            parse_constraint(">=2.0.0 <3.0.0")
        )

    def dist_info_name(self, name: NormalizedName, version: str) -> str:
        escaped_name = distribution_name(name)
        return f"{escaped_name}-{version}.dist-info"

    def _get_sys_tags(self) -> list[str]:
        """Get sys_tags via subprocess.
        Required if poetry-core is not run inside the build environment.
        """
        try:
            output = subprocess.check_output(
                [
                    self.executable.as_posix(),
                    "-c",
                    f"""
import importlib.util
import sys

from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "packaging", Path(r"{packaging.__file__}")
)

packaging = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = packaging

spec = importlib.util.spec_from_file_location(
    "packaging.tags", Path(r"{packaging.tags.__file__}")
)
packaging_tags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging_tags)
for t in packaging_tags.sys_tags():
    print(t.interpreter, t.abi, t.platform, sep="-")
""",
                ],
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to get sys_tags for python interpreter"
                f" '{self.executable.as_posix()}':\n{decode(e.output)}"
            )
        return decode(output).strip().splitlines()

    @property
    def tag(self) -> str:
        if self._package.build_script:
            if self.executable != Path(sys.executable):
                # poetry-core is not run in the build environment
                # -> this is probably not a PEP 517 build but a poetry build
                return self._get_sys_tags()[0]
            sys_tag = next(packaging.tags.sys_tags())
            tag = (sys_tag.interpreter, sys_tag.abi, sys_tag.platform)
        else:
            platform = "any"
            impl = "py2.py3" if self.supports_python2() else "py3"
            tag = (impl, "none", platform)
        return "-".join(tag)

    def _add_file(
        self,
        wheel: zipfile.ZipFile,
        full_path: Path,
        rel_path: Path,
    ) -> None:
        # We always want to have /-separated paths in the zip file and in RECORD
        rel_path_name = rel_path.as_posix()
        zinfo = zipfile.ZipInfo(rel_path_name)

        # Normalize permission bits to either 755 (executable) or 644
        st_mode = full_path.stat().st_mode
        new_mode = normalize_file_permissions(st_mode)
        zinfo.external_attr = (new_mode & 0xFFFF) << 16  # Unix attributes

        if stat.S_ISDIR(st_mode):
            zinfo.external_attr |= 0x10  # MS-DOS directory flag

        hashsum = hashlib.sha256()
        with full_path.open("rb") as src:
            while True:
                buf = src.read(1024 * 8)
                if not buf:
                    break
                hashsum.update(buf)

            src.seek(0)
            wheel.writestr(zinfo, src.read(), compress_type=zipfile.ZIP_DEFLATED)

        size = full_path.stat().st_size
        hash_digest = urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

        self._records.append((rel_path_name, hash_digest, size))

    @contextlib.contextmanager
    def _write_to_zip(
        self, wheel: zipfile.ZipFile, rel_path: str
    ) -> Iterator[StringIO]:
        sio = StringIO()
        yield sio

        # The default is a fixed timestamp rather than the current time, so
        # that building a wheel twice on the same computer can automatically
        # give you the exact same result.
        date_time = (2016, 1, 1, 0, 0, 0)
        zi = zipfile.ZipInfo(rel_path, date_time)
        zi.external_attr = (0o644 & 0xFFFF) << 16  # Unix attributes
        b = sio.getvalue().encode("utf-8")
        hashsum = hashlib.sha256(b)
        hash_digest = urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

        wheel.writestr(zi, b, compress_type=zipfile.ZIP_DEFLATED)
        self._records.append((rel_path, hash_digest, len(b)))

    def _write_entry_points(self, fp: TextIO) -> None:
        """
        Write entry_points.txt.
        """
        entry_points = self.convert_entry_points()

        for group_name in sorted(entry_points):
            fp.write(f"[{group_name}]\n")
            for ep in sorted(entry_points[group_name]):
                fp.write(ep.replace(" ", "") + "\n")

            fp.write("\n")

    def _write_wheel_file(self, fp: TextIO) -> None:
        fp.write(
            wheel_file_template.format(
                version=__version__,
                pure_lib="true" if self._package.build_script is None else "false",
                tag=self.tag,
            )
        )

    def _write_metadata_file(self, fp: TextIO) -> None:
        """
        Write out metadata in the 2.x format (email like)
        """
        fp.write(self.get_metadata_content())
