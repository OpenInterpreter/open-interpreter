import base64
import os
import subprocess
import tempfile
from io import BytesIO

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pyautogui
import requests
from PIL import Image

from ..utils.computer_vision import find_text_in_image


class Display:
    # It hallucinates these:
    def __init__(self, computer):
        self.computer = computer
        self.width, self.height = pyautogui.size()
        self.api_base = "https://api.openinterpreter.com"

    def size(self):
        return pyautogui.size()

    def center(self):
        return self.width // 2, self.height // 2

    def screenshot(self, show=True, quadrant=None):
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)

        if quadrant == None:
            screenshot = pyautogui.screenshot()
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
        os.remove(temp_file.name)

        if show:
            # Show the image using matplotlib
            plt.imshow(np.array(img))
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
                    f'{self.api_base.strip("/")}/computer/display/text/',
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

    # locate text should be moved here as well!
    def find_icon(self, query):
        print(
            "Message for user: Locating this icon will take ~30 seconds. We're working on speeding this up."
        )

        # Take a screenshot
        screenshot = self.screenshot(show=False)

        # Convert the screenshot to base64
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        screenshot_base64 = base64.b64encode(buffered.getvalue()).decode()

        try:
            response = requests.post(
                f'{self.api_base.strip("/")}/computer/display/icon/',
                json={"query": query, "base64": screenshot_base64},
            )
            response = response.json()
        except Exception as e:
            if "SSLError" in str(e):
                print(
                    "Icon locating API not avaliable, or we were unable to find the icon. Please try another method to find this icon."
                )

        x, y = response[0]

        # In the future, if there's multiple, we should let the LLM pick by image, like how local text does

        # Convert x and y to fractions of the screenshot width and height
        x = x / screenshot.width
        y = y / screenshot.height

        return x, y
