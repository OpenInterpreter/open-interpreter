import os

from .base import CLIResult, ToolResult
from .collection import ToolCollection
from .computer import ComputerTool
from .edit import EditTool

if os.environ.get("INTERPRETER_SIMPLE_BASH") == "true":
    from .simple_bash import BashTool
else:
    from .bash import BashTool

__ALL__ = [
    BashTool,
    CLIResult,
    ComputerTool,
    EditTool,
    ToolCollection,
    ToolResult,
]
