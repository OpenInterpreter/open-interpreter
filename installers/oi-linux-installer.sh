#!/bin/bash

# Check if Rust is installed
if ! command -v rustc &> /dev/null
then
    echo "Rust is not installed. Installing now..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
else
    echo "Rust is already installed."
fi

# Install pyenv
curl https://pyenv.run | bash

# Define pyenv location
pyenv_root="$HOME/.pyenv/bin/pyenv"

# Install specific Python version using pyenv
$pyenv_root install 3.11.7
$pyenv_root shell 3.11.7

version=$(lsb_release -rs)

if (( $(echo "$version 23.04" | awk '{print ($1 >= $2)}') )); then
    sudo apt update
    sudo apt install pipx
else
    python -m pip install --user pipx
fi

pipx ensurepath
pipx install open-interpreter

# Unset the Python version
$pyenv_root shell --unset