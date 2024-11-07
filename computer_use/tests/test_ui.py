import pytest

from ..ui.markdown import format_markdown
from ..ui.tool import ToolUI


def test_markdown_formatting():
    # Test basic markdown formatting
    text = "**bold** and *italic*"
    formatted = format_markdown(text)
    assert formatted != text  # The text should be transformed
    assert "bold" in formatted
    assert "italic" in formatted


def test_code_block_formatting():
    # Test code block formatting
    code = """```python
def hello():
    print("Hello, World!")
```"""
    formatted = format_markdown(code)
    assert "```" not in formatted  # Code block markers should be processed
    assert "def hello():" in formatted


def test_tool_ui_initialization():
    ui = ToolUI()
    assert ui is not None
    assert hasattr(ui, "display")


def test_tool_ui_display():
    ui = ToolUI()
    test_message = "Test message"
    # Should not raise any exceptions
    ui.display(test_message)


def test_tool_ui_error_handling():
    ui = ToolUI()
    test_error = "Test error message"
    # Should not raise any exceptions
    ui.display_error(test_error)


def test_tool_ui_progress():
    ui = ToolUI()
    # Test progress indication
    ui.start_progress("Testing progress")
    ui.update_progress(50)
    ui.end_progress()
    # If we reach here without exceptions, test passes


@pytest.mark.parametrize(
    "input_text,expected_contains",
    [
        ("**bold**", "bold"),
        ("*italic*", "italic"),
        ("# heading", "heading"),
        ("`code`", "code"),
    ],
)
def test_various_markdown_formats(input_text, expected_contains):
    formatted = format_markdown(input_text)
    assert expected_contains in formatted
