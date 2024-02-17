import os
from ...utils.lazy_import import lazy_import

# Lazy import of optional packages
pyperclip = lazy_import('pyperclip')

class Clipboard:
    def __init__(self, computer):
        self.computer = computer

        if os.name == "nt":
            self.modifier_key = "ctrl"
        else:
            self.modifier_key = "command"

    def view(self):
        """
        Returns the current content of on the clipboard.
        """
        return pyperclip.paste()

    def copy(self, text=None):
        """
        Copies the given text to the clipboard.
        """
        if text is not None:
            pyperclip.copy(text)
        else:
            self.computer.keyboard.hotkey(self.modifier_key, "c")

    def paste(self):
        """
        Pastes the current content of the clipboard.
        """
        self.computer.keyboard.hotkey(self.modifier_key, "v")
