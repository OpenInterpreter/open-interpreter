from __future__ import annotations

from poetry.console.commands.command import Command


class CheckCommand(Command):
    name = "check"
    description = "Checks the validity of the <comment>pyproject.toml</comment> file."

    def validate_classifiers(
        self, project_classifiers: set[str]
    ) -> tuple[list[str], list[str]]:
        """Identify unrecognized and deprecated trove classifiers.

        A fully-qualified classifier is a string delimited by `` :: `` separators. To
        make the error message more readable we need to have visual clues to
        materialize the start and end of a classifier string. That way the user can
        easily copy and paste it from the messages while reducing mistakes because of
        extra spaces.

        We use ``!r`` (``repr()``) for classifiers and list of classifiers for
        consistency. That way all strings will be rendered with the same kind of quotes
        (i.e. simple tick: ``'``).
        """
        from trove_classifiers import classifiers
        from trove_classifiers import deprecated_classifiers

        errors = []
        warnings = []

        unrecognized = sorted(
            project_classifiers - set(classifiers) - set(deprecated_classifiers)
        )
        # Allow "Private ::" classifiers as recommended on PyPI and the packaging guide
        # to allow users to avoid accidentally publishing private packages to PyPI.
        # https://pypi.org/classifiers/
        unrecognized = [u for u in unrecognized if not u.startswith("Private ::")]
        if unrecognized:
            errors.append(f"Unrecognized classifiers: {unrecognized!r}.")

        deprecated = sorted(
            project_classifiers.intersection(set(deprecated_classifiers))
        )
        if deprecated:
            for old_classifier in deprecated:
                new_classifiers = deprecated_classifiers[old_classifier]
                if new_classifiers:
                    message = (
                        f"Deprecated classifier {old_classifier!r}. "
                        f"Must be replaced by {new_classifiers!r}."
                    )
                else:
                    message = (
                        f"Deprecated classifier {old_classifier!r}. Must be removed."
                    )
                warnings.append(message)

        return errors, warnings

    def handle(self) -> int:
        from poetry.factory import Factory
        from poetry.pyproject.toml import PyProjectTOML

        # Load poetry config and display errors, if any
        poetry_file = self.poetry.file.path
        config = PyProjectTOML(poetry_file).poetry_config
        check_result = Factory.validate(config, strict=True)

        # Validate trove classifiers
        project_classifiers = set(config.get("classifiers", []))
        errors, warnings = self.validate_classifiers(project_classifiers)
        check_result["errors"].extend(errors)
        check_result["warnings"].extend(warnings)

        if not check_result["errors"] and not check_result["warnings"]:
            self.info("All set!")

            return 0

        for error in check_result["errors"]:
            self.line_error(f"<error>Error: {error}</error>")

        for error in check_result["warnings"]:
            self.line_error(f"<warning>Warning: {error}</warning>")

        return 1
