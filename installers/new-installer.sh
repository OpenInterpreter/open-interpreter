#!/bin/bash

set -e

# Configuration
REPO_URL="https://github.com/OpenInterpreter/open-interpreter.git"
BRANCH="development"
PYTHON_VERSION="3.12"

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

# Direct installation using uv with specific Python version
echo "Installing package..."
uv pip install --python "$PYTHON_VERSION" "git+$REPO_URL@$BRANCH"

echo
echo "Installation complete!"