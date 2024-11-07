import pytest

from ..tools.base import BaseTool
from ..tools.collection import ToolCollection


class DummyTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "dummy"

    def execute(self, **kwargs):
        return "dummy executed"


def test_tool_collection_initialization():
    collection = ToolCollection()
    assert collection is not None
    assert hasattr(collection, "tools")
    assert isinstance(collection.tools, dict)


def test_tool_registration():
    collection = ToolCollection()
    dummy_tool = DummyTool()
    collection.register_tool(dummy_tool)
    assert "dummy" in collection.tools
    assert collection.tools["dummy"] == dummy_tool


def test_tool_execution():
    collection = ToolCollection()
    dummy_tool = DummyTool()
    collection.register_tool(dummy_tool)
    result = collection.execute_tool("dummy")
    assert result == "dummy executed"


def test_invalid_tool_execution():
    collection = ToolCollection()
    with pytest.raises(KeyError):
        collection.execute_tool("nonexistent_tool")


def test_tool_listing():
    collection = ToolCollection()
    dummy_tool = DummyTool()
    collection.register_tool(dummy_tool)
    tools = collection.list_tools()
    assert isinstance(tools, list)
    assert "dummy" in tools


def test_tool_removal():
    collection = ToolCollection()
    dummy_tool = DummyTool()
    collection.register_tool(dummy_tool)
    collection.remove_tool("dummy")
    assert "dummy" not in collection.tools


def test_duplicate_tool_registration():
    collection = ToolCollection()
    dummy_tool1 = DummyTool()
    dummy_tool2 = DummyTool()
    collection.register_tool(dummy_tool1)
    # Should replace the existing tool without raising an exception
    collection.register_tool(dummy_tool2)
    assert collection.tools["dummy"] == dummy_tool2
