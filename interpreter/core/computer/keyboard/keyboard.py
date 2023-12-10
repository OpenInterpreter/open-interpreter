import os
import platform
import random
import time

import pyautogui


class Keyboard:
    def write(self, text):
        # Split the text into words
        words = text.split(" ")

        # Type each word with a space after it, unless it's the last word
        for i, word in enumerate(words):
            # Type the word
            pyautogui.write(word)
            # Add a space after the word if it's not the last word
            if i != len(words) - 1:
                pyautogui.write(" ")
            # Add a delay after each word to simulate ChatGPT
            time.sleep(random.uniform(0.1, 0.3))

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
            pyautogui.hotkey(*args)

    def down(self, key):
        pyautogui.keyDown(key)

    def up(self, key):
        pyautogui.keyUp(key)
