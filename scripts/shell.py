"""
Shell Integration Setup for Open Interpreter

This script installs shell integration that:
1. Maintains a transcript of terminal interactions (commands and their outputs)
2. Captures both successful commands and their results
3. Routes unknown commands to the interpreter with full terminal history as context
4. Works with both zsh and bash shells

The history is stored in ~/.shell_history_with_output in a chat-like format:
user: <command>
computer: <output>
"""

import os
import re
from pathlib import Path


def get_shell_config():
    """Determine user's shell and return the appropriate config file path."""
    shell = os.environ.get("SHELL", "").lower()
    home = str(Path.home())

    if "zsh" in shell:
        return os.path.join(home, ".zshrc"), "zsh"
    elif "bash" in shell:
        bash_rc = os.path.join(home, ".bashrc")
        bash_profile = os.path.join(home, ".bash_profile")

        if os.path.exists(bash_rc):
            return bash_rc, "bash"
        elif os.path.exists(bash_profile):
            return bash_profile, "bash"

    return None, None


def get_shell_script(shell_type):
    """Return the appropriate shell script based on shell type."""
    base_script = r"""# Create log file if it doesn't exist
touch ~/.shell_history_with_output

# Function to capture terminal interaction
function capture_output() {
    local cmd=$1
    # Use LC_ALL=C to force ASCII output and handle encoding issues
    exec 1> >(LC_ALL=C tee >(LC_ALL=C sed -e $'s/\x1B\[[0-9;]*[a-zA-Z]//g' -e $'s/\x1B\[[0-9;]*[mGKHF]//g' -e $'s/[^[:print:]\t\n]//g' >> ~/.shell_history_with_output))
    exec 2> >(LC_ALL=C tee >(LC_ALL=C sed -e $'s/\x1B\[[0-9;]*[a-zA-Z]//g' -e $'s/\x1B\[[0-9;]*[mGKHF]//g' -e $'s/[^[:print:]\t\n]//g' >> ~/.shell_history_with_output))
    
    echo "user: $cmd" >> ~/.shell_history_with_output
    echo "computer:" >> ~/.shell_history_with_output
    
    # Trim history file if it exceeds 20K characters
    if [ $(wc -c < ~/.shell_history_with_output) -gt 20000 ]; then
        # Keep only the last 15K characters to prevent frequent trimming
        tail -c 15000 ~/.shell_history_with_output > ~/.shell_history_with_output.tmp
        mv ~/.shell_history_with_output.tmp ~/.shell_history_with_output
    fi
}

# After the command completes, reset the output redirection
function reset_output() {
    exec 1>&1
    exec 2>&2
}

# Command not found handler that pipes context to interpreter
command_not_found_handler() {
    local cmd=$1
    
    # Capture output in temp file, display unstripped version, then process and append stripped version
    output_file=$(mktemp)
    # Add trap to handle SIGINT (Ctrl+C) gracefully
    trap "rm -f $output_file; return 0" INT
    
    # Force ASCII output and clean non-printable characters
    LC_ALL=C interpreter --input "$(cat ~/.shell_history_with_output)" --instructions "You are in FAST mode. Be ultra-concise. Determine what the user is trying to do (most recently) and help them." 2>&1 | \
        tee "$output_file"
    LC_ALL=C cat "$output_file" | LC_ALL=C sed \
        -e $'s/\x1B\[[0-9;]*[a-zA-Z]//g' \
        -e $'s/\x1B\[[0-9;]*[mGKHF]//g' \
        -e $'s/\]633;[^]]*\]//g' \
        -e 's/^[[:space:]\.]*//;s/[[:space:]\.]*$//' \
        -e 's/─\{3,\}//g' \
        -e $'s/[^[:print:]\t\n]//g' \
        >> ~/.shell_history_with_output
    
    # Clean up and remove the trap
    trap - INT
    rm -f "$output_file"
    return 0
}

# Hook into preexec"""

    if shell_type == "zsh":
        return (
            base_script
            + '\npreexec() {\n    capture_output "$1"\n}\n\npostexec() {\n    reset_output\n}\n'
        )
    elif shell_type == "bash":
        return (
            base_script
            + '\ntrap \'capture_output "$(HISTTIMEFORMAT= history 1 | sed "s/^[ ]*[0-9]*[ ]*//")" \' DEBUG\n'
            + "trap 'reset_output' RETURN\n"
        )
    return None


def main():
    """Install or reinstall the shell integration."""
    print("Starting installation...")
    config_path, shell_type = get_shell_config()

    if not config_path or not shell_type:
        print("Could not determine your shell configuration.")
        print(
            "Please visit docs.openinterpreter.com/shell for manual installation instructions."
        )
        return

    # Clean up history file
    history_file = os.path.expanduser("~/.shell_history_with_output")
    if os.path.exists(history_file):
        os.remove(history_file)

    # Create fresh history file
    with open(history_file, "w") as f:
        f.write("")

    # Read existing config
    try:
        with open(config_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""

    start_marker = "### <openinterpreter> ###"
    end_marker = "### </openinterpreter> ###"

    # Check if markers exist
    if start_marker in content:
        response = input(
            "Open Interpreter shell integration appears to be already installed. Would you like to reinstall? (y/n): "
        )
        if response.lower() != "y":
            print("Installation cancelled.")
            return

        # Remove existing installation
        pattern = f"{start_marker}.*?{end_marker}"
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    # Get appropriate shell script
    shell_script = get_shell_script(shell_type)

    # Create new content
    new_content = (
        f"{content.rstrip()}\n\n{start_marker}\n{shell_script}\n{end_marker}\n"
    )

    # Write back to config file
    try:
        with open(config_path, "w") as f:
            f.write(new_content)
        print(
            f"Successfully installed Open Interpreter shell integration to {config_path}"
        )
        print("Please restart your shell or run 'source ~/.zshrc' to apply changes.")
    except Exception as e:
        print(f"Error writing to {config_path}: {e}")
        print(
            "Please visit docs.openinterpreter.com for manual installation instructions."
        )


if __name__ == "__main__":
    main()
