"""
Functions to find importable names.

Can extract names from source code of a python file, .so object, or builtin module.
"""

import inspect
import logging
import pathlib
from importlib import import_module
from typing import Generator, List

from rope.base import ast

from .defs import (
    ModuleCompiled,
    ModuleFile,
    ModuleInfo,
    Name,
    NameType,
    Package,
    PartialName,
    Source,
)

logger = logging.getLogger(__name__)


def get_type_ast(node: ast.AST) -> NameType:
    """Get the lsp type of a node."""
    if isinstance(node, ast.ClassDef):
        return NameType.Class
    if isinstance(node, ast.FunctionDef):
        return NameType.Function
    if isinstance(node, ast.Assign):
        return NameType.Variable
    return NameType.Variable  # default value


def get_names_from_file(
    module: pathlib.Path,
    package_name: str = "",
    underlined: bool = False,
    process_imports: bool = False,
) -> Generator[PartialName, None, None]:
    """Get all the names from a given file using ast."""
    try:
        root_node = ast.parse(module.read_bytes())
    except SyntaxError as error:
        print(error)
        return
    for node in ast.iter_child_nodes(root_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                try:
                    assert isinstance(target, ast.Name)
                    if underlined or not target.id.startswith("_"):
                        yield PartialName(
                            target.id,
                            get_type_ast(node),
                        )
                except (AttributeError, AssertionError):
                    # TODO handle tuple assignment
                    pass
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if underlined or not node.name.startswith("_"):
                yield PartialName(
                    node.name,
                    get_type_ast(node),
                )
        elif process_imports and isinstance(node, ast.ImportFrom):
            # When we process imports, we want to include names in it's own package.
            if node.level == 0:
                continue
            if not node.module or package_name is node.module.split(".")[0]:
                continue
            for name in node.names:
                if isinstance(name, ast.alias):
                    if name.asname:
                        real_name = name.asname
                    else:
                        real_name = name.name
                else:
                    real_name = name
                if underlined or not real_name.startswith("_"):
                    yield PartialName(real_name, get_type_ast(node))


def get_type_object(imported_object) -> NameType:
    """Determine the type of an object."""
    if inspect.isclass(imported_object):
        return NameType.Class
    if inspect.isfunction(imported_object) or inspect.isbuiltin(imported_object):
        return NameType.Function
    return NameType.Variable


def get_names(module: ModuleInfo, package: Package) -> List[Name]:
    """Get all names from a module and package."""
    if isinstance(module, ModuleCompiled):
        return list(
            get_names_from_compiled(package.name, package.source, module.underlined)
        )
    if isinstance(module, ModuleFile):
        return [
            combine(package, module, partial_name)
            for partial_name in get_names_from_file(
                module.filepath,
                package.name,
                underlined=module.underlined,
                process_imports=module.process_imports,
            )
        ]
    return []


def get_names_from_compiled(
    package: str,
    source: Source,
    underlined: bool = False,
) -> Generator[Name, None, None]:
    """
    Get the names from a compiled module.

    Instead of using ast, it imports the module.
    Parameters
    ----------
    package : str
        package to import. Must be in sys.path
    underlined : bool
        include underlined names
    """
    # builtins is banned because you never have to import it
    # python_crun is banned because it crashes python
    banned = ["builtins", "python_crun"]
    if package in banned or (package.startswith("_") and not underlined):
        return  # Builtins is redundant since you don't have to import it.
    if source not in (Source.BUILTIN, Source.STANDARD):
        return
    try:
        module = import_module(str(package))
    except ImportError:
        logger.error(f"{package} could not be imported for autoimport analysis")
        return
    else:
        for name, value in inspect.getmembers(module):
            if underlined or not name.startswith("_"):
                if (
                    inspect.isclass(value)
                    or inspect.isfunction(value)
                    or inspect.isbuiltin(value)
                ):
                    yield Name(
                        str(name), package, package, source, get_type_object(value)
                    )


def combine(package: Package, module: ModuleFile, name: PartialName) -> Name:
    """Combine information to form a full name."""
    return Name(name.name, module.modname, package.name, package.source, name.name_type)
