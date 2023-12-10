import time

import matplotlib.pyplot as plt
import numpy as np
import pyautogui
from PIL import Image

from ..utils.computer_vision import find_text_in_image


class Mouse:
    def __init__(self, computer):
        self.computer = computer

    def move(self, *args, x=None, y=None, index=None, svg=None):
        if len(args) > 1:
            raise ValueError(
                "Too many positional arguments provided: click(*args, x=None, y=None, show=True, index=None)"
            )
        elif len(args) == 1:
            text = args[0]
            # Take a screenshot
            img = self.computer.screenshot(show=False)

            # Find the text in the screenshot
            centers, bounding_box_image = find_text_in_image(img, text)

            # If the text was found
            if centers:
                # This could be refactored to be more readable
                if len(centers) > 1:
                    if index == None:
                        print(
                            f"(Message for language model) This text ('{text}') was found multiple times on screen. Please try 'click()' again, but pass in an `index` int to identify which one you want to click. The indices have been drawn on the image."
                        )
                        # Show the image using matplotlib
                        plt.imshow(np.array(bounding_box_image))
                        plt.show()
                        return
                    else:
                        center = centers[index]
                else:
                    center = centers[0]

                # Slowly move the mouse from its current position
                pyautogui.moveTo(center[0], center[1], duration=0.5)

            else:
                plt.imshow(np.array(bounding_box_image))
                plt.show()
                print("Your text was not found on the screen. Please try again.")
        elif x is not None and y is not None:
            # Move to the specified coordinates and click
            pyautogui.moveTo(x, y, duration=0.5)
        elif svg is not None:
            raise NotImplementedError("SVG handling not implemented yet.")
            # img = self.computer.screenshot(show=False)
            # # Move to the specified coordinates and click
            # coordinates = find_svg_in_image(svg, img)
            # if coordinates == None:
            #     print("Not found.")
            #     return
            # pyautogui.moveTo(coordinates[0], coordinates[1], duration=0.5)
            # pyautogui.click(coordinates[0], coordinates[1])
        else:
            raise ValueError("Either text or both x and y must be provided")

    def click(self, *args, **kwargs):
        if args or kwargs:
            self.move(*args, **kwargs)
        pyautogui.click()

    def down(self):
        pyautogui.mouseDown()

    def up(self):
        pyautogui.mouseUp()
