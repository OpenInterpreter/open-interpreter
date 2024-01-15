#!/bin/bash

# Check if Rust is installed
if ! command -v rustc &> /dev/null
then
    echo "Rust is not installed. Installing now..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    source $HOME/.cargo/env
else
    echo "Rust is already installed."
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null
then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Define pyenv location
pyenv_root="$HOME/.pyenv/bin/pyenv"

# Check if pyenv is installed
if ! command -v $pyenv_root &> /dev/null
then
    echo "pyenv is not installed. Installing now..."
    brew install pyenv
else
    echo "pyenv is already installed."
fi

# Check if Python 3.11.7 is installed
if ! $pyenv_root versions | grep 3.11.7 &> /dev/null
then
    echo "Python 3.11.7 is not installed. Installing now..."
    $pyenv_root install 3.11.7
fi

$pyenv_root shell 3.11.7
brew install pipx
pipx ensurepath
pipx install open-interpreter
$pyenv_root shell --unset