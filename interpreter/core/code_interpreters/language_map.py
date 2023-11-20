from .languages.applescript import AppleScript
from .languages.html import HTML
from .languages.javascript import JavaScript
from .languages.powershell import PowerShell
from .languages.python import Python
from .languages.r import R
from .languages.shell import Shell

language_map = {
    "python": Python,
    "bash": Shell,
    "shell": Shell,
    "sh": Shell,
    "zsh": Shell,
    "javascript": JavaScript,
    "html": HTML,
    "applescript": AppleScript,
    "r": R,
    "powershell": PowerShell,
}
