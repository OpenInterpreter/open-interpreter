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
    curl https://pyenv.run | bash
else
    echo "pyenv is already installed."
fi

$pyenv_root init

$pyenv_root install 3.11.7 --skip-existing

# do we need to do this? it works on a computer where shell didn't, but it doesn't install the command to `interpreter`
# PYENV_VERSION=3.11.7 $pyenv_root exec pip install open-interpreter

$pyenv_root shell 3.11.7

pip install open-interpreter

$pyenv_root shell --unset

echo ""
echo "Open Interpreter has been installed. Run the following command to use it: "
echo ""
echo "interpreter"