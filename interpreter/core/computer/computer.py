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
        for language_name in list(self._active_languages.keys()):
            language = self._active_languages[language_name]
            if (
                language
            ):  # Not sure why this is None sometimes. We should look into this
                language.terminate()
            del self._active_languages[language_name]


computer = Computer()
