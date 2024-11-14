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
    info "Installation complete! You can now use 'open-interpreter' from a new terminal window."
elif [[ "$OSTYPE" == "darwin"* ]]; then
    info "Installation complete! You can now use the 'open-interpreter' command."
    info "Make sure $BIN_DIR is in your PATH by adding this to your ~/.zshrc or ~/.bash_profile:"
    info "    export PATH=\"\$PATH:$BIN_DIR\""
else
    info "Installation complete! You can now use the 'open-interpreter' command."
    info "Make sure $BIN_DIR is in your PATH."
fi
