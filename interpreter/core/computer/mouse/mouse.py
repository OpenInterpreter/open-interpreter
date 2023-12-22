import time

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pyautogui
from PIL import Image


class Mouse:
    def __init__(self, computer):
        self.computer = computer

    def move(self, *args, x=None, y=None, icon=None):
        screenshot = None
        if len(args) > 1:
            raise ValueError(
                "Too many positional arguments provided: click(*args, x=None, y=None, show=True, index=None)\n\nPlease take a computer.screenshot() to find text/icons to click, then use computer.mouse.click(text) or computer.mouse.click(icon=description_of_icon) if at all possible. This is significantly more accurate."
            )
        elif len(args) == 1:
            text = args[0]

            screenshot = self.computer.display.screenshot(show=False)
            coordinates = self.computer.display.find_text(text, screenshot=screenshot)

            if len(coordinates) == 0:
                plt.imshow(np.array(screenshot))
                plt.show()
                raise ValueError(
                    f"Your text ('{text}') was not found on the screen. Please try again."
                )
            elif len(coordinates) > 1:
                # Convert the screenshot to a numpy array for drawing
                img_array = np.array(screenshot)
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
                img_draw = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

                # Iterate over the response items
                for i, item in enumerate(coordinates):
                    width, height = screenshot.size
                    x, y = item
                    x *= width
                    y *= height

                    x = int(x)
                    y = int(y)

                    # Draw a solid blue circle around the found text
                    cv2.circle(img_draw, (x, y), 20, (0, 0, 255), -1)
                    # Put the index number in the center of the circle in white
                    cv2.putText(
                        img_draw,
                        str(i),
                        (x - 10, y + 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )

                plt.imshow(img_draw)
                plt.show()

                coordinates = [
                    f"{i}: {int(item[0]*self.computer.display.width)}, {int(item[1]*self.computer.display.height)}"
                    for i, item in enumerate(coordinates)
                ]
                error_message = (
                    f"Your text ('{text}') was found multiple times on the screen. Please click one of the following coordinates with computer.mouse.move(x=x, y=y):\n"
                    + "\n".join(coordinates)
                )
                raise ValueError(error_message)
            else:
                x, y = coordinates[0]
                x *= self.computer.display.width
                y *= self.computer.display.height

        elif x is not None and y is not None:
            pass
        elif icon is not None:
            x, y = self.computer.display.find_icon(icon)
        else:
            raise ValueError("Either text, icon, or both x and y must be provided")

        if self.computer.debug_mode:
            if not screenshot:
                screenshot = self.computer.display.screenshot(show=False)
            # Convert the screenshot to a numpy array for drawing
            img_array = np.array(screenshot)
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            img_draw = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

            # Draw a solid blue circle around the place we're clicking
            cv2.circle(img_draw, (x, y), 20, (0, 0, 255), -1)

            # Convert the drawn image back to a PIL image
            img_pil = Image.fromarray(img_draw)
            # Show the image
            img_pil.show()

            time.sleep(4)

            # ^ This should ideally show it on the users computer but not show it to the LLM
            # because we're in debug mode, trying to do debug

        pyautogui.moveTo(x, y, duration=0.5)

    def click(self, *args, button="left", clicks=1, interval=0.1, **kwargs):
        if args or kwargs:
            self.move(*args, **kwargs)
        pyautogui.click(button=button, clicks=clicks, interval=interval)

    def double_click(self, *args, button="left", interval=0.1, **kwargs):
        if args or kwargs:
            self.move(*args, **kwargs)
        pyautogui.doubleClick(button=button, interval=interval)

    def triple_click(self, *args, button="left", interval=0.1, **kwargs):
        if args or kwargs:
            self.move(*args, **kwargs)
        pyautogui.tripleClick(button=button, interval=interval)

    def right_click(self, *args, **kwargs):
        if args or kwargs:
            self.move(*args, **kwargs)
        pyautogui.rightClick()

    def down(self):
        pyautogui.mouseDown()

    def up(self):
        pyautogui.mouseUp()
