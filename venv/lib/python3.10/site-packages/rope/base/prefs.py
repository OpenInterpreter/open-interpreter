"""Rope preferences."""
from dataclasses import asdict, dataclass
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Tuple

from packaging.requirements import Requirement
from pytoolconfig import PyToolConfig, UniversalKey, field
from pytoolconfig.sources import Source

from rope.base.resources import Folder


@dataclass
class Prefs:
    """Class to store rope preferences."""

    ignored_resources: List[str] = field(
        default_factory=lambda: [
            "*.pyc",
            "*~",
            ".ropeproject",
            ".hg",
            ".svn",
            "_svn",
            ".git",
            ".tox",
            ".venv",
            "venv",
            ".mypy_cache",
            ".pytest_cache",
        ],
        description=dedent("""
            Specify which files and folders to ignore in the project.
            Changes to ignored resources are not added to the history and
            VCSs.  Also they are not returned in `Project.get_files()`.
            Note that ``?`` and ``*`` match all characters but slashes.
            '*.pyc': matches 'test.pyc' and 'pkg/test.pyc'
            'mod*.pyc': matches 'test/mod1.pyc' but not 'mod/1.pyc'
            '.svn': matches 'pkg/.svn' and all of its children
            'build/*.o': matches 'build/lib.o' but not 'build/sub/lib.o'
            'build//*.o': matches 'build/lib.o' and 'build/sub/lib.o'
        """),
    )
    python_files: List[str] = field(
        default_factory=lambda: ["*.py"],
        description=dedent("""
            Specifies which files should be considered python files.  It is
            useful when you have scripts inside your project.  Only files
            ending with ``.py`` are considered to be python files by
            default.
        """),
    )
    source_folders: List[str] = field(
        description=dedent("""
            Custom source folders:  By default rope searches the project
            for finding source folders (folders that should be searched
            for finding modules).  You can add paths to that list.  Note
            that rope guesses project source folders correctly most of the
            time; use this if you have any problems.
            The folders should be relative to project root and use '/' for
            separating folders regardless of the platform rope is running on.
            'src/my_source_folder' for instance.
        """),
        default_factory=lambda: [],
    )
    python_path: List[str] = field(
        default_factory=lambda: [],
        description="You can extend python path for looking up modules.",
    )
    save_objectdb: bool = field(
        default=False, description="Should rope save object information or not."
    )
    compress_objectdb: bool = field(
        default=False,
        description="Deprecated. This has no effect",
    )
    automatic_soa: bool = field(
        True, "If `True`, rope analyzes each module when it is being saved."
    )
    soa_followed_calls: int = field(
        default=0, description="The depth of calls to follow in static object analysis"
    )
    perform_doa: bool = field(
        default=True,
        description=dedent("""
            If `False` when running modules or unit tests 'dynamic object analysis' is turned off.
            This makes them much faster.
        """),
    )
    validate_objectdb: bool = field(
        default=False,
        description="Rope can check the validity of its object DB when running.",
    )

    max_history_items: int = field(default=32, description="How many undos to hold?")
    save_history: bool = field(
        default=True, description="Shows whether to save history across sessions."
    )
    compress_history: bool = field(
        default=False,
        description="Deprecated. This has no effect",
    )

    indent_size: int = field(
        default=4,
        description=dedent("""
            Set the number spaces used for indenting.  According to
            :PEP:`8`, it is best to use 4 spaces.  Since most of rope's
            unit-tests use 4 spaces it is more reliable, too.
        """),
    )

    extension_modules: List[str] = field(
        default_factory=list,
        description="""
Builtin and c-extension modules that are allowed to be imported and inspected by rope.
        """,
    )

    import_dynload_stdmods: bool = field(
        default=True,
        description="Add all standard c-extensions to extension_modules list.",
    )
    ignore_syntax_errors: bool = field(
        default=False,
        description=dedent("""
            If `True` modules with syntax errors are considered to be empty.
            The default value is `False`; When `False` syntax errors raise
            `rope.base.exceptions.ModuleSyntaxError` exception.
        """),
    )

    ignore_bad_imports: bool = field(
        default=False,
        description=dedent("""
            If `True`, rope ignores unresolvable imports.  Otherwise, they
            appear in the importing namespace.
        """),
    )

    prefer_module_from_imports: bool = field(
        default=False,
        description=dedent("""
            If `True`, rope will insert new module imports as `from <package> import <module>`by default.
        """),
    )

    split_imports: bool = field(
        default=False,
        description=dedent("""
            If `True`, rope will transform a comma list of imports into
            multiple separate import statements when organizing
            imports.
        """),
    )

    pull_imports_to_top: bool = field(
        default=True,
        description=dedent("""
            If `True`, rope will remove all top-level import statements and
            reinsert them at the top of the module when making changes.
        """),
    )

    sort_imports_alphabetically: bool = field(
        default=False,
        description=dedent("""
            If `True`, rope will sort imports alphabetically by module name instead
            of alphabetically by import statement, with from imports after normal
            imports.
        """),
    )
    type_hinting_factory: str = field(
        "rope.base.oi.type_hinting.factory.default_type_hinting_factory",
        description=dedent("""
            Location of implementation of
            rope.base.oi.type_hinting.interfaces.ITypeHintingFactory In general
            case, you don't have to change this value, unless you're an rope expert.
            Change this value to inject you own implementations of interfaces
            listed in module rope.base.oi.type_hinting.providers.interfaces
            For example, you can add you own providers for Django Models, or disable
            the search type-hinting in a class hierarchy, etc.
        """),
    )
    project_opened: Optional[Callable] = field(
        None,
        description=dedent("""
            This function is called after opening the project.
            Can only be set in config.py.
        """),
    )
    py_version: Optional[Tuple[int, int]] = field(
        default=None,
        description="Minimum python version to target",
        universal_config=UniversalKey.min_py_version,
    )
    dependencies: Optional[List[Requirement]] = field(
        default=None, universal_config=UniversalKey.dependencies
    )
    callbacks: Dict[str, Callable[[Any], None]] = field(
        default_factory=lambda: {},
        description=dedent("""
            Callbacks run when configuration values are changed.
            Can only be set in config.py.
        """),
    )

    def set(self, key: str, value: Any):
        """Set the value of `key` preference to `value`."""
        if key in self.callbacks:
            self.callbacks[key](value)
        else:
            setattr(self, key, value)

    def add(self, key: str, value: Any):
        """Add an entry to a list preference

        Add `value` to the list of entries for the `key` preference.

        """
        if getattr(self, key) is None:
            self[key] = []
        getattr(self, key).append(value)

    def get(self, key: str, default: Any = None):
        """Get the value of the key preference"""
        return getattr(self, key, default)

    def add_callback(self, key: str, callback: Callable):
        """Add `key` preference with `callback` function

        Whenever `key` is set the callback is called with the
        given `value` as parameter.

        """
        self.callbacks[key] = callback

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def __getitem__(self, key: str):
        return self.get(key)


