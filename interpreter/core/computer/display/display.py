import base64
import os
import subprocess
import tempfile
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pyautogui
import requests
from PIL import Image

from ..utils.computer_vision import find_text_in_image


class Display:
    def __init__(self):
        self.is_retina = False
        try:
            # Get the output from the shell command
            output = subprocess.check_output(
                "system_profiler SPDisplaysDataType", shell=True
            ).decode("utf-8")
            # Check if the output contains 'Retina'
            if "retina" in output.lower():
                self.is_retina = True
        except Exception:
            pass

    def screenshot(self, show=True, quadrant=None):
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)

        if quadrant == None:
            screenshot = pyautogui.screenshot()
        else:
            try:
                screen_width, screen_height = pyautogui.size()
            except:
                raise EnvironmentError("Unable to determine screen size.")

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

    def find_text(self, text, index=None):
        # Take a screenshot
        img = self.screenshot(show=False)

        # Find the text in the screenshot
        centers, bounding_box_image = find_text_in_image(img, text)

        # If the text was found
        if centers:
            # This could be refactored to be more readable
            if len(centers) > 1:
                if index == None:
                    # Show the image using matplotlib
                    plt.imshow(np.array(bounding_box_image))
                    plt.show()
                    # Error so subsequent code is not executed
                    raise IndexError(
                        f"This text ('{text}') was found multiple times on screen."
                    )
                else:
                    center = centers[index]
            else:
                center = centers[0]

            x, y = center[0], center[1]

            if self.is_retina:
                x /= 2
                y /= 2

            return x, y

        else:
            plt.imshow(np.array(bounding_box_image))
            plt.show()
            raise ValueError(
                f"Your text ('{text}') was not found on the screen. Please try again."
            )

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

        api_base = "https://api.openinterpreter.com"
        api_base = "https://computer-tools.killianlucas1.repl.co/"

        try:
            response = requests.post(
                f'{api_base.strip("/")}/computer/display/',
                json={"query": query, "base64": screenshot_base64},
            )
            response = response.json()

            if "x" not in response:
                raise Exception(f"Failed to find '{query}' on the screen.")
        except Exception as e:
            if "SSLError" in str(e):
                print(
                    "Icon locating API not avaliable. Please try another method to click this icon."
                )

        x, y = response["x"], response["y"]

        if self.is_retina:
            x /= 2
            y /= 2

        return x, y
