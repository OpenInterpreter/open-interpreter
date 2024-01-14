# Check if Python is installed and its version is not 3.11
$pythonVersion = & python --version 2>&1
if ($pythonVersion -notmatch "Python 3.11") {
    # Define the URL for the Python 3.11.7 installer
    $url = "https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe"
    $output = "C:\Temp\python-3.11.7-amd64.exe"

    # Create the Temp directory if it doesn't exist
    if (-not (Test-Path -Path C:\Temp)) {
        New-Item -Path C:\Temp -ItemType Directory
    }

    # Download the installer
    Invoke-WebRequest -Uri $url -OutFile $output

    # Install Python silently
    Start-Process -FilePath $output -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -PassThru

    # Cleanup: Remove the installer file after installation
    Remove-Item -Path $output -Force
}

# Install pyenv-win
pip install pyenv-win

# Set Python version to 3.11.7
pyenv install 3.11.7
pyenv global 3.11.7

# Check if Rust is installed
if (!(Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Output "Rust is not installed. Installing now..."
    Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe
    ./rustup-init.exe -y --default-toolchain stable
    Remove-Item rustup-init.exe
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
} else {
    Write-Output "Rust is already installed."
}

if (!(Get-Command scoop -ErrorAction SilentlyContinue)) {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
}

scoop install pipx
pipx ensurepath

pipx install open-interpreter