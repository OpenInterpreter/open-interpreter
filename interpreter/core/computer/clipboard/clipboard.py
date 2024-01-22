import os

try:
    import pyperclip
except:
    # Optional package
    pass


class Clipboard:
    def __init__(self, computer):
        self.computer = computer

        if os.name == "nt":
            self.modifier_key = "ctrl"
        else:
            self.modifier_key = "command"

    def view(self):
        return pyperclip.paste()

    def copy(self, text=None):
        if text is not None:
            pyperclip.copy(text)
        else:
            self.computer.keyboard.hotkey(self.modifier_key, "c")

    def paste(self):
        self.computer.keyboard.hotkey(self.modifier_key, "v")
