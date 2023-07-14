class RopeError(Exception):
    """Base exception for rope"""


class ResourceNotFoundError(RopeError):
    """Resource not found exception"""


class RefactoringError(RopeError):
    """Errors for performing a refactoring"""


class InterruptedTaskError(RopeError):
    """The task has been interrupted"""


class HistoryError(RopeError):
    """Errors for history undo/redo operations"""


class ModuleNotFoundError(RopeError):
    """Module not found exception"""


class AttributeNotFoundError(RopeError):
    """Attribute not found exception"""


class NameNotFoundError(RopeError):
    """Name not found exception"""


class BadIdentifierError(RopeError):
    """The name cannot be resolved"""


class ModuleSyntaxError(RopeError):
    """Module has syntax errors

    The `filename` and `lineno` fields indicate where the error has
    occurred.

    """

    def __init__(self, filename, lineno, message):
        self.filename = filename
        self.lineno = lineno
        self.message_ = message
        super().__init__(
            f"Syntax error in file <{filename}> line <{lineno}>: {message}"
        )


class ModuleDecodeError(RopeError):
    """Cannot decode module"""

    def __init__(self, filename, message):
        self.filename = filename
        self.message_ = message
        super().__init__(f"Cannot decode file <{filename}>: {message}")