class _RopeConfigSource(Source):
    """Custom source for rope config.py files."""

    name: str = "config.py"
    run_globals: Dict

    def __init__(self, ropefolder: Folder):
        self.ropefolder = ropefolder
        self.run_globals = {}

    def _read(self) -> bool:
        if self.ropefolder is None or not self.ropefolder.has_child("config.py"):
            return False
        config = self.ropefolder.get_child("config.py")
        self.run_globals.update(
            {
                "__name__": "__main__",
                "__builtins__": __builtins__,
                "__file__": config.real_path,
            }
        )
        with open(config.real_path) as f:
            code = compile(f.read(), config.real_path, "exec")
            exec(code, self.run_globals)
        return True

    def parse(self) -> Optional[Dict]:
        prefs = Prefs()
        if not self._read():
            return None
        if "set_prefs" in self.run_globals:
            self.run_globals["set_prefs"](prefs)
        if "project_opened" in self.run_globals:
            prefs["project_opened"] = self.run_globals["project_opened"]
        return asdict(prefs)


def get_config(root: Folder, ropefolder: Folder) -> PyToolConfig:
    custom_sources = [_RopeConfigSource(ropefolder)]
    config = PyToolConfig(
        "rope",
        root.pathlib,
        Prefs,
        custom_sources=custom_sources,
        bases=[".ropefolder"],
        recursive=False,
        global_config=True,
    )
    return config
