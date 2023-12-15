import os
import tempfile

import matplotlib.pyplot as plt
import numpy as np
import pyautogui
from PIL import Image


class Display:
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
