import os
import platform
import random
import time

import pyautogui


class Keyboard:
    def write(self, text):
        pyautogui.write(text)

    def press(self, keys):
        pyautogui.press(keys)

    def hotkey(self, *args):
        modifiers = {"command", "control", "option", "shift"}
        if "darwin" in platform.system().lower() and len(args) == 2:
            # pyautogui.hotkey seems to not work, so we use applescript
            # Determine which argument is the keystroke and which is the modifier
            keystroke, modifier = args if args[0] not in modifiers else args[::-1]

            # Create the AppleScript
            script = f"""
            tell application "System Events"
                keystroke "{keystroke}" using {modifier}
            end tell
            """

            # Execute the AppleScript
            os.system("osascript -e '{}'".format(script))
        else:
            pyautogui.hotkey(*args, interval=0.15)

    def down(self, key):
        pyautogui.keyDown(key)

    def up(self, key):
        pyautogui.keyUp(key)
