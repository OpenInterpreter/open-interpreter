import os

import pyautogui
import pyperclip


class Clipboard:
    def __init__(self):
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
            pyautogui.hotkey(self.modifier_key, "c", interval=0.15)

    def paste(self):
        pyautogui.hotkey(self.modifier_key, "v", interval=0.15)
