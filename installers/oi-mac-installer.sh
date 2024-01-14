#!/bin/bash

# Check if Homebrew is installed
if ! command -v brew &> /dev/null
then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null
then
    echo "pyenv is not installed. Installing now..."
    brew install pyenv
else
    echo "pyenv is already installed."
fi

# Check if Python 3.11.5 is installed
if ! pyenv versions | grep 3.11.5 &> /dev/null
then
    echo "Python 3.11.5 is not installed. Installing now..."
    pyenv install 3.11.5
fi

# Set Python 3.11.5 as the default version
echo "Setting Python 3.11.5 as the default version..."
pyenv global 3.11.5

# Check if Rust is installed
if ! command -v rustc &> /dev/null
then
    echo "Rust is not installed. Installing now..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    source $HOME/.cargo/env
else
    echo "Rust is already installed."
fi

brew install pipx
pipx ensurepath

pipx install open-interpreter