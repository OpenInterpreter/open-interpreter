"""
Shell Integration Uninstaller for Open Interpreter

This script removes the shell integration previously installed by shell.py
by removing the content between the marker comments in the shell config file.
"""

import os
import re
from pathlib import Path


def get_shell_config():
    """Determine user's shell and return the appropriate config file path."""
    shell = os.environ.get("SHELL", "").lower()
    home = str(Path.home())

    if "zsh" in shell:
        return os.path.join(home, ".zshrc")
    elif "bash" in shell:
        bash_rc = os.path.join(home, ".bashrc")
        bash_profile = os.path.join(home, ".bash_profile")

        if os.path.exists(bash_rc):
            return bash_rc
        elif os.path.exists(bash_profile):
            return bash_profile

    return None


def main():
    """Remove the shell integration."""
    print("Starting uninstallation...")
    config_path = get_shell_config()

    if not config_path:
        print("Could not determine your shell configuration.")
        return

    # Read existing config
    try:
        with open(config_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Config file {config_path} not found.")
        return

    start_marker = "### <openinterpreter> ###"
    end_marker = "### </openinterpreter> ###"

    # Check if markers exist
    if start_marker not in content:
        print("Open Interpreter shell integration not found in config file.")
        return

    # Remove the shell integration section
    pattern = f"{start_marker}.*?{end_marker}"
    new_content = re.sub(pattern, "", content, flags=re.DOTALL)

    # Clean up any extra blank lines
    new_content = re.sub(r"\n\s*\n\s*\n", "\n\n", new_content)

    # Write back to config file
    try:
        with open(config_path, "w") as f:
            f.write(new_content)
        print(
            f"Successfully removed Open Interpreter shell integration from {config_path}"
        )
        print("Please restart your shell for changes to take effect.")

        # Remove history file if it exists
        history_file = os.path.expanduser("~/.shell_history_with_output")
        if os.path.exists(history_file):
            os.remove(history_file)
            print("Removed shell history file.")

    except Exception as e:
        print(f"Error writing to {config_path}: {e}")


if __name__ == "__main__":
    main()
