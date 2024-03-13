import base64
import os
import platform
import pprint
import time
import warnings
from contextlib import redirect_stdout
from io import BytesIO

import requests

from ...utils.lazy_import import lazy_import
from ..utils.recipient_utils import format_to_recipient

# Still experimenting with this
# from utils.get_active_window import get_active_window

# Lazy import of optional packages
pyautogui = lazy_import("pyautogui")
np = lazy_import("numpy")
plt = lazy_import("matplotlib.pyplot")

from ..utils.computer_vision import find_text_in_image, pytesseract_get_text


class Display:
    def __init__(self, computer):
        self.computer = computer
        # set width and height to None initially to prevent pyautogui from importing until it's needed
        self._width = None
        self._height = None
        self._hashes = {}

    # We use properties here so that this code only executes when height/width are accessed for the first time
    @property
    def width(self):
        if self._width is None:
            self._width, _ = pyautogui.size()
        return self._width

    @property
    def height(self):
        if self._height is None:
            _, self._height = pyautogui.size()
        return self._height

    def size(self):
        """
        Returns the current screen size as a tuple (width, height).
        """
        return pyautogui.size()

    def center(self):
        """
        Calculates and returns the center point of the screen as a tuple (x, y).
        """
        return self.width // 2, self.height // 2

    def view(self, show=True, quadrant=None):
        """
        Redirects to self.screenshot
        """
        return self.screenshot(show, quadrant)

    # def get_active_window(self):
    #     return get_active_window()

    def screenshot(
        self, show=True, quadrant=None, active_app_only=False, force_image=False
    ):
        """
        Shows you what's on the screen by taking a screenshot of the entire screen or a specified quadrant. Returns a `pil_image` `in case you need it (rarely). **You almost always want to do this first!**
        """
        if not self.computer.emit_images and force_image == False:
            text = self.get_text_as_list_of_lists()
            pp = pprint.PrettyPrinter(indent=4)
            pretty_text = pp.pformat(text)  # language models like it pretty!
            pretty_text = format_to_recipient(pretty_text, "assistant")
            print(pretty_text)
            print(
                format_to_recipient(
                    "To recieve the text above as a Python object, run computer.display.get_text_as_list_of_lists()",
                    "assistant",
                )
            )
            return

        if quadrant == None:
            # Implement active_app_only!
            if active_app_only:
                region = self.get_active_window()["region"]
                screenshot = pyautogui.screenshot(region=region)
            else:
                if platform.system() == "Darwin":
                    screenshot = take_screenshot_to_pil()
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

        # Open the image file with PIL
        # IPython interactive mode auto-displays plots, causing RGBA handling issues, possibly MacOS-specific.
        screenshot = screenshot.convert("RGB")

        if show:
            # Show the image using matplotlib
            plt.imshow(np.array(screenshot))

            with warnings.catch_warnings():
                # It displays an annoying message about Agg not being able to display something or WHATEVER
                warnings.simplefilter("ignore")
                plt.show()

        return screenshot

    def find(self, description, screenshot=None):
        if description.startswith('"') and description.endswith('"'):
            return self.find_text(description.strip('"'), screenshot)
        else:
            try:
                if self.computer.debug:
                    print("DEBUG MODE ON")
                    print("NUM HASHES:", len(self._hashes))
                else:
                    message = format_to_recipient(
                        "Locating this icon will take ~15 seconds. Subsequent icons should be found more quickly.",
                        recipient="user",
                    )
                    print(message)

                if len(self._hashes) > 5000:
                    self._hashes = dict(list(self._hashes.items())[-5000:])

                from .point.point import point

                result = point(
                    description, screenshot, self.computer.debug, self._hashes
                )

                return result
            except:
                if self.computer.debug:
                    # We want to know these bugs lmao
                    raise
                if self.computer.offline:
                    raise
                message = format_to_recipient(
                    "Locating this icon will take ~30 seconds. We're working on speeding this up.",
                    recipient="user",
                )
                print(message)

                # Take a screenshot
                if screenshot == None:
                    screenshot = self.screenshot(show=False)

                # Downscale the screenshot to 1920x1080
                screenshot = screenshot.resize((1920, 1080))

                # Convert the screenshot to base64
                buffered = BytesIO()
                screenshot.save(buffered, format="PNG")
                screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

                try:
                    response = requests.post(
                        f'{self.computer.api_base.strip("/")}/point/',
                        json={"query": description, "base64": screenshot_base64},
                    )
                    return response.json()
                except Exception as e:
                    raise Exception(
                        str(e)
                        + "\n\nIcon locating API not available, or we were unable to find the icon. Please try another method to find this icon."
                    )

    def find_text(self, text, screenshot=None):
        """
        Searches for specified text within a screenshot or the current screen if no screenshot is provided.
        """
        if screenshot == None:
            screenshot = self.screenshot(show=False)

        if not self.computer.offline:
            # Convert the screenshot to base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

            try:
                response = requests.post(
                    f'{self.computer.api_base.strip("/")}/point/text/',
                    json={"query": text, "base64": screenshot_base64},
                )
                response = response.json()
                return response
            except:
                print("Attempting to find the text locally.")

        # We'll only get here if 1) self.computer.offline = True, or the API failed

        # Find the text in the screenshot
        centers = find_text_in_image(screenshot, text, self.computer.debug)

        return [
            {"coordinates": center, "text": "", "similarity": 1} for center in centers
        ]  # Have it deliver the text properly soon.

    def get_text_as_list_of_lists(self, screenshot=None):
        """
        Extracts and returns text from a screenshot or the current screen as a list of lists, each representing a line of text.
        """
        if screenshot == None:
            screenshot = self.screenshot(show=False, force_image=True)

        if not self.computer.offline:
            # Convert the screenshot to base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

            try:
                response = requests.post(
                    f'{self.computer.api_base.strip("/")}/text/',
                    json={"base64": screenshot_base64},
                )
                response = response.json()
                return response
            except:
                print("Attempting to get the text locally.")

        # We'll only get here if 1) self.computer.offline = True, or the API failed

        try:
            return pytesseract_get_text(screenshot)
        except:
            raise Exception(
                "Failed to find text locally.\n\nTo find text in order to use the mouse, please make sure you've installed `pytesseract` along with the Tesseract executable (see this Stack Overflow answer for help installing Tesseract: https://stackoverflow.com/questions/50951955/pytesseract-tesseractnotfound-error-tesseract-is-not-installed-or-its-not-i)."
            )


import io
import subprocess

from PIL import Image


def take_screenshot_to_pil(filename="temp_screenshot.png"):
    # Capture the screenshot and save it to a temporary file
    subprocess.run(["screencapture", "-x", filename], check=True)

    # Open the image file with PIL
    with open(filename, "rb") as f:
        image_data = f.read()
    image = Image.open(io.BytesIO(image_data))

    # Optionally, delete the temporary file if you don't need it after loading
    os.remove(filename)

    return image
