"""Program to generate documentation for a given PyToolConfig object."""


from __future__ import annotations

import sys
from dataclasses import is_dataclass
from typing import Any, Generator

from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.ext.autodoc import ClassDocumenter
from tabulate import tabulate

from .fields import _gather_config_fields
from .pytoolconfig import PyToolConfig
from .sources import Source
from .types import ConfigField, Dataclass
from .universal_config import UniversalConfig

if sys.version_info < (3, 8, 0):
    from typing_extensions import get_origin
else:
    from typing import get_origin


def _type_to_str(type_to_print: type[Any]) -> str | None:
    if type_to_print is None:
        return None
    if get_origin(type_to_print) is None:
        return type_to_print.__name__
    return str(type_to_print).replace("typing.", "")


def _subtables(model: type[Dataclass]) -> dict[str, type[Dataclass]]:
    result = {}
    for name, field in _gather_config_fields(model).items():
        if is_dataclass(field._type):
            result[name] = field._type
    return result


def _generate_table(
    model: type[Dataclass],
    tablefmt: str = "rst",
    prefix: str = "",
) -> Generator[str, None, None]:
    header = ["name", "description", "type", "default"]
    model_fields: dict[str, ConfigField] = _gather_config_fields(model)
    command_line = any(field.command_line for field in model_fields.values())
    if command_line:
        header.append("command line flag")
    table = []
    for name, field in model_fields.items():
        if not is_dataclass(field._type):
            row = [
                f"{name}" if prefix == "" else f"{prefix}.{name}",
                field.description.replace("\n", " ") if field.description else None,
                _type_to_str(field._type),
                field._default,
            ]
            if field.universal_config:
                key = field.universal_config
                assert is_dataclass(UniversalConfig)
                universal_key = _gather_config_fields(UniversalConfig)[key.name]
                row[1] = universal_key.description
                row[3] = universal_key._default
            if command_line:
                cli_doc = field.command_line
                if cli_doc is not None:
                    row.append(", ".join(cli_doc))
                else:
                    row.append(None)
            table.append(row)
    yield from tabulate(table, tablefmt=tablefmt, headers=header).split("\n")


class PyToolConfigAutoDocumenter(ClassDocumenter):
    """Sphinx autodocumenter for pytoolconfig models."""

    objtype = "pytoolconfigtable"
    content_indent = ""
    titles_allowed = True

    @classmethod
    def can_document_member(
        cls, member: Any, membername: str, isattr: bool, parent: Any
    ) -> bool:
        """Check if member is dataclass."""
        return is_dataclass(member)

    def add_directive_header(self, sig: str) -> None:
        """Remove directive headers."""

    def add_content(
        self, more_content: StringList | None, no_docstring: bool = False
    ) -> None:
        """Create simple table to document configuration options."""
        source = self.get_sourcename()
        config = self.object
        for line in _generate_table(config):
            self.add_line(line, source)


class PyToolConfigSourceDocumenter(ClassDocumenter):
    objtype = "pytoolconfigsources"
    content_indent = ""
    titles_allowed = True

    @classmethod
    def can_document_member(
        cls, member: Any, membername: str, isattr: bool, parent: Any
    ) -> bool:
        """Check if member is dataclass."""
        return isinstance(member, Source)

    def add_directive_header(self, sig: str) -> None:
        """Remove directive headers."""

    def add_content(
        self, more_content: StringList | None, no_docstring: bool = False
    ) -> None:
        """Create simple table to document configuration options."""
        source = self.get_sourcename()
        config = self.object
        for line in _generate_table(config):
            self.add_line(line, source)


def setup(app: Sphinx) -> None:
    """Register automatic documenter."""
    app.setup_extension("sphinx.ext.autodoc")
    app.add_autodocumenter(PyToolConfigAutoDocumenter)


def _generate_documentation(config: PyToolConfig) -> Generator[str, None, None]:
    """Generate Markdown documentation for a given config model.

    This currently Beta at best. Do not use.
    """
    yield "# Configuration\n"
    if len(config.sources) > 1:
        yield f"{config.tool} supports the following sources:\n"
        for idx, source in enumerate(config.sources):
            yield f" {idx}. {source.name}\n"
    else:
        name = next(config.sources).name
        yield f"{config.tool} supports the {name} format\n"
    yield "\n"
    for source in config.sources:
        if source.description:
            yield f"## {source.name} \n"
            yield source.description
            yield "\n"
    yield "## Options\n"
    yield from _generate_table(config.model, "github")
    yield "\n"
    for prefix, subtable in _subtables(config.model).items():
        yield from _generate_table(subtable, "github", prefix)
        yield "\n"
