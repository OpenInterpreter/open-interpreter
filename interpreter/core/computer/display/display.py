import base64
import os
import pprint
import subprocess
import tempfile
import time
import warnings
from io import BytesIO

import matplotlib.pyplot as plt
import requests
from PIL import Image

from ..utils.recipient_utils import format_to_recipient

# Still experimenting with this
# from utils.get_active_window import get_active_window

try:
    import cv2
    import numpy as np
    import pyautogui
except:
    # Optional packages
    pass

from ..utils.computer_vision import find_text_in_image, pytesseract_get_text


class Display:
    def __init__(self, computer):
        self.computer = computer

        try:
            self.width, self.height = pyautogui.size()
        except:
            # pyautogui is an optional package, so it's okay if this fails
            pass

        self.api_base = "https://api.openinterpreter.com"

    def size(self):
        return pyautogui.size()

    def center(self):
        return self.width // 2, self.height // 2

    def view(self, show=True, quadrant=None):
        """
        Redirects to self.screenshot
        """
        return self.screenshot(show, quadrant)

    # def get_active_window(self):
    #     return get_active_window()

    def screenshot(self, show=True, quadrant=None, active_app_only=False):
        time.sleep(2)
        if not self.computer.emit_images:
            text = self.get_text()
            pp = pprint.PrettyPrinter(indent=4)
            pretty_text = pp.pformat(text)  # language models like it pretty!
            pretty_text = format_to_recipient(pretty_text, "assistant")
            print(pretty_text)
            print(
                format_to_recipient(
                    "To recieve the text above as a Python object, run computer.display.get_text()",
                    "assistant",
                )
            )
            return

        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)

        if quadrant == None:
            # Implement active_app_only!
            if active_app_only:
                region = self.get_active_window()["region"]
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
                # message = format_to_recipient("Taking a screenshot of the entire screen. This is not recommended. You (the language model assistant) will recieve it with low resolution.\n\nTo maximize performance, use computer.display.view(active_app_only=True). This will produce an ultra high quality image of the active application.", "assistant")
                # print(message)

        else:
            screen_width, screen_height = pyautogui.size()

            quadrant_width = screen_width // 2
            quadrant_height = screen_height // 2

            quadrant_coordinates = {
                1: (0, 0),
                2: (quadrant_width, 0),
                3: (0, quadrant_height),
                4: (quadrant_width, quadrant_height),
            }

            if quadrant in quadrant_coordinates:
                x, y = quadrant_coordinates[quadrant]
                screenshot = pyautogui.screenshot(
                    region=(x, y, quadrant_width, quadrant_height)
                )
            else:
                raise ValueError("Invalid quadrant. Choose between 1 and 4.")

        screenshot.save(temp_file.name)

        # Open the image file with PIL
        img = Image.open(temp_file.name)

        # Delete the temporary file
        try:
            os.remove(temp_file.name)
        except Exception as e:
            # On windows, this can fail due to permissions stuff??
            # (PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\killi\\AppData\\Local\\Temp\\tmpgc2wscpi.png')
            if self.computer.verbose:
                print(str(e))

        if show:
            # Show the image using matplotlib
            plt.imshow(np.array(img))

            with warnings.catch_warnings():
                # It displays an annoying message about Agg not being able to display something or WHATEVER
                warnings.simplefilter("ignore")
                plt.show()

        return img

    def find_text(self, text, screenshot=None):
        # Take a screenshot
        if screenshot == None:
            screenshot = self.screenshot(show=False)

        if not self.computer.offline:
            # Convert the screenshot to base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

            try:
                response = requests.post(
                    f'{self.api_base.strip("/")}/v0/point/text/',
                    json={"query": text, "base64": screenshot_base64},
                )
                response = response.json()
                return response
            except:
                print("Attempting to find the text locally.")

        # We'll only get here if 1) self.computer.offline = True, or the API failed

        # Find the text in the screenshot
        centers = find_text_in_image(screenshot, text)

        return centers

    def get_text(self, screenshot=None):
        # Take a screenshot
        if screenshot == None:
            screenshot = self.screenshot(show=False)

        if not self.computer.offline:
            # Convert the screenshot to base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

            try:
                response = requests.post(
                    f'{self.api_base.strip("/")}/v0/text/',
                    json={"base64": screenshot_base64},
                )
                response = response.json()
                return response
            except:
                print("Attempting to get the text locally.")

        # We'll only get here if 1) self.computer.offline = True, or the API failed

        return pytesseract_get_text(screenshot)

    # locate text should be moved here as well!
    def find_icon(self, query):
        message = self.computer.terminal.format_to_recipient(
            "Locating this icon will take ~30 seconds. We're working on speeding this up.",
            recipient="user",
        )
        print(message)

        # Take a screenshot
        screenshot = self.screenshot(show=False)

        # Convert the screenshot to base64
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

        try:
            response = requests.post(
                f'{self.api_base.strip("/")}/v0/point/',
                json={"query": query, "base64": screenshot_base64},
            )
            return response.json()
        except Exception as e:
            raise Exception(
                str(e)
                + "\n\nIcon locating API not avaliable, or we were unable to find the icon. Please try another method to find this icon."
            )
