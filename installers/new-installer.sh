#!/bin/bash

set -e

# Configuration
REPO_URL="https://github.com/OpenInterpreter/open-interpreter.git"
BRANCH="development"
PYTHON_VERSION="3.12"
VENV_DIR="$HOME/.openinterpreter/venv"

# Install uv if not present
if ! command -v uv > /dev/null 2>&1; then
    echo "Installing uv package manager..."
    if command -v curl > /dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        wget -qO- https://astral.sh/uv/install.sh | sh
    fi
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python using uv
echo "Installing Python $PYTHON_VERSION..."
uv python install "$PYTHON_VERSION"

# Create virtual environment
echo "Creating virtual environment..."
mkdir -p "$HOME/.openinterpreter"
uv venv --python "$PYTHON_VERSION" "$VENV_DIR"

# Install package into the venv
echo "Installing package..."
uv pip install --python "$VENV_DIR/bin/python" "git+$REPO_URL@$BRANCH"

# Update PATH for current session and future sessions
export PATH="$VENV_DIR/bin:$PATH"
SHELL_CONFIG="$HOME/.bashrc"
case "$SHELL" in
    *zsh*)
        SHELL_CONFIG="$HOME/.zshrc"
        ;;
esac
echo "export PATH=\"$VENV_DIR/bin:\$PATH\"" >> "$SHELL_CONFIG"

echo "Testing..."
echo "Say hello world!" | interpreter --model gpt-4o-mini

echo
echo "Installation complete!"