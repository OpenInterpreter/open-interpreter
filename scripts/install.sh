#!/usr/bin/env bash

# Exit on error
set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print error messages
error() {
    echo "Error: $1" >&2
    exit 1
}

# Function to print status messages
info() {
    echo "→ $1"
}

# Function for cleanup on failure
cleanup() {
    info "Cleaning up after installation failure..."
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
    fi
}

# Set trap for cleanup on script failure
trap cleanup ERR

# Install uv if it's not already installed
if ! command_exists uv; then
    info "Installing uv package manager..."
    if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command_exists curl; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        elif command_exists wget; then
            wget -qO- https://astral.sh/uv/install.sh | sh
        else
            error "Neither curl nor wget found. Please install either curl or wget first."
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    else
        error "Unsupported operating system"
    fi
fi

# Function to check Python version compatibility
check_python_version() {
    local version=$1
    if [[ $version =~ ^3\.(9|1[0-9])(\.[0-9]+)?$ ]]; then
        return 0
    fi
    return 1
}

# Find existing compatible Python version or install one
info "Checking for compatible Python (>=3.9,<4)..."
existing_python=""
while IFS= read -r version; do
    if check_python_version "$version"; then
        existing_python=$version
        break
    fi
done < <(uv python list 2>/dev/null || true)

if [ -z "$existing_python" ]; then
    info "Installing Python 3.11..."
    uv python install 3.11 || error "Failed to install Python"
    existing_python="3.11"
fi

info "Using Python $existing_python"

# Function to get user data directory
get_user_data_dir() {
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "$USERPROFILE/.openinterpreter"
    elif [[ -n "${XDG_DATA_HOME}" ]]; then
        echo "${XDG_DATA_HOME}/openinterpreter"
    else
        echo "$HOME/.openinterpreter"
    fi
}

# Define installation directories
INSTALL_DIR="$(get_user_data_dir)"
VENV_DIR="$INSTALL_DIR/venv"

# Define bin directory for executables
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    BIN_DIR="$INSTALL_DIR/bin"
    ACTIVATE_SCRIPT="$VENV_DIR/Scripts/activate"
    WRAPPER_SCRIPT="$BIN_DIR/open-interpreter.cmd"
else
    BIN_DIR="$HOME/.local/bin"
    ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
    WRAPPER_SCRIPT="$BIN_DIR/open-interpreter"
fi

# Create installation directories
info "Creating installation directories..."
mkdir -p "$INSTALL_DIR" "$BIN_DIR" || error "Failed to create installation directories"

# Create a virtual environment with the selected Python version
info "Creating virtual environment..."
uv venv --python "$existing_python" "$VENV_DIR" || error "Failed to create virtual environment"

# Create platform-specific wrapper script
info "Creating wrapper script..."
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows CMD wrapper
    cat > "$WRAPPER_SCRIPT" << EOF
@echo off
call "$ACTIVATE_SCRIPT"
python -m interpreter %*
EOF
    
    # Also create a PowerShell wrapper
    WRAPPER_PS1="$BIN_DIR/open-interpreter.ps1"
    cat > "$WRAPPER_PS1" << EOF
& "$ACTIVATE_SCRIPT"
python -m interpreter @args
EOF

    # Add to User PATH if not already present
    powershell -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';$BIN_DIR', 'User')"
    info "Added $BIN_DIR to User PATH"
else
    # Unix-like systems (Linux/macOS)
    cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
source "$ACTIVATE_SCRIPT"
python -m interpreter "\$@"
EOF
    chmod +x "$WRAPPER_SCRIPT" || error "Failed to make wrapper script executable"
fi

# Platform-specific final instructions
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    info "Installation complete! You can now use 'interpreter' from a new terminal window."
elif [[ "$OSTYPE" == "darwin"* ]]; then
    info "Installation complete! You can now use the 'interpreter' command."
    info "Would you like to add $BIN_DIR to your PATH? [y/N] "
    read -r add_to_path
    if [[ "$add_to_path" =~ ^[Yy]$ ]]; then
        if [[ -f "$HOME/.zshrc" ]]; then
            echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$HOME/.zshrc"
            info "Added to ~/.zshrc. Please restart your terminal or run: source ~/.zshrc"
        elif [[ -f "$HOME/.bash_profile" ]]; then
            echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$HOME/.bash_profile"
            info "Added to ~/.bash_profile. Please restart your terminal or run: source ~/.bash_profile"
        else
            info "Could not find ~/.zshrc or ~/.bash_profile. Please manually add to your shell's config:"
            info "    export PATH=\"\$PATH:$BIN_DIR\""
        fi
    else
        info "You can manually add $BIN_DIR to your PATH by adding this to ~/.zshrc or ~/.bash_profile:"
        info "    export PATH=\"\$PATH:$BIN_DIR\""
    fi
else
    info "Installation complete! You can now use the 'interpreter' command."
    info "Would you like to add $BIN_DIR to your PATH? [y/N] "
    read -r add_to_path
    if [[ "$add_to_path" =~ ^[Yy]$ ]]; then
        if [[ -f "$HOME/.bashrc" ]]; then
            echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$HOME/.bashrc"
            info "Added to ~/.bashrc. Please restart your terminal or run: source ~/.bashrc"
        else
            info "Could not find ~/.bashrc. Please manually add to your shell's config:"
            info "    export PATH=\"\$PATH:$BIN_DIR\""
        fi
    else
        info "You can manually add $BIN_DIR to your PATH by adding this to ~/.bashrc:"
        info "    export PATH=\"\$PATH:$BIN_DIR\""
    fi
fi

# Offer shell integration
info "Would you like to install our experimental shell integration? This allows you to use your shell as a chatbox, with your shell history as context. [y/N] "
read -r install_shell_integration
if [[ "$install_shell_integration" =~ ^[Yy]$ ]]; then
    if command_exists interpreter-shell; then
        interpreter-shell
        info "Shell integration installed successfully! Restart your shell to activate it. Run interpreter-uninstall-shell to remove it."
    else
        error "Could not find interpreter-shell command. Please ensure Open Interpreter was installed correctly."
    fi
fi
