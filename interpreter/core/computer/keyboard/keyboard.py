import os
import platform
import random
import time

import pyautogui


class Keyboard:
    def write(self, text):
        time.sleep(0.15)
        pyautogui.write(text)
        time.sleep(0.15)

    def press(self, keys):
        time.sleep(0.15)
        pyautogui.press(keys)
        time.sleep(0.15)

    def hotkey(self, *args):
        time.sleep(0.15)
        modifiers = {
            "command": "command down",
            "control": "control down",
            "option": "option down",
            "shift": "shift down",
        }
        if "darwin" in platform.system().lower() and len(args) == 2:
            # pyautogui.hotkey seems to not work, so we use applescript
            # Determine which argument is the keystroke and which is the modifier
            keystroke, modifier = args if args[0] not in modifiers else args[::-1]

            # Map the modifier to the one that AppleScript expects
            modifier = modifiers[modifier]

            if keystroke == "space":
                keystroke = " "

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
        time.sleep(0.15)

    def down(self, key):
        time.sleep(0.15)
        pyautogui.keyDown(key)
        time.sleep(0.15)

    def up(self, key):
        time.sleep(0.15)
        pyautogui.keyUp(key)
        time.sleep(0.15)
