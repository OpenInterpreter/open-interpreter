from __future__ import annotations

import os.path
import re

from wheel.cli import WheelError
from wheel.wheelfile import WheelFile

DIST_INFO_RE = re.compile(r"^(?P<namever>(?P<name>.+?)-(?P<ver>\d.*?))\.dist-info$")
BUILD_NUM_RE = re.compile(rb"Build: (\d\w*)$")


def pack(directory: str, dest_dir: str, build_number: str | None):
    """Repack a previously unpacked wheel directory into a new wheel file.

    The .dist-info/WHEEL file must contain one or more tags so that the target
    wheel file name can be determined.

    :param directory: The unpacked wheel directory
    :param dest_dir: Destination directory (defaults to the current directory)
    """
    # Find the .dist-info directory
    dist_info_dirs = [
        fn
        for fn in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, fn)) and DIST_INFO_RE.match(fn)
    ]
    if len(dist_info_dirs) > 1:
        raise WheelError(f"Multiple .dist-info directories found in {directory}")
    elif not dist_info_dirs:
        raise WheelError(f"No .dist-info directories found in {directory}")

    # Determine the target wheel filename
    dist_info_dir = dist_info_dirs[0]
    name_version = DIST_INFO_RE.match(dist_info_dir).group("namever")

    # Read the tags and the existing build number from .dist-info/WHEEL
    existing_build_number = None
    wheel_file_path = os.path.join(directory, dist_info_dir, "WHEEL")
    with open(wheel_file_path, "rb") as f:
        tags, existing_build_number = read_tags(f.read())

        if not tags:
            raise WheelError(
                "No tags present in {}/WHEEL; cannot determine target wheel "
                "filename".format(dist_info_dir)
            )

    # Set the wheel file name and add/replace/remove the Build tag in .dist-info/WHEEL
    build_number = build_number if build_number is not None else existing_build_number
    if build_number is not None:
        if build_number:
            name_version += "-" + build_number

        if build_number != existing_build_number:
            with open(wheel_file_path, "rb+") as f:
                wheel_file_content = f.read()
                wheel_file_content = set_build_number(wheel_file_content, build_number)

                f.seek(0)
                f.truncate()
                f.write(wheel_file_content)

    # Reassemble the tags for the wheel file
    tagline = compute_tagline(tags)

    # Repack the wheel
    wheel_path = os.path.join(dest_dir, f"{name_version}-{tagline}.whl")
    with WheelFile(wheel_path, "w") as wf:
        print(f"Repacking wheel as {wheel_path}...", end="", flush=True)
        wf.write_files(directory)

    print("OK")


def read_tags(input_str: bytes) -> tuple[list[str], str | None]:
    """Read tags from a string.

    :param input_str: A string containing one or more tags, separated by spaces
    :return: A list of tags and a list of build tags
    """

    tags = []
    existing_build_number = None
    for line in input_str.splitlines():
        if line.startswith(b"Tag: "):
            tags.append(line.split(b" ")[1].rstrip().decode("ascii"))
        elif line.startswith(b"Build: "):
            existing_build_number = line.split(b" ")[1].rstrip().decode("ascii")

    return tags, existing_build_number


def set_build_number(wheel_file_content: bytes, build_number: str | None) -> bytes:
    """Compute a build tag and add/replace/remove as necessary.

    :param wheel_file_content: The contents of .dist-info/WHEEL
    :param build_number: The build tags present in .dist-info/WHEEL
    :return: The (modified) contents of .dist-info/WHEEL
    """
    replacement = (
        ("Build: %s\r\n" % build_number).encode("ascii") if build_number else b""
    )

    wheel_file_content, num_replaced = BUILD_NUM_RE.subn(
        replacement, wheel_file_content
    )

    if not num_replaced:
        wheel_file_content += replacement

    return wheel_file_content


def compute_tagline(tags: list[str]) -> str:
    """Compute a tagline from a list of tags.

    :param tags: A list of tags
    :return: A tagline
    """
    impls = sorted({tag.split("-")[0] for tag in tags})
    abivers = sorted({tag.split("-")[1] for tag in tags})
    platforms = sorted({tag.split("-")[2] for tag in tags})
    return "-".join([".".join(impls), ".".join(abivers), ".".join(platforms)])
