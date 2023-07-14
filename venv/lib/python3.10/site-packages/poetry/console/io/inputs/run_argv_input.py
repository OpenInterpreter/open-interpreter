from __future__ import annotations

from typing import TYPE_CHECKING

from cleo.io.inputs.argv_input import ArgvInput


if TYPE_CHECKING:
    from cleo.io.inputs.definition import Definition


class RunArgvInput(ArgvInput):
    def __init__(
        self,
        argv: list[str] | None = None,
        definition: Definition | None = None,
    ) -> None:
        super().__init__(argv, definition=definition)

        self._parameter_options: list[str] = []

    @property
    def first_argument(self) -> str | None:
        return "run"

    def add_parameter_option(self, name: str) -> None:
        self._parameter_options.append(name)

    def has_parameter_option(
        self, values: str | list[str], only_params: bool = False
    ) -> bool:
        if not isinstance(values, list):
            values = [values]

        for token in self._tokens:
            if only_params and token == "--":
                return False

            for value in values:
                if value not in self._parameter_options:
                    continue

                # Options with values:
                # For long options, test for '--option=' at beginning
                # For short options, test for '-o' at beginning
                leading = value + "=" if value.startswith("--") else value

                if token == value or leading != "" and token.startswith(leading):
                    return True

        return False

    def _parse(self) -> None:
        parse_options = True
        self._parsed = self._tokens[:]

        try:
            token = self._parsed.pop(0)
        except IndexError:
            token = None

        while token is not None:
            if parse_options and token == "":
                self._parse_argument(token)
            elif parse_options and token == "--":
                parse_options = False
            elif parse_options and token.find("--") == 0:
                if token in self._parameter_options:
                    self._parse_long_option(token)
                else:
                    self._parse_argument(token)
            elif parse_options and token[0] == "-" and token != "-":
                if token in self._parameter_options:
                    self._parse_short_option(token)
                else:
                    self._parse_argument(token)
            else:
                self._parse_argument(token)

            try:
                token = self._parsed.pop(0)
            except IndexError:
                token = None
