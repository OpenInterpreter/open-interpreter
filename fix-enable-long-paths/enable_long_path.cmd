@echo off
setlocal

REM Check if the script is running with administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges. Please run it as administrator.
    pause
    exit /b 1
)

REM Enable Long Paths Group Policy
echo Enabling Long Paths Group Policy...
gpedit /c "Computer Configuration\Administrative Templates\System\Filesystem" /v "Enable Win32 long paths" /t REG_DWORD /d 1 /f >nul 2>&1
if %errorLevel% neq 0 (
    echo Failed to enable Long Paths Group Policy.
    pause
    exit /b 1
)

REM Enable Long Paths in Registry Editor
echo Enabling Long Paths in Registry Editor...
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f >nul 2>&1
if %errorLevel% neq 0 (
    echo Failed to enable Long Paths in Registry Editor.
    pause
    exit /b 1
)

echo Long Paths support has been enabled successfully.
pause
exit /b 0
