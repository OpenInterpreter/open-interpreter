import os

from .base import CLIResult, ToolResult
from .collection import ToolCollection
from .computer import ComputerTool
from .edit import EditTool

# Temporarily always use simple bash
if True or os.environ.get("INTERPRETER_SIMPLE_BASH", "").lower() == "true":
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
