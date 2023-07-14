from __future__ import annotations

import hashlib
import io
import os
import shutil
import stat
import sys
import tempfile

from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from poetry.utils.constants import REQUESTS_TIMEOUT


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from io import BufferedWriter

    from poetry.core.packages.package import Package
    from requests import Session

    from poetry.utils.authenticator import Authenticator


@contextmanager
def directory(path: Path) -> Iterator[Path]:
    cwd = Path.cwd()
    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(cwd)


@contextmanager
def atomic_open(filename: str | os.PathLike[str]) -> Iterator[BufferedWriter]:
    """
    write a file to the disk in an atomic fashion

    Taken from requests.utils
    (https://github.com/psf/requests/blob/7104ad4b135daab0ed19d8e41bd469874702342b/requests/utils.py#L296)
    """
    tmp_descriptor, tmp_name = tempfile.mkstemp(dir=os.path.dirname(filename))
    try:
        with os.fdopen(tmp_descriptor, "wb") as tmp_handler:
            yield tmp_handler
        os.replace(tmp_name, filename)
    except BaseException:
        os.remove(tmp_name)
        raise


def _on_rm_error(func: Callable[[str], None], path: str, exc_info: Exception) -> None:
    if not os.path.exists(path):
        return

    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_directory(
    path: Path, *args: Any, force: bool = False, **kwargs: Any
) -> None:
    """
    Helper function handle safe removal, and optionally forces stubborn file removal.
    This is particularly useful when dist files are read-only or git writes read-only
    files on Windows.

    Internally, all arguments are passed to `shutil.rmtree`.
    """
    if path.is_symlink():
        return os.unlink(path)

    kwargs["onerror"] = kwargs.pop("onerror", _on_rm_error if force else None)
    shutil.rmtree(path, *args, **kwargs)


def merge_dicts(d1: dict[str, Any], d2: dict[str, Any]) -> None:
    for k in d2:
        if k in d1 and isinstance(d1[k], dict) and isinstance(d2[k], Mapping):
            merge_dicts(d1[k], d2[k])
        else:
            d1[k] = d2[k]


def download_file(
    url: str,
    dest: Path,
    session: Authenticator | Session | None = None,
    chunk_size: int = 1024,
) -> None:
    import requests

    from poetry.puzzle.provider import Indicator

    get = requests.get if not session else session.get

    response = get(url, stream=True, timeout=REQUESTS_TIMEOUT)
    response.raise_for_status()

    set_indicator = False
    with Indicator.context() as update_context:
        update_context(f"Downloading {url}")

        if "Content-Length" in response.headers:
            try:
                total_size = int(response.headers["Content-Length"])
            except ValueError:
                total_size = 0

            fetched_size = 0
            last_percent = 0

            # if less than 1MB, we simply show that we're downloading
            # but skip the updating
            set_indicator = total_size > 1024 * 1024

        with atomic_open(dest) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)

                    if set_indicator:
                        fetched_size += len(chunk)
                        percent = (fetched_size * 100) // total_size
                        if percent > last_percent:
                            last_percent = percent
                            update_context(f"Downloading {url} {percent:3}%")


def get_package_version_display_string(
    package: Package, root: Path | None = None
) -> str:
    if package.source_type in ["file", "directory"] and root:
        assert package.source_url is not None
        path = Path(os.path.relpath(package.source_url, root)).as_posix()
        return f"{package.version} {path}"

    pretty_version: str = package.full_pretty_version
    return pretty_version


def paths_csv(paths: list[Path]) -> str:
    return ", ".join(f'"{c!s}"' for c in paths)


def is_dir_writable(path: Path, create: bool = False) -> bool:
    try:
        if not path.exists():
            if not create:
                return False
            path.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryFile(dir=str(path)):
            pass
    except OSError:
        return False
    else:
        return True


def pluralize(count: int, word: str = "") -> str:
    if count == 1:
        return word
    return word + "s"


def _get_win_folder_from_registry(csidl_name: str) -> str:
    if sys.platform != "win32":
        raise RuntimeError("Method can only be called on Windows.")

    import winreg as _winreg

    shell_folder_name = {
        "CSIDL_APPDATA": "AppData",
        "CSIDL_COMMON_APPDATA": "Common AppData",
        "CSIDL_LOCAL_APPDATA": "Local AppData",
        "CSIDL_PROGRAM_FILES": "Program Files",
    }[csidl_name]

    key = _winreg.OpenKey(
        _winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
    )
    dir, type = _winreg.QueryValueEx(key, shell_folder_name)

    assert isinstance(dir, str)
    return dir


def _get_win_folder_with_ctypes(csidl_name: str) -> str:
    if sys.platform != "win32":
        raise RuntimeError("Method can only be called on Windows.")

    import ctypes

    csidl_const = {
        "CSIDL_APPDATA": 26,
        "CSIDL_COMMON_APPDATA": 35,
        "CSIDL_LOCAL_APPDATA": 28,
        "CSIDL_PROGRAM_FILES": 38,
    }[csidl_name]

    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl_const, None, 0, buf)

    # Downgrade to short path name if have highbit chars. See
    # <http://bugs.activestate.com/show_bug.cgi?id=85099>.
    has_high_char = False
    for c in buf:
        if ord(c) > 255:
            has_high_char = True
            break
    if has_high_char:
        buf2 = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(buf.value, buf2, 1024):
            buf = buf2

    return buf.value


def get_win_folder(csidl_name: str) -> Path:
    if sys.platform == "win32":
        try:
            from ctypes import windll  # noqa: F401

            _get_win_folder = _get_win_folder_with_ctypes
        except ImportError:
            _get_win_folder = _get_win_folder_from_registry

        return Path(_get_win_folder(csidl_name))

    raise RuntimeError("Method can only be called on Windows.")


def get_real_windows_path(path: Path) -> Path:
    program_files = get_win_folder("CSIDL_PROGRAM_FILES")
    local_appdata = get_win_folder("CSIDL_LOCAL_APPDATA")

    path = Path(
        str(path).replace(
            str(program_files / "WindowsApps"),
            str(local_appdata / "Microsoft/WindowsApps"),
        )
    )

    if path.as_posix().startswith(local_appdata.as_posix()):
        path = path.resolve()

    return path


def get_file_hash(path: Path, hash_name: str = "sha256") -> str:
    h = hashlib.new(hash_name)
    with path.open("rb") as fp:
        for content in iter(lambda: fp.read(io.DEFAULT_BUFFER_SIZE), b""):
            h.update(content)

    return h.hexdigest()
