

from .languages.python import Python
from .languages.shell import Shell
from .languages.javascript import JavaScript
from .languages.html import HTML
from .languages.applescript import AppleScript
from .languages.r import R

def create_code_interpreter(language):
    # Case in-sensitive
    language = language.lower()

    language_map = {
        "python": Python,
        "bash": Shell,
        "shell": Shell,
        "javascript": JavaScript,
        "html": HTML,
        "applescript": AppleScript,
        "r": R,
    }

    try:
        CodeInterpreter = language_map[language]
        return CodeInterpreter()
    except KeyError:
        raise ValueError(f"Unknown or unsupported language: {language}")
