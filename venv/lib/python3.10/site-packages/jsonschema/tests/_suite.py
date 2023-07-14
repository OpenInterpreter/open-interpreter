"""
Python representations of the JSON Schema Test Suite tests.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json
import os
import re
import subprocess
import sys
import unittest

from attrs import field, frozen
from referencing import Registry
import referencing.jsonschema

if TYPE_CHECKING:
    import pyperf

from jsonschema.validators import _VALIDATORS
import jsonschema

_DELIMITERS = re.compile(r"[\W\- ]+")


def _find_suite():
    root = os.environ.get("JSON_SCHEMA_TEST_SUITE")
    if root is not None:
        return Path(root)

    root = Path(jsonschema.__file__).parent.parent / "json"
    if not root.is_dir():  # pragma: no cover
        raise ValueError(
            (
                "Can't find the JSON-Schema-Test-Suite directory. "
                "Set the 'JSON_SCHEMA_TEST_SUITE' environment "
                "variable or run the tests from alongside a checkout "
                "of the suite."
            ),
        )
    return root


@frozen
class Suite:

    _root: Path = field(factory=_find_suite)
    _remotes: referencing.jsonschema.SchemaRegistry = field(init=False)

    def __attrs_post_init__(self):
        jsonschema_suite = self._root.joinpath("bin", "jsonschema_suite")
        argv = [sys.executable, str(jsonschema_suite), "remotes"]
        remotes = subprocess.check_output(argv).decode("utf-8")

        resources = json.loads(remotes)

        li = "http://localhost:1234/locationIndependentIdentifierPre2019.json"
        li4 = "http://localhost:1234/locationIndependentIdentifierDraft4.json"

        registry = Registry().with_resources(
            [
                (
                    li,
                    referencing.jsonschema.DRAFT7.create_resource(
                        contents=resources.pop(li),
                    ),
                ),
                (
                    li4,
                    referencing.jsonschema.DRAFT4.create_resource(
                        contents=resources.pop(li4),
                    ),
                ),
            ],
        ).with_contents(
            resources.items(),
            default_specification=referencing.jsonschema.DRAFT202012,
        )
        object.__setattr__(self, "_remotes", registry)

    def benchmark(self, runner: pyperf.Runner):  # pragma: no cover
        for name, Validator in _VALIDATORS.items():
            self.version(name=name).benchmark(
                runner=runner,
                Validator=Validator,
            )

    def version(self, name) -> Version:
        return Version(
            name=name,
            path=self._root / "tests" / name,
            remotes=self._remotes,
        )


@frozen
class Version:

    _path: Path
    _remotes: referencing.jsonschema.SchemaRegistry

    name: str

    def benchmark(self, **kwargs):  # pragma: no cover
        for case in self.cases():
            case.benchmark(**kwargs)

    def cases(self) -> Iterable[_Case]:
        return self._cases_in(paths=self._path.glob("*.json"))

    def format_cases(self) -> Iterable[_Case]:
        return self._cases_in(paths=self._path.glob("optional/format/*.json"))

    def optional_cases_of(self, name: str) -> Iterable[_Case]:
        return self._cases_in(paths=[self._path / "optional" / f"{name}.json"])

    def to_unittest_testcase(self, *groups, **kwargs):
        name = kwargs.pop("name", "Test" + self.name.title().replace("-", ""))
        methods = {
            method.__name__: method
            for method in (
                test.to_unittest_method(**kwargs)
                for group in groups
                for case in group
                for test in case.tests
            )
        }
        cls = type(name, (unittest.TestCase,), methods)

        # We're doing crazy things, so if they go wrong, like a function
        # behaving differently on some other interpreter, just make them
        # not happen.
        with suppress(Exception):
            cls.__module__ = _someone_save_us_the_module_of_the_caller()

        return cls

    def _cases_in(self, paths: Iterable[Path]) -> Iterable[_Case]:
        for path in paths:
            for case in json.loads(path.read_text(encoding="utf-8")):
                yield _Case.from_dict(
                    case,
                    version=self,
                    subject=path.stem,
                    remotes=self._remotes,
                )


@frozen
class _Case:

    version: Version

    subject: str
    description: str
    schema: Mapping[str, Any] | bool
    tests: list[_Test]
    comment: str | None = None

    @classmethod
    def from_dict(cls, data, remotes, **kwargs):
        data.update(kwargs)
        tests = [
            _Test(
                version=data["version"],
                subject=data["subject"],
                case_description=data["description"],
                schema=data["schema"],
                remotes=remotes,
                **test,
            ) for test in data.pop("tests")
        ]
        return cls(tests=tests, **data)

    def benchmark(self, runner: pyperf.Runner, **kwargs):  # pragma: no cover
        for test in self.tests:
            runner.bench_func(
                test.fully_qualified_name,
                partial(test.validate_ignoring_errors, **kwargs),
            )


@frozen(repr=False)
class _Test:

    version: Version

    subject: str
    case_description: str
    description: str

    data: Any
    schema: Mapping[str, Any] | bool

    valid: bool

    _remotes: referencing.jsonschema.SchemaRegistry

    comment: str | None = None

    def __repr__(self):  # pragma: no cover
        return f"<Test {self.fully_qualified_name}>"

    @property
    def fully_qualified_name(self):  # pragma: no cover
        return " > ".join(
            [
                self.version.name,
                self.subject,
                self.case_description,
                self.description,
            ],
        )

    def to_unittest_method(self, skip=lambda test: None, **kwargs):
        if self.valid:
            def fn(this):
                self.validate(**kwargs)
        else:
            def fn(this):
                with this.assertRaises(jsonschema.ValidationError):
                    self.validate(**kwargs)

        fn.__name__ = "_".join(
            [
                "test",
                _DELIMITERS.sub("_", self.subject),
                _DELIMITERS.sub("_", self.case_description),
                _DELIMITERS.sub("_", self.description),
            ],
        )
        reason = skip(self)
        if reason is None or os.environ.get("JSON_SCHEMA_DEBUG", "0") != "0":
            return fn
        elif os.environ.get("JSON_SCHEMA_EXPECTED_FAILURES", "0") != "0":  # pragma: no cover  # noqa: E501
            return unittest.expectedFailure(fn)
        else:
            return unittest.skip(reason)(fn)

    def validate(self, Validator, **kwargs):
        Validator.check_schema(self.schema)
        validator = Validator(
            schema=self.schema,
            registry=self._remotes,
            **kwargs,
        )
        if os.environ.get("JSON_SCHEMA_DEBUG", "0") != "0":  # pragma: no cover
            breakpoint()
        validator.validate(instance=self.data)

    def validate_ignoring_errors(self, Validator):  # pragma: no cover
        with suppress(jsonschema.ValidationError):
            self.validate(Validator=Validator)


def _someone_save_us_the_module_of_the_caller():
    """
    The FQON of the module 2nd stack frames up from here.

    This is intended to allow us to dynamically return test case classes that
    are indistinguishable from being defined in the module that wants them.

    Otherwise, trial will mis-print the FQON, and copy pasting it won't re-run
    the class that really is running.

    Save us all, this is all so so so so so terrible.
    """

    return sys._getframe(2).f_globals["__name__"]
