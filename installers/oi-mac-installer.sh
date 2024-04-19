#!/bin/bash

echo "Starting Open Interpreter installation..."
sleep 2
echo "This will take approximately 5 minutes..."
sleep 2

# Define pyenv location
pyenv_root="$HOME/.pyenv/bin/pyenv"

# Check if pyenv is installed
if ! command -v $pyenv_root &> /dev/null
then
    echo "pyenv is not installed. Installing now..."
    curl https://pyenv.run | zsh #zsh is the default shell for mac now. Changing this may cause install to fail 
else
    echo "pyenv is already installed."
fi

PYENV_VERSION='3.11.7'

$pyenv_root init

$pyenv_root install $PYENV_VERSION --skip-existing

$pyenv_root init

$pyenv_root global $PYENV_VERSION

$pyenv_root exec pip install open-interpreter

$pyenv_root shell $PYENV_VERSION 
$pyenv_root pip install open-interpreter
$pyenv_root shell --unset

echo ""
echo "Open Interpreter has been installed. Run the following command to use it: "
echo ""
echo "interpreter"