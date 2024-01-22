#!/bin/bash

echo "Starting Open Interpreter installation..."
sleep 2
echo "This will take approximately 5 minutes..."
sleep 2


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

$pyenv_root install 3.11.7 --skip-existing

$pyenv_root shell 3.11.7

pip install open-interpreter

$pyenv_root shell --unset

echo ""
echo "Open Interpreter has been installed. Run the following command to use it: "
echo ""
echo "interpreter"