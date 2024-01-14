#!/bin/bash

# Check if Rust is installed
if ! command -v rustc &> /dev/null
then
    echo "Rust is not installed. Installing now..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
else
    echo "Rust is already installed."
fi

version=$(lsb_release -rs)

if (( $(echo "$version 23.04" | awk '{print ($1 >= $2)}') )); then
    sudo apt update
    sudo apt install pipx
    pipx ensurepath
else
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
fi

pipx install open-interpreter