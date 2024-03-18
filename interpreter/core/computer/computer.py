import json

from .ai.ai import Ai
from .browser.browser import Browser
from .calendar.calendar import Calendar
from .clipboard.clipboard import Clipboard
from .contacts.contacts import Contacts
from .display.display import Display
from .docs.docs import Docs
from .keyboard.keyboard import Keyboard
from .mail.mail import Mail
from .mouse.mouse import Mouse
from .os.os import Os
from .skills.skills import Skills
from .sms.sms import SMS
from .terminal.terminal import Terminal


class Computer:
    def __init__(self, interpreter):
        self.interpreter = interpreter

        self.terminal = Terminal(self)

        self.offline = False
        self.verbose = False
        self.debug = False

        self.mouse = Mouse(self)
        self.keyboard = Keyboard(self)
        self.display = Display(self)
        self.clipboard = Clipboard(self)
        self.mail = Mail(self)
        self.sms = SMS(self)
        self.calendar = Calendar(self)
        self.contacts = Contacts(self)
        self.browser = Browser(self)
        self.os = Os(self)
        self.skills = Skills(self)
        self.docs = Docs(self)
        self.ai = Ai(self)

        self.emit_images = True
        self.api_base = "https://api.openinterpreter.com/v0"
        self.save_skills = True

        self.import_computer_api = True
        self._has_imported_computer_api = False  # Because we only want to do this once

    # Shortcut for computer.terminal.languages
    @property
    def languages(self):
        return self.terminal.languages

    @languages.setter
    def languages(self, value):
        self.terminal.languages = value

    def run(self, *args, **kwargs):
        """
        Shortcut for computer.terminal.run
        """
        return self.terminal.run(*args, **kwargs)

    def exec(self, code):
        """
        Shortcut for computer.terminal.run("shell", code)
        It has hallucinated this.
        """
        return self.terminal.run("shell", code)

    def stop(self):
        """
        Shortcut for computer.terminal.stop
        """
        return self.terminal.stop()

    def terminate(self):
        """
        Shortcut for computer.terminal.terminate
        """
        return self.terminal.terminate()

    def screenshot(self, *args, **kwargs):
        """
        Shortcut for computer.display.screenshot
        """
        return self.display.screenshot(*args, **kwargs)

    def to_dict(self):
        def json_serializable(obj):
            try:
                json.dumps(obj)
                return True
            except:
                return False

        return {k: v for k, v in self.__dict__.items() if json_serializable(v)}

    def load_dict(self, data_dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
