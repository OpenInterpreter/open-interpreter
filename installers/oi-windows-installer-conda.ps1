# Define variables
$condaInstallerUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$condaInstallerPath = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"
$condaPath = "$env:USERPROFILE\Miniconda3"
$envName = "oi"
$pythonVersion = "3.11.7"
$packageName = "open-interpreter litellm openai"
$desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), 'Open Interpreter.lnk')
$condaExePath = "$condaPath\Scripts\conda.exe"

# URL of the .ico file
$icoUrl = "https://raw.githubusercontent.com/OpenInterpreter/open-interpreter/main/docs/assets/favicon.ico"
$icoPath = "$env:TEMP\open-interpreter.ico"

# Function to download a file with progress
function DownloadFileWithProgress {
    param (
        [string]$url,
        [string]$output
    )
    
    $request = [System.Net.HttpWebRequest]::Create($url)
    $response = $request.GetResponse()
    $totalLength = $response.ContentLength
    $readBytes = 0
    $buffer = New-Object byte[] 1024
    $percentComplete = 0
    
    $stream = $response.GetResponseStream()
    $fileStream = New-Object IO.FileStream ($output, [System.IO.FileMode]::Create)
    
    try {
        while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $fileStream.Write($buffer, 0, $read)
            $readBytes += $read
            $newPercentComplete = [math]::Round(($readBytes / $totalLength) * 100)
            
            if ($newPercentComplete -ne $percentComplete) {
                $percentComplete = $newPercentComplete
                Write-Progress -Activity "Downloading Miniconda Installer" -Status "$percentComplete% Complete" -PercentComplete $percentComplete
            }
        }
    } finally {
        $fileStream.Close()
        $stream.Close()
    }
    
    Write-Progress -Activity "Downloading Miniconda Installer" -Completed
}

# Download the .ico file
Write-Host "Downloading icon file..."
DownloadFileWithProgress -url $icoUrl -output $icoPath

# Function to check if Conda is installed
function Test-CondaInstalled {
    try {
        & conda --version > $null 2>&1
        return $true
    } catch {
        return $false
    }
}

# Check if Conda is installed
if (-Not (Test-CondaInstalled)) {
    Write-Host "Conda is not installed."

    # Download Miniconda installer if not already downloaded
    if (-Not (Test-Path $condaInstallerPath)) {
        DownloadFileWithProgress -url $condaInstallerUrl -output $condaInstallerPath
    } else {
        Write-Host "Miniconda installer already downloaded."
    }

    # Run the Miniconda installer with messages before and after
    Write-Host "Starting Miniconda installation... (there will be no progress bar)"
    Start-Process -Wait -FilePath $condaInstallerPath -ArgumentList "/InstallationType=JustMe", "/AddToPath=1", "/RegisterPython=0", "/S", "/D=$condaPath"
    Write-Host "Miniconda installation complete."

    # Ensure Conda is in the PATH for the current session
    $env:Path += ";$condaPath\Scripts;$condaPath"
} else {
    Write-Host "Conda is already installed."
}

# Create and activate the Conda environment, and show progress
Write-Host "Creating Conda environment '$envName'..."
& $condaExePath create -n $envName python=$pythonVersion -y
Write-Host "Conda environment '$envName' created."

# Dynamically generate the user's paths for the shortcut
$userCondaScriptsPath = "$condaPath\Scripts"
$userEnvName = $envName

# Create a shortcut on the desktop to activate the environment, install OpenInterpreter, and run it
$targetPath = "$env:SystemRoot\System32\cmd.exe"
$arguments = "/K `"$userCondaScriptsPath\activate.bat` $userEnvName && echo Updating Open Interpreter && pip install -U $packageName && cls && echo Launching Open Interpreter && interpreter`""

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($desktopPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $env:USERPROFILE
$shortcut.WindowStyle = 1  # Normal window
$shortcut.IconLocation = $icoPath
$shortcut.Save()

Write-Host "Shortcut 'Open Interpreter.lnk' has been created on the desktop with the custom icon."

# Open the shortcut
Start-Process -FilePath $desktopPath
