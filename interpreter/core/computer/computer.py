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


class Computer:
    def __init__(self):
        self.languages = [Python, Shell, JavaScript, HTML, AppleScript, R, PowerShell]
        self._active_languages = {}

    def run(self, language, code):
        # To reduce footprint, I think Shell should use the same kernel as Python.
        # There should be a way to share kernels in the future I think.
        # Is this bad?
        if language_map[language] == Shell:
            code = "!" + code
            language = "python"

        if language not in self._active_languages:
            self._active_languages[language] = language_map[language]()
        try:
            yield from self._active_languages[language].run(code)
        except GeneratorExit:
            self.stop()

    def stop(self):
        for language in self._active_languages.values():
            language.stop()

    def terminate(self):
        for language in self._active_languages.values():
            language.terminate()
        self._active_languages = {}


computer = Computer()
