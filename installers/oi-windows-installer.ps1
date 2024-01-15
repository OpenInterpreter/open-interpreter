# Check if pyenv is installed
$pyenvRoot = "${env:USERPROFILE}\.pyenv\pyenv-win"
$pyenvBin = "$pyenvRoot\bin\pyenv.bat"
if (!(Get-Command $pyenvBin -ErrorAction SilentlyContinue)) {
    # Download and install pyenv-win
    $pyenvInstaller = "install-pyenv-win.ps1"
    $pyenvInstallUrl = "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1"
    Invoke-WebRequest -Uri $pyenvInstallUrl -OutFile $pyenvInstaller
    & powershell -ExecutionPolicy Bypass -File $pyenvInstaller
    Remove-Item -Path $pyenvInstaller
}

# Check if Rust is installed
if (!(Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Output "Rust is not installed. Installing now..."
    $rustupUrl = "https://win.rustup.rs/x86_64"
    $rustupFile = "rustup-init.exe"
    Invoke-WebRequest -Uri $rustupUrl -OutFile $rustupFile
    Start-Process -FilePath .\$rustupFile -ArgumentList '-y', '--default-toolchain', 'stable' -Wait
    Remove-Item -Path .\$rustupFile
}

# Check if Scoop is installed
if (!(Get-Command scoop -ErrorAction SilentlyContinue)) {
    Write-Output "Scoop is not installed. Installing now..."
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    Invoke-Expression (New-Object System.Net.WebClient).DownloadString('https://get.scoop.sh')
}

# Install pipx using Scoop
scoop install pipx
& pipx ensurepath

# Use the full path to pyenv to install Python
& "$pyenvBin" install 3.11.7

# Turn on this Python and install OI
$env:PYENV_VERSION="3.11.7"
& pipx install open-interpreter

# Get us out of this vers of Python (which was just used to setup OI, which should stay in that vers of Python...?)
Remove-Item Env:\PYENV_VERSION