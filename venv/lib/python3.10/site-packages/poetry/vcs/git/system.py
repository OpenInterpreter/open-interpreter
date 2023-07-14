from __future__ import annotations

import os
import subprocess

from typing import TYPE_CHECKING

from dulwich.client import find_git_command


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


class SystemGit:
    @classmethod
    def clone(cls, repository: str, dest: Path) -> str:
        cls._check_parameter(repository)

        return cls.run("clone", "--recurse-submodules", "--", repository, str(dest))

    @classmethod
    def checkout(cls, rev: str, target: Path | None = None) -> str:
        args = []

        if target:
            args += [
                "--git-dir",
                (target / ".git").as_posix(),
                "--work-tree",
                target.as_posix(),
            ]

        cls._check_parameter(rev)

        args += ["checkout", rev]

        return cls.run(*args)

    @staticmethod
    def run(*args: Any, **kwargs: Any) -> str:
        folder = kwargs.pop("folder", None)
        if folder:
            args = (
                "--git-dir",
                (folder / ".git").as_posix(),
                "--work-tree",
                folder.as_posix(),
                *args,
            )

        git_command = find_git_command()
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return (
            subprocess.check_output(
                git_command + list(args),
                stderr=subprocess.STDOUT,
                env=env,
            )
            .decode()
            .strip()
        )

    @staticmethod
    def _check_parameter(parameter: str) -> None:
        """
        Checks a git parameter to avoid unwanted code execution.
        """
        if parameter.strip().startswith("-"):
            raise RuntimeError(f"Invalid Git parameter: {parameter}")
