import asyncio
import base64
import platform
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import PIL
import pytest

from computer_use.tools.computer import (
    MAX_SCALING_TARGETS,
    ComputerTool,
    ScalingSource,
    ToolError,
    chunks,
    smooth_move_to,
)


@pytest.fixture
def computer_tool():
    """Fixture to create a ComputerTool instance with mocked screen size"""
    with patch("pyautogui.size", return_value=(1920, 1080)):
        tool = ComputerTool()
        tool._screenshot_delay = 0  # Speed up tests by removing delay
        return tool


def test_initialization(computer_tool):
    """Test ComputerTool initialization"""
    assert computer_tool.name == "computer"
    assert computer_tool.api_type == "computer_20241022"
    assert computer_tool.width == 1920
    assert computer_tool.height == 1080
    assert computer_tool.display_num is None
    assert computer_tool._display_offset_x == 0


def test_options(computer_tool):
    """Test options property"""
    options = computer_tool.options
    assert isinstance(options["display_width_px"], int)
    assert isinstance(options["display_height_px"], int)
    assert options["display_number"] is None


@pytest.mark.asyncio
async def test_key_action():
    """Test keyboard actions"""
    mock_img = MagicMock()
    mock_img.save = MagicMock()
    mock_img.resize = MagicMock(return_value=mock_img)

    fake_image_data = b"PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header

    with patch("pyautogui.size", return_value=(1920, 1080)), patch(
        "pyautogui.press"
    ) as mock_press, patch(
        "pyautogui.screenshot", return_value=mock_img
    ) as mock_screenshot, patch(
        "PIL.Image.open", return_value=mock_img
    ), patch(
        "builtins.open", mock_open(read_data=fake_image_data)
    ):
        tool = ComputerTool()
        tool._screenshot_delay = 0

        # Test single key
        await tool(action="key", text="a")
        mock_press.assert_called_with("a")

        # Test key combination on non-Darwin
        with patch("platform.system", return_value="Linux"):
            await tool(action="key", text="ctrl+c")


@pytest.mark.asyncio
async def test_type_action(computer_tool):
    """Test typing action"""
    mock_img = MagicMock()
    mock_img.save = MagicMock()
    mock_img.resize = MagicMock(return_value=mock_img)

    fake_image_data = b"PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header

    with patch("pyautogui.write") as mock_write, patch(
        "pyautogui.screenshot", return_value=mock_img
    ) as mock_screenshot, patch("PIL.Image.open", return_value=mock_img), patch(
        "builtins.open", mock_open(read_data=fake_image_data)
    ):
        await computer_tool(action="type", text="Hello")
        mock_write.assert_called_with("Hello", interval=0.012)


@pytest.mark.asyncio
async def test_mouse_actions(computer_tool):
    """Test mouse-related actions"""
    mock_img = MagicMock()
    mock_img.save = MagicMock()
    mock_img.resize = MagicMock(return_value=mock_img)

    fake_image_data = b"PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header

    with patch("pyautogui.moveTo") as mock_move, patch(
        "pyautogui.click"
    ) as mock_click, patch(
        "pyautogui.screenshot", return_value=mock_img
    ) as mock_screenshot, patch(
        "PIL.Image.open", return_value=mock_img
    ), patch(
        "builtins.open", mock_open(read_data=fake_image_data)
    ):
        # Test mouse move
        await computer_tool(action="mouse_move", coordinate=[100, 100])
        assert mock_move.called

        # Test clicks
        await computer_tool(action="left_click")
        mock_click.assert_called_with(button="left")

        await computer_tool(action="right_click")
        mock_click.assert_called_with(button="right")

        # Test double click
        await computer_tool(action="double_click")
        # Should click twice
        assert mock_click.call_count >= 2


@pytest.mark.asyncio
async def test_screenshot(computer_tool):
    """Test screenshot functionality"""
    # Create a mock image with all required attributes
    mock_img = MagicMock()
    mock_img.save = MagicMock()
    mock_img.resize = MagicMock(return_value=mock_img)

    # Create mock file data that PIL will read
    fake_image_data = b"PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header

    # Mock PIL.Image.open to return our mock image
    with patch("PIL.Image.open", return_value=mock_img) as mock_pil_open, patch(
        "pyautogui.screenshot", return_value=mock_img
    ) as mock_screenshot, patch("builtins.open", mock_open(read_data=fake_image_data)):
        result = await computer_tool.screenshot()

        # Verify calls were made
        assert mock_screenshot.called
        assert mock_img.save.called
        assert mock_pil_open.called

        # Verify result
        assert hasattr(result, "base64_image")
        assert result.base64_image is not None

        # Check that resize was called with expected parameters
        mock_img.resize.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_actions(computer_tool):
    """Test error handling"""
    with pytest.raises(ToolError):
        await computer_tool(action="invalid_action")

    with pytest.raises(ToolError):
        await computer_tool(action="mouse_move")  # Missing coordinate

    with pytest.raises(ToolError):
        await computer_tool(action="mouse_move", coordinate=[100])  # Invalid coordinate


def test_scale_coordinates(computer_tool):
    """Test coordinate scaling"""
    # Test valid scaling
    x, y = computer_tool.scale_coordinates(ScalingSource.API, 100, 100)
    assert isinstance(x, int)
    assert isinstance(y, int)

    # Test out of bounds
    with pytest.raises(ToolError):
        computer_tool.scale_coordinates(ScalingSource.API, 2000, 2000)


def test_smooth_move_to():
    """Test smooth mouse movement"""
    with patch("pyautogui.moveTo") as mock_move, patch(
        "pyautogui.position", return_value=(0, 0)
    ):
        smooth_move_to(100, 100, duration=0.1)
        assert mock_move.called
        assert (
            mock_move.call_count > 1
        )  # Should make multiple calls for smooth movement


def test_chunks_utility():
    """Test chunks helper function"""
    result = chunks("Hello", 2)
    assert result == ["He", "ll", "o"]
    assert len(result) == 3
