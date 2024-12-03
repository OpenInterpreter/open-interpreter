#!/bin/bash

# Exit on any error
set -e

# Configuration
VENV_DIR="$HOME/.openinterpreter"
INSTALL_DIR="$HOME/.local/bin"
PYTHON_VERSION="3.12"
REPO_URL="https://github.com/OpenInterpreter/open-interpreter.git"
BRANCH="development"
COMMANDS=("interpreter" "i" "wtf")

# Print error message and exit
error_exit() {
    echo "Error: $1" >&2
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" > /dev/null 2>&1
}

# Get installation path of a command
get_command_path() {
    which "$1" 2>/dev/null || echo ""
}

# Handle existing installations
check_and_handle_existing() {
    local found_existing=false
    local paths_to_remove=()
    
    # Check for pip installation
    if pip show open-interpreter >/dev/null 2>&1; then
        found_existing=true
        echo "Found existing pip installation of open-interpreter"
        read -p "Would you like to uninstall it? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Uninstalling open-interpreter via pip..."
            pip uninstall -y open-interpreter || echo "Failed to uninstall via pip"
        fi
    fi
    
    # Check for command installations
    for cmd in "${COMMANDS[@]}"; do
        local cmd_path=$(get_command_path "$cmd")
        if [ -n "$cmd_path" ]; then
            found_existing=true
            echo "Found existing installation of '$cmd' at: $cmd_path"
            paths_to_remove+=("$cmd_path")
        fi
    done
    
    # If command installations were found, ask to remove them
    if [ ${#paths_to_remove[@]} -gt 0 ]; then
        echo
        echo "Found existing command installations:"
        printf '%s\n' "${paths_to_remove[@]}"
        read -p "Would you like to remove these files? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for path in "${paths_to_remove[@]}"; do
                echo "Removing: $path"
                rm -f "$path" || echo "Failed to remove: $path"
            done
        fi
    fi
    
    # If any existing installations were found but user chose not to remove them,
    # ask if they want to continue
    if [ "$found_existing" = true ]; then
        echo
        read -p "Continue with installation anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            exit 0
        fi
    fi
}

# Install uv package manager
install_uv() {
    echo "Installing uv package manager..."
    if command_exists curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command_exists wget; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        error_exit "Neither curl nor wget is available. Please install one of them first."
    fi
    
    # Update PATH to include cargo binaries
    export PATH="$HOME/.cargo/bin:$PATH"
    
    # Verify uv installation
    if ! command_exists uv; then
        error_exit "Failed to install uv package manager"
    fi
}

# Create virtual environment and install package
setup_environment() {
    echo "Creating virtual environment..."
    mkdir -p "$VENV_DIR"
    uv venv --python "$PYTHON_VERSION" "$VENV_DIR/venv"
    
    echo "Installing open-interpreter from $BRANCH branch..."
    uv pip install --python "$VENV_DIR/venv/bin/python" "git+$REPO_URL@$BRANCH"
}

# Create symbolic links
create_symlinks() {
    echo "Creating command symlinks..."
    mkdir -p "$INSTALL_DIR"
    for cmd in "${COMMANDS[@]}"; do
        ln -sf "$VENV_DIR/venv/bin/$cmd" "$INSTALL_DIR/$cmd"
    done
}

# Main installation process
main() {
    echo "Starting Open Interpreter installation..."
    
    # Check and handle existing installations first
    check_and_handle_existing
    
    if ! command_exists uv; then
        install_uv
    fi
    
    setup_environment
    create_symlinks
    
    echo
    echo "Installation complete! The commands '${COMMANDS[*]}' are now available."
    echo "If they're not found, you may need to add ~/.local/bin to your PATH:"
    echo 'export PATH="$HOME/.local/bin:$PATH"'
}

# Run main function
main