#!/bin/bash

handle_error() {
    echo "Error: $1"
    exit 1
}

echo "Starting Open Interpreter installation..."
sleep 2
echo "This will take approximately 5 minutes..."
sleep 2

# Check if Rust is installed
if ! command -v rustc &> /dev/null
then
    echo "Rust is not installed. Installing now..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh || handle_error "Failed to install Rust."
else
    echo "Rust is already installed."
fi

# Install pyenv
curl https://pyenv.run | bash || handle_error "Failed to install pyenv."

# Define pyenv location
pyenv_root="$HOME/.pyenv/bin/pyenv"

# Install specific Python version using pyenv
$pyenv_root init || handle_error "Failed to initialize pyenv."
$pyenv_root install 3.11.7 --skip-existing || handle_error "Failed to install Python 3.11.7 with pyenv."
$pyenv_root shell 3.11.7 || handle_error "Failed to set Python version with pyenv."

pip install open-interpreter || handle_error "Failed to install open-interpreter."

# Unset the Python version
$pyenv_root shell --unset || handle_error "Failed to unset Python version with pyenv."

echo ""
echo "Open Interpreter has been installed. Run the following command to use it: "
echo ""
echo "interpreter"
