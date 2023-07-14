# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import re
import sys

from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from cleo import option
from tomlkit import inline_table

from poetry.core.pyproject import PyProjectException
from poetry.core.pyproject.toml import PyProjectTOML
from poetry.utils._compat import OrderedDict
from poetry.utils._compat import Path
from poetry.utils._compat import urlparse

from .command import Command
from .env_command import EnvCommand


class InitCommand(Command):
    name = "init"
    description = (
        "Creates a basic <comment>pyproject.toml</> file in the current directory."
    )

    options = [
        option("name", None, "Name of the package.", flag=False),
        option("description", None, "Description of the package.", flag=False),
        option("author", None, "Author name of the package.", flag=False),
        option("python", None, "Compatible Python versions.", flag=False),
        option(
            "dependency",
            None,
            "Package to require, with an optional version constraint, "
            "e.g. requests:^2.10.0 or requests=2.11.1.",
            flag=False,
            multiple=True,
        ),
        option(
            "dev-dependency",
            None,
            "Package to require for development, with an optional version constraint, "
            "e.g. requests:^2.10.0 or requests=2.11.1.",
            flag=False,
            multiple=True,
        ),
        option("license", "l", "License of the package.", flag=False),
    ]

    help = """\
The <c1>init</c1> command creates a basic <comment>pyproject.toml</> file in the current directory.
"""

    def __init__(self):
        super(InitCommand, self).__init__()

        self._pool = None

    def handle(self):
        from poetry.core.vcs.git import GitConfig
        from poetry.layouts import layout
        from poetry.utils._compat import Path
        from poetry.utils.env import SystemEnv

        pyproject = PyProjectTOML(Path.cwd() / "pyproject.toml")

        if pyproject.file.exists():
            if pyproject.is_poetry_project():
                self.line(
                    "<error>A pyproject.toml file with a poetry section already exists.</error>"
                )
                return 1

            if pyproject.data.get("build-system"):
                self.line(
                    "<error>A pyproject.toml file with a defined build-system already exists.</error>"
                )
                return 1

        vcs_config = GitConfig()

        self.line("")
        self.line(
            "This command will guide you through creating your <info>pyproject.toml</> config."
        )
        self.line("")

        name = self.option("name")
        if not name:
            name = Path.cwd().name.lower()

            question = self.create_question(
                "Package name [<comment>{}</comment>]: ".format(name), default=name
            )
            name = self.ask(question)

        version = "0.1.0"
        question = self.create_question(
            "Version [<comment>{}</comment>]: ".format(version), default=version
        )
        version = self.ask(question)

        description = self.option("description") or ""
        question = self.create_question(
            "Description [<comment>{}</comment>]: ".format(description),
            default=description,
        )
        description = self.ask(question)

        author = self.option("author")
        if not author and vcs_config and vcs_config.get("user.name"):
            author = vcs_config["user.name"]
            author_email = vcs_config.get("user.email")
            if author_email:
                author += " <{}>".format(author_email)

        question = self.create_question(
            "Author [<comment>{}</comment>, n to skip]: ".format(author), default=author
        )
        question.set_validator(lambda v: self._validate_author(v, author))
        author = self.ask(question)

        if not author:
            authors = []
        else:
            authors = [author]

        license = self.option("license") or ""

        question = self.create_question(
            "License [<comment>{}</comment>]: ".format(license), default=license
        )
        question.set_validator(self._validate_license)
        license = self.ask(question)

        python = self.option("python")
        if not python:
            current_env = SystemEnv(Path(sys.executable))
            default_python = "^{}".format(
                ".".join(str(v) for v in current_env.version_info[:2])
            )
            question = self.create_question(
                "Compatible Python versions [<comment>{}</comment>]: ".format(
                    default_python
                ),
                default=default_python,
            )
            python = self.ask(question)

        self.line("")

        requirements = {}
        if self.option("dependency"):
            requirements = self._format_requirements(
                self._determine_requirements(self.option("dependency"))
            )

        question = "Would you like to define your main dependencies interactively?"
        help_message = (
            "You can specify a package in the following forms:\n"
            "  - A single name (<b>requests</b>)\n"
            "  - A name and a constraint (<b>requests@^2.23.0</b>)\n"
            "  - A git url (<b>git+https://github.com/python-poetry/poetry.git</b>)\n"
            "  - A git url with a revision (<b>git+https://github.com/python-poetry/poetry.git#develop</b>)\n"
            "  - A file path (<b>../my-package/my-package.whl</b>)\n"
            "  - A directory (<b>../my-package/</b>)\n"
            "  - A url (<b>https://example.com/packages/my-package-0.1.0.tar.gz</b>)\n"
        )
        help_displayed = False
        if self.confirm(question, True):
            self.line(help_message)
            help_displayed = True
            requirements.update(
                self._format_requirements(self._determine_requirements([]))
            )
            self.line("")

        dev_requirements = {}
        if self.option("dev-dependency"):
            dev_requirements = self._format_requirements(
                self._determine_requirements(self.option("dev-dependency"))
            )

        question = (
            "Would you like to define your development dependencies interactively?"
        )
        if self.confirm(question, True):
            if not help_displayed:
                self.line(help_message)

            dev_requirements.update(
                self._format_requirements(self._determine_requirements([]))
            )
            self.line("")

        layout_ = layout("standard")(
            name,
            version,
            description=description,
            author=authors[0] if authors else None,
            license=license,
            python=python,
            dependencies=requirements,
            dev_dependencies=dev_requirements,
        )

        content = layout_.generate_poetry_content(original=pyproject)
        if self.io.is_interactive():
            self.line("<info>Generated file</info>")
            self.line("")
            self.line(content)
            self.line("")

        if not self.confirm("Do you confirm generation?", True):
            self.line("<error>Command aborted</error>")

            return 1

        with (Path.cwd() / "pyproject.toml").open("w", encoding="utf-8") as f:
            f.write(content)

    def _determine_requirements(
        self, requires, allow_prereleases=False, source=None
    ):  # type: (List[str], bool) -> List[Dict[str, str]]
        if not requires:
            requires = []

            package = self.ask(
                "Search for package to add (or leave blank to continue):"
            )
            while package is not None:
                constraint = self._parse_requirements([package])[0]
                if (
                    "git" in constraint
                    or "url" in constraint
                    or "path" in constraint
                    or "version" in constraint
                ):
                    self.line("Adding <info>{}</info>".format(package))
                    requires.append(constraint)
                    package = self.ask("\nAdd a package:")
                    continue

                matches = self._get_pool().search(constraint["name"])

                if not matches:
                    self.line("<error>Unable to find package</error>")
                    package = False
                else:
                    choices = []
                    matches_names = [p.name for p in matches]
                    exact_match = constraint["name"] in matches_names
                    if exact_match:
                        choices.append(
                            matches[matches_names.index(constraint["name"])].pretty_name
                        )

                    for found_package in matches:
                        if len(choices) >= 10:
                            break

                        if found_package.name.lower() == constraint["name"].lower():
                            continue

                        choices.append(found_package.pretty_name)

                    self.line(
                        "Found <info>{}</info> packages matching <c1>{}</c1>".format(
                            len(matches), package
                        )
                    )

                    package = self.choice(
                        "\nEnter package # to add, or the complete package name if it is not listed",
                        choices,
                        attempts=3,
                    )

                    # package selected by user, set constraint name to package name
                    if package is not False:
                        constraint["name"] = package

                # no constraint yet, determine the best version automatically
                if package is not False and "version" not in constraint:
                    question = self.create_question(
                        "Enter the version constraint to require "
                        "(or leave blank to use the latest version):"
                    )
                    question.attempts = 3
                    question.validator = lambda x: (x or "").strip() or False

                    package_constraint = self.ask(question)

                    if package_constraint is None:
                        _, package_constraint = self._find_best_version_for_package(
                            package
                        )

                        self.line(
                            "Using version <b>{}</b> for <c1>{}</c1>".format(
                                package_constraint, package
                            )
                        )

                    constraint["version"] = package_constraint

                if package is not False:
                    requires.append(constraint)

                package = self.ask("\nAdd a package:")

            return requires

        requires = self._parse_requirements(requires)
        result = []
        for requirement in requires:
            if "git" in requirement or "url" in requirement or "path" in requirement:
                result.append(requirement)
                continue
            elif "version" not in requirement:
                # determine the best version automatically
                name, version = self._find_best_version_for_package(
                    requirement["name"],
                    allow_prereleases=allow_prereleases,
                    source=source,
                )
                requirement["version"] = version
                requirement["name"] = name

                self.line(
                    "Using version <b>{}</b> for <c1>{}</c1>".format(version, name)
                )
            else:
                # check that the specified version/constraint exists
                # before we proceed
                name, _ = self._find_best_version_for_package(
                    requirement["name"],
                    requirement["version"],
                    allow_prereleases=allow_prereleases,
                    source=source,
                )

                requirement["name"] = name

            result.append(requirement)

        return result

    def _find_best_version_for_package(
        self, name, required_version=None, allow_prereleases=False, source=None
    ):  # type: (...) -> Tuple[str, str]
        from poetry.version.version_selector import VersionSelector

        selector = VersionSelector(self._get_pool())
        package = selector.find_best_candidate(
            name, required_version, allow_prereleases=allow_prereleases, source=source
        )

        if not package:
            # TODO: find similar
            raise ValueError(
                "Could not find a matching version of package {}".format(name)
            )

        return package.pretty_name, selector.find_recommended_require_version(package)

    def _parse_requirements(
        self, requirements
    ):  # type: (List[str]) -> List[Dict[str, str]]
        from poetry.puzzle.provider import Provider

        result = []

        try:
            cwd = self.poetry.file.parent
        except (PyProjectException, RuntimeError):
            cwd = Path.cwd()

        for requirement in requirements:
            requirement = requirement.strip()
            extras = []
            extras_m = re.search(r"\[([\w\d,-_ ]+)\]$", requirement)
            if extras_m:
                extras = [e.strip() for e in extras_m.group(1).split(",")]
                requirement, _ = requirement.split("[")

            url_parsed = urlparse.urlparse(requirement)
            if url_parsed.scheme and url_parsed.netloc:
                # Url
                if url_parsed.scheme in ["git+https", "git+ssh"]:
                    from poetry.core.vcs.git import Git
                    from poetry.core.vcs.git import ParsedUrl

                    parsed = ParsedUrl.parse(requirement)
                    url = Git.normalize_url(requirement)

                    pair = OrderedDict([("name", parsed.name), ("git", url.url)])
                    if parsed.rev:
                        pair["rev"] = url.revision

                    if extras:
                        pair["extras"] = extras

                    package = Provider.get_package_from_vcs(
                        "git", url.url, rev=pair.get("rev")
                    )
                    pair["name"] = package.name
                    result.append(pair)

                    continue
                elif url_parsed.scheme in ["http", "https"]:
                    package = Provider.get_package_from_url(requirement)

                    pair = OrderedDict(
                        [("name", package.name), ("url", package.source_url)]
                    )
                    if extras:
                        pair["extras"] = extras

                    result.append(pair)
                    continue
            elif (os.path.sep in requirement or "/" in requirement) and cwd.joinpath(
                requirement
            ).exists():
                path = cwd.joinpath(requirement)
                if path.is_file():
                    package = Provider.get_package_from_file(path.resolve())
                else:
                    package = Provider.get_package_from_directory(path)

                result.append(
                    OrderedDict(
                        [
                            ("name", package.name),
                            ("path", path.relative_to(cwd).as_posix()),
                        ]
                        + ([("extras", extras)] if extras else [])
                    )
                )

                continue

            pair = re.sub(
                "^([^@=: ]+)(?:@|==|(?<![<>~!])=|:| )(.*)$", "\\1 \\2", requirement
            )
            pair = pair.strip()

            require = OrderedDict()
            if " " in pair:
                name, version = pair.split(" ", 2)
                extras_m = re.search(r"\[([\w\d,-_]+)\]$", name)
                if extras_m:
                    extras = [e.strip() for e in extras_m.group(1).split(",")]
                    name, _ = name.split("[")

                require["name"] = name
                if version != "latest":
                    require["version"] = version
            else:
                m = re.match(
                    r"^([^><=!: ]+)((?:>=|<=|>|<|!=|~=|~|\^).*)$", requirement.strip()
                )
                if m:
                    name, constraint = m.group(1), m.group(2)
                    extras_m = re.search(r"\[([\w\d,-_]+)\]$", name)
                    if extras_m:
                        extras = [e.strip() for e in extras_m.group(1).split(",")]
                        name, _ = name.split("[")

                    require["name"] = name
                    require["version"] = constraint
                else:
                    extras_m = re.search(r"\[([\w\d,-_]+)\]$", pair)
                    if extras_m:
                        extras = [e.strip() for e in extras_m.group(1).split(",")]
                        pair, _ = pair.split("[")

                    require["name"] = pair

            if extras:
                require["extras"] = extras

            result.append(require)

        return result

    def _format_requirements(
        self, requirements
    ):  # type: (List[Dict[str, str]]) -> Dict[str, Union[str, Dict[str, str]]]
        requires = {}
        for requirement in requirements:
            name = requirement.pop("name")
            if "version" in requirement and len(requirement) == 1:
                constraint = requirement["version"]
            else:
                constraint = inline_table()
                constraint.trivia.trail = "\n"
                constraint.update(requirement)

            requires[name] = constraint

        return requires

    def _validate_author(self, author, default):
        from poetry.core.packages.package import AUTHOR_REGEX

        author = author or default

        if author in ["n", "no"]:
            return

        m = AUTHOR_REGEX.match(author)
        if not m:
            raise ValueError(
                "Invalid author string. Must be in the format: "
                "John Smith <john@example.com>"
            )

        return author

    def _validate_license(self, license):
        from poetry.core.spdx import license_by_id

        if license:
            license_by_id(license)

        return license

    def _get_pool(self):
        from poetry.repositories import Pool
        from poetry.repositories.pypi_repository import PyPiRepository

        if isinstance(self, EnvCommand):
            return self.poetry.pool

        if self._pool is None:
            self._pool = Pool()
            self._pool.add_repository(PyPiRepository(config=self.poetry.config))

        return self._pool
