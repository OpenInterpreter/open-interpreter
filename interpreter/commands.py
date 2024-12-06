import os
import platform
from typing import Any, Dict, Tuple, Type

from .profiles import Profile

SETTINGS: Dict[str, Tuple[Type, str]] = {
    "model": (str, "Model (e.g. claude-3-5-sonnet-20241022)"),
    "provider": (str, "Provider (e.g. anthropic, openai)"),
    "system_message": (str, "System message"),
    "tools": (list, "Enabled tools (comma-separated: interpreter,editor,gui)"),
    "auto_run": (bool, "Auto-run tools without confirmation"),
    "tool_calling": (bool, "Enable/disable tool calling"),
    "api_base": (str, "Custom API endpoint"),
    "api_key": (str, "API key"),
    "api_version": (str, "API version"),
    "temperature": (float, "Sampling temperature (0-1)"),
    "max_turns": (int, "Maximum conversation turns (-1 for unlimited)"),
}


def parse_value(value_str: str, type_hint: type) -> Any:
    """Convert string value to appropriate type"""
    if type_hint == bool:
        return value_str.lower() in ("true", "yes", "1", "on")
    if type_hint == list:
        return value_str.split(",")
    if type_hint == float:
        return float(value_str)
    if type_hint == int:
        return int(value_str)
    return value_str


def print_help() -> None:
    """Print help message for available commands"""
    print("Available Commands:")
    print("  /help                Show this help message")
    print("\nProfile Management:")
    print("  /profile show        Show current profile location")
    print(
        "  /profile save [path] Save settings to profile (default: ~/.openinterpreter)"
    )
    print("  /profile load <path> Load settings from profile")
    print("  /profile reset       Reset settings to defaults")
    print("\nSettings:")
    for name, (type_hint, help_text) in SETTINGS.items():
        if type_hint == bool:
            print(f"  /set {name} <true/false>    {help_text}")
        else:
            print(f"  /set {name} <value>    {help_text}")
    print()


class CommandHandler:
    def __init__(self, interpreter):
        self.interpreter = interpreter

    def handle_command(self, cmd: str, parts: list[str]) -> bool:
        """Handle / commands for controlling interpreter settings"""

        # Handle /help
        if cmd == "/help":
            print_help()
            return True

        # Handle /profile commands
        if cmd == "/profile":
            return self._handle_profile_command(parts)

        # Handle /set commands
        if cmd == "/set":
            return self._handle_set_command(parts)

        # Not a recognized command
        return False

    def _handle_profile_command(self, parts: list[str]) -> bool:
        if len(parts) < 2:
            print(
                "Error: Missing profile command. Use /help to see available commands."
            )
            return True

        subcmd = parts[1].lower()
        path = parts[2] if len(parts) > 2 else None

        if subcmd == "show":
            return self._handle_profile_show()
        elif subcmd == "save":
            return self._handle_profile_save(path)
        elif subcmd == "load":
            return self._handle_profile_load(path)
        elif subcmd == "reset":
            return self._handle_profile_reset()
        else:
            print(f"Unknown profile command: {subcmd}")
            print("Use /help to see available commands")
            return True

    def _handle_profile_show(self) -> bool:
        path = os.path.expanduser(self.interpreter._profile.profile_path)
        if not os.path.exists(path):
            print(f"Profile does not exist yet. Current path would be: {path}")
            print("Use /profile save to create it")
            return True

        if platform.system() == "Darwin":  # macOS
            os.system(f"open -R '{path}'")
        elif platform.system() == "Windows":
            os.system(f"explorer /select,{path}")
        else:
            print(f"Current profile path: {path}")
        return True

    def _handle_profile_save(self, path: str | None) -> bool:
        try:
            self.interpreter.save_profile(path)
        except Exception as e:
            print(f"Error saving profile: {str(e)}")
        return True

    def _handle_profile_load(self, path: str | None) -> bool:
        if not path:
            print("Error: Missing path for profile load")
            return True
        try:
            self.interpreter.load_profile(path)
            print(f"Settings loaded from: {path}")
        except Exception as e:
            print(f"Error loading profile: {str(e)}")
        return True

    def _handle_profile_reset(self) -> bool:
        # Create new profile with defaults
        self.interpreter._profile = Profile()
        # Update interpreter attributes
        for key, value in self.interpreter._profile.to_dict().items():
            if key != "profile":
                setattr(self.interpreter, key, value)

        print("Settings reset to defaults. To save this profile, use /profile save")
        return True

    def _handle_set_command(self, parts: list[str]) -> bool:
        if len(parts) < 2:
            print("Error: Missing parameter name")
            return True

        param = parts[1].lower()

        if param not in SETTINGS:
            print(f"Unknown parameter: {param}")
            return True

        if len(parts) < 3:
            print(f"Error: Missing value for {param}")
            return True

        value_str = parts[2]
        type_hint, _ = SETTINGS[param]
        try:
            self.interpreter._client = (
                None  # Reset client, in case they changed API key or API base
            )
            value = parse_value(value_str, type_hint)
            setattr(self.interpreter, param, value)
            print(f"Set {param} = {value}")
        except (ValueError, TypeError) as e:
            print(f"Error setting {param}: {str(e)}")
        return True
