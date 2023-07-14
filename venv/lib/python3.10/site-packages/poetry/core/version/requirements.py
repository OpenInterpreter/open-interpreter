from __future__ import annotations

import urllib.parse as urlparse

from poetry.core.constraints.version import parse_constraint
from poetry.core.constraints.version.exceptions import ParseConstraintError
from poetry.core.version.grammars import GRAMMAR_PEP_508_CONSTRAINTS
from poetry.core.version.markers import _compact_markers
from poetry.core.version.parser import Parser


class InvalidRequirement(ValueError):
    """
    An invalid requirement was found, users should refer to PEP 508.
    """


# Parser: PEP 508 Constraints
_parser = Parser(GRAMMAR_PEP_508_CONSTRAINTS, "lalr")


class Requirement:
    """
    Parse a requirement.

    Parse a given requirement string into its parts, such as name, specifier,
    URL, and extras. Raises InvalidRequirement on a badly-formed requirement
    string.
    """

    def __init__(self, requirement_string: str) -> None:
        from lark import UnexpectedCharacters
        from lark import UnexpectedToken

        try:
            parsed = _parser.parse(requirement_string)
        except (UnexpectedCharacters, UnexpectedToken) as e:
            raise InvalidRequirement(
                "The requirement is invalid: Unexpected character at column"
                f" {e.column}\n\n{e.get_context(requirement_string)}"
            )

        self.name: str = next(parsed.scan_values(lambda t: t.type == "NAME")).value
        url = next(parsed.scan_values(lambda t: t.type == "URI"), None)

        if url:
            url = url.value
            parsed_url = urlparse.urlparse(url)
            if parsed_url.scheme == "file":
                if urlparse.urlunparse(parsed_url) != url:
                    raise InvalidRequirement(
                        f'The requirement is invalid: invalid URL "{url}"'
                    )
            elif (
                not (parsed_url.scheme and parsed_url.netloc)
            ) and not parsed_url.path:
                raise InvalidRequirement(
                    f'The requirement is invalid: invalid URL "{url}"'
                )
            self.url = url
        else:
            self.url = None

        self.extras = [e.value for e in parsed.scan_values(lambda t: t.type == "EXTRA")]
        constraint = next(parsed.find_data("version_specification"), None)
        constraint = ",".join(constraint.children) if constraint else "*"

        try:
            self.constraint = parse_constraint(constraint)
        except ParseConstraintError:
            raise InvalidRequirement(
                f'The requirement is invalid: invalid version constraint "{constraint}"'
            )

        self.pretty_constraint = constraint

        marker = next(parsed.find_data("marker_spec"), None)
        if marker:
            marker = _compact_markers(
                marker.children[0].children, tree_prefix="markers__"
            )

        self.marker = marker

    def __str__(self) -> str:
        parts = [self.name]

        if self.extras:
            extras = ",".join(sorted(self.extras))
            parts.append(f"[{extras}]")

        if self.pretty_constraint:
            parts.append(self.pretty_constraint)

        if self.url:
            parts.append(f"@ {self.url}")

        if self.marker:
            parts.append(f"; {self.marker}")

        return "".join(parts)

    def __repr__(self) -> str:
        return f"<Requirement({str(self)!r})>"
