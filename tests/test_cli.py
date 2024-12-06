import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from interpreter.cli import _parse_list_arg, load_interpreter, parse_args
from interpreter.profiles import Profile


def test_version_flag():
    # Test --version flag
    result = subprocess.run(
        ["interpreter", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Open Interpreter" in result.stdout


def test_help_flag():
    # Test --help flag
    result = subprocess.run(["interpreter", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()


def test_parse_list_arg():
    # Test parsing JSON list
    assert _parse_list_arg('["a", "b", "c"]') == ["a", "b", "c"]

    # Test parsing comma-separated list
    assert _parse_list_arg("a,b,c") == ["a", "b", "c"]

    # Test empty input
    assert _parse_list_arg("") == []

    # Test whitespace handling
    assert _parse_list_arg("a, b,  c  ") == ["a", "b", "c"]


def test_model_flag():
    # Test --model flag
    with patch.object(sys, "argv", ["interpreter", "--model", "gpt-4"]):
        args = parse_args()
        assert args["model"] == "gpt-4"


def test_api_key_flag():
    # Test --api-key flag
    test_key = "test-key-123"
    with patch.object(sys, "argv", ["interpreter", "--api-key", test_key]):
        args = parse_args()
        assert args["api_key"] == test_key


def test_temperature_flag():
    # Test --temperature flag
    with patch.object(sys, "argv", ["interpreter", "--temperature", "0.7"]):
        args = parse_args()
        assert args["temperature"] == "0.7"


def test_auto_run_flag():
    # Test --auto-run flag
    with patch.object(sys, "argv", ["interpreter", "--auto-run"]):
        args = parse_args()
        assert args["auto_run"] is True


def test_debug_flag():
    # Test --debug flag
    with patch.object(sys, "argv", ["interpreter", "--debug"]):
        args = parse_args()
        assert args["debug"] is True


def test_tool_calling_flags():
    # Test --no-tool-calling flag
    with patch.object(sys, "argv", ["interpreter", "--no-tool-calling"]):
        args = parse_args()
        assert args["tool_calling"] is False


def test_interactive_flags():
    # Test --interactive flag
    with patch.object(sys, "argv", ["interpreter", "--interactive"]):
        args = parse_args()
        assert args["interactive"] is True

    # Test --no-interactive flag
    with patch.object(sys, "argv", ["interpreter", "--no-interactive"]):
        args = parse_args()
        assert args["interactive"] is False


def test_direct_input():
    # Test direct input without flags
    test_input = "Hello interpreter"
    with patch.object(sys, "argv", ["interpreter", test_input]):
        args = parse_args()
        assert args["input"] == f"i {test_input}"


@pytest.mark.asyncio
async def test_load_interpreter():
    # Test interpreter loading with custom settings
    args = {"model": "gpt-4", "temperature": 0.7, "auto_run": True, "debug": True}
    interpreter = load_interpreter(args)

    assert interpreter.model == "gpt-4"
    assert interpreter.temperature == 0.7
    assert interpreter.auto_run is True
    assert interpreter.debug is True
