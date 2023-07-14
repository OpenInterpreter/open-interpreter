from __future__ import annotations

import ast

from configparser import ConfigParser
from typing import TYPE_CHECKING
from typing import Any

from poetry.core.constraints.version import Version


if TYPE_CHECKING:
    from pathlib import Path


class SetupReader:
    """
    Class that reads a setup.py file without executing it.
    """

    DEFAULT: dict[str, Any] = {
        "name": None,
        "version": None,
        "install_requires": [],
        "extras_require": {},
        "python_requires": None,
    }

    FILES = ["setup.py", "setup.cfg"]

    @classmethod
    def read_from_directory(cls, directory: Path) -> dict[str, Any]:
        result = cls.DEFAULT.copy()
        for filename in cls.FILES:
            filepath = directory / filename
            if not filepath.exists():
                continue

            read_file_func = getattr(cls(), "read_" + filename.replace(".", "_"))
            new_result = read_file_func(filepath)

            for key in result:
                if new_result[key]:
                    result[key] = new_result[key]

        return result

    def read_setup_py(self, filepath: Path) -> dict[str, Any]:
        with filepath.open(encoding="utf-8") as f:
            content = f.read()

        result: dict[str, Any] = {}

        body = ast.parse(content).body

        setup_call = self._find_setup_call(body)
        if setup_call is None:
            return self.DEFAULT

        # Inspecting keyword arguments
        call, body = setup_call
        result["name"] = self._find_single_string(call, body, "name")
        result["version"] = self._find_single_string(call, body, "version")
        result["install_requires"] = self._find_install_requires(call, body)
        result["extras_require"] = self._find_extras_require(call, body)
        result["python_requires"] = self._find_single_string(
            call, body, "python_requires"
        )

        return result

    def read_setup_cfg(self, filepath: Path) -> dict[str, Any]:
        parser = ConfigParser()

        parser.read(str(filepath))

        name = None
        version = None
        if parser.has_option("metadata", "name"):
            name = parser.get("metadata", "name")

        if parser.has_option("metadata", "version"):
            version = Version.parse(parser.get("metadata", "version")).text

        install_requires = []
        extras_require: dict[str, list[str]] = {}
        python_requires = None
        if parser.has_section("options"):
            if parser.has_option("options", "install_requires"):
                for dep in parser.get("options", "install_requires").split("\n"):
                    dep = dep.strip()
                    if not dep:
                        continue

                    install_requires.append(dep)

            if parser.has_option("options", "python_requires"):
                python_requires = parser.get("options", "python_requires")

        if parser.has_section("options.extras_require"):
            for group in parser.options("options.extras_require"):
                extras_require[group] = []
                deps = parser.get("options.extras_require", group)
                for dep in deps.split("\n"):
                    dep = dep.strip()
                    if not dep:
                        continue

                    extras_require[group].append(dep)

        return {
            "name": name,
            "version": version,
            "install_requires": install_requires,
            "extras_require": extras_require,
            "python_requires": python_requires,
        }

    def _find_setup_call(
        self, elements: list[ast.stmt]
    ) -> tuple[ast.Call, list[ast.stmt]] | None:
        funcdefs: list[ast.stmt] = []
        for i, element in enumerate(elements):
            if isinstance(element, ast.If) and i == len(elements) - 1:
                # Checking if the last element is an if statement
                # and if it is 'if __name__ == "__main__"' which
                # could contain the call to setup()
                test = element.test
                if not isinstance(test, ast.Compare):
                    continue

                left = test.left
                if not isinstance(left, ast.Name):
                    continue

                if left.id != "__name__":
                    continue

                setup_call = self._find_sub_setup_call([element])
                if setup_call is None:
                    continue

                call, body = setup_call
                return call, body + elements

            if not isinstance(element, ast.Expr):
                if isinstance(element, ast.FunctionDef):
                    funcdefs.append(element)

                continue

            value = element.value
            if not isinstance(value, ast.Call):
                continue

            func = value.func
            if not (isinstance(func, ast.Name) and func.id == "setup") and not (
                isinstance(func, ast.Attribute)
                and getattr(func.value, "id", None) == "setuptools"
                and func.attr == "setup"
            ):
                continue

            return value, elements

        # Nothing, we inspect the function definitions
        return self._find_sub_setup_call(funcdefs)

    def _find_sub_setup_call(
        self, elements: list[ast.stmt]
    ) -> tuple[ast.Call, list[ast.stmt]] | None:
        for element in elements:
            if not isinstance(element, (ast.FunctionDef, ast.If)):
                continue

            setup_call = self._find_setup_call(element.body)
            if setup_call is not None:
                sub_call, body = setup_call

                body = elements + body

                return sub_call, body

        return None

    def _find_install_requires(self, call: ast.Call, body: list[ast.stmt]) -> list[str]:
        install_requires: list[str] = []
        value = self._find_in_call(call, "install_requires")
        if value is None:
            # Trying to find in kwargs
            kwargs = self._find_call_kwargs(call)

            if kwargs is None or not isinstance(kwargs, ast.Name):
                return install_requires

            variable = self._find_variable_in_body(body, kwargs.id)
            if not isinstance(variable, (ast.Dict, ast.Call)):
                return install_requires

            if isinstance(variable, ast.Call):
                if not isinstance(variable.func, ast.Name):
                    return install_requires

                if variable.func.id != "dict":
                    return install_requires

                value = self._find_in_call(variable, "install_requires")
            else:
                value = self._find_in_dict(variable, "install_requires")

        if value is None:
            return install_requires

        if isinstance(value, ast.List):
            for el in value.elts:
                if isinstance(el, ast.Str):
                    install_requires.append(el.s)
        elif isinstance(value, ast.Name):
            variable = self._find_variable_in_body(body, value.id)

            if variable is not None and isinstance(variable, ast.List):
                for el in variable.elts:
                    if isinstance(el, ast.Str):
                        install_requires.append(el.s)

        return install_requires

    def _find_extras_require(
        self, call: ast.Call, body: list[ast.stmt]
    ) -> dict[str, list[str]]:
        extras_require: dict[str, list[str]] = {}
        value = self._find_in_call(call, "extras_require")
        if value is None:
            # Trying to find in kwargs
            kwargs = self._find_call_kwargs(call)

            if kwargs is None or not isinstance(kwargs, ast.Name):
                return extras_require

            variable = self._find_variable_in_body(body, kwargs.id)
            if not isinstance(variable, (ast.Dict, ast.Call)):
                return extras_require

            if isinstance(variable, ast.Call):
                if not isinstance(variable.func, ast.Name):
                    return extras_require

                if variable.func.id != "dict":
                    return extras_require

                value = self._find_in_call(variable, "extras_require")
            else:
                value = self._find_in_dict(variable, "extras_require")

        if value is None:
            return extras_require

        if isinstance(value, ast.Dict):
            val: ast.expr | None
            for key, val in zip(value.keys, value.values):
                if not isinstance(key, ast.Str):
                    continue

                if isinstance(val, ast.Name):
                    val = self._find_variable_in_body(body, val.id)

                if isinstance(val, ast.List):
                    extras_require[key.s] = [
                        e.s for e in val.elts if isinstance(e, ast.Str)
                    ]
        elif isinstance(value, ast.Name):
            variable = self._find_variable_in_body(body, value.id)

            if variable is None or not isinstance(variable, ast.Dict):
                return extras_require

            for key, val in zip(variable.keys, variable.values):
                if not isinstance(key, ast.Str):
                    continue

                if isinstance(val, ast.Name):
                    val = self._find_variable_in_body(body, val.id)

                if isinstance(val, ast.List):
                    extras_require[key.s] = [
                        e.s for e in val.elts if isinstance(e, ast.Str)
                    ]

        return extras_require

    def _find_single_string(
        self, call: ast.Call, body: list[ast.stmt], name: str
    ) -> str | None:
        value = self._find_in_call(call, name)
        if value is None:
            # Trying to find in kwargs
            kwargs = self._find_call_kwargs(call)

            if kwargs is None or not isinstance(kwargs, ast.Name):
                return None

            variable = self._find_variable_in_body(body, kwargs.id)
            if not isinstance(variable, (ast.Dict, ast.Call)):
                return None

            if isinstance(variable, ast.Call):
                if not isinstance(variable.func, ast.Name):
                    return None

                if variable.func.id != "dict":
                    return None

                value = self._find_in_call(variable, name)
            else:
                value = self._find_in_dict(variable, name)

        if value is None:
            return None

        if isinstance(value, ast.Str):
            return value.s
        elif isinstance(value, ast.Name):
            variable = self._find_variable_in_body(body, value.id)

            if variable is not None and isinstance(variable, ast.Str):
                return variable.s

        return None

    def _find_in_call(self, call: ast.Call, name: str) -> Any | None:
        for keyword in call.keywords:
            if keyword.arg == name:
                return keyword.value
        return None

    def _find_call_kwargs(self, call: ast.Call) -> Any | None:
        kwargs = None
        for keyword in call.keywords:
            if keyword.arg is None:
                kwargs = keyword.value

        return kwargs

    def _find_variable_in_body(
        self, body: list[ast.stmt], name: str
    ) -> ast.expr | None:
        for elem in body:
            if not isinstance(elem, ast.Assign):
                continue

            for target in elem.targets:
                if not isinstance(target, ast.Name):
                    continue

                if target.id == name:
                    return elem.value

        return None

    def _find_in_dict(self, dict_: ast.Dict, name: str) -> ast.expr | None:
        for key, val in zip(dict_.keys, dict_.values):
            if isinstance(key, ast.Str) and key.s == name:
                return val

        return None
