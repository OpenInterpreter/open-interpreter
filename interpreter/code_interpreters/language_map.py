from .languages.python import Python
from .languages.shell import Shell
from .languages.javascript import JavaScript
from .languages.html import HTML
from .languages.applescript import AppleScript
from .languages.r import R
from .languages.powershell import PowerShell


language_map = {
    "python": Python,
    "bash": Shell,
    "shell": Shell,
    "javascript": JavaScript,
    "html": HTML,
    "applescript": AppleScript,
    "r": R,
    "powershell": PowerShell,
}
