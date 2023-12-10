import os
import platform
import random
import time

import pyautogui

pyautogui.FAILSAFE = False


class Keyboard:
    def write(self, text):
        # Split the text into words
        words = text.split(" ")

        # Type each word
        for word in words:
            # Type the word
            pyautogui.write(word)
            # Add a delay after each word
            time.sleep(random.uniform(0.1, 0.3))

    def press(self, keys):
        pyautogui.press(keys)

    def hotkey(self, *args):
        if "darwin" in platform.system().lower():
            # For some reason, application focus or something, we need to do this for spotlight
            # only if they passed in "command", "space" or "command", " ", or those in another order
            if set(args) == {"command", " "} or set(args) == {"command", "space"}:
                os.system(
                    """
                osascript -e 'tell application "System Events" to keystroke " " using {command down}'
                """
                )
            else:
                pyautogui.hotkey(*args)

    def down(self, key):
        pyautogui.keyDown(key)

    def up(self, key):
        pyautogui.keyUp(key)
