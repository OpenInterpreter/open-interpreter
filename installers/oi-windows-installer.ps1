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