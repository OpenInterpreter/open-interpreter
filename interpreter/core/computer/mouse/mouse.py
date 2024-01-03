import time

import matplotlib.pyplot as plt

try:
    import cv2
    import numpy as np
    import pyautogui
except:
    # Optional packages
    pass


class Mouse:
    def __init__(self, computer):
        self.computer = computer

    def scroll(self, clicks):
        pyautogui.scroll(clicks)

    def position(self):
        """
        Get the current mouse position.

        Returns:
            tuple: A tuple (x, y) representing the mouse's current position on the screen.
        """
        try:
            return pyautogui.position()
        except Exception as e:
            raise RuntimeError(
                f"An error occurred while retrieving the mouse position: {e}. "
            )

    def move(self, *args, x=None, y=None, icon=None):
        screenshot = None
        if len(args) > 1:
            raise ValueError(
                "Too many positional arguments provided. To move/click specific coordinates, use kwargs (x=x, y=y).\n\nPlease take a screenshot with computer.display.view() to find text/icons to click, then use computer.mouse.click(text) or computer.mouse.click(icon=description_of_icon) if at all possible. This is **significantly** more accurate than using coordinates. Specifying (x=x, y=y) is highly likely to fail. Specifying ('text to click') is highly likely to succeed."
            )
        elif len(args) == 1:
            text = args[0]

            screenshot = self.computer.display.screenshot(show=False)

            if self.computer.offline == True:
                try:
                    import pytesseract
                except:
                    raise Exception(
                        "To find text in order to use the mouse, please install `pytesseract` along with the Tesseract executable."
                    )

            coordinates = self.computer.display.find_text(text, screenshot=screenshot)

            # TESTING
            print(coordinates)

            if len(coordinates) == 0:
                if self.computer.emit_images:
                    plt.imshow(np.array(screenshot))
                    plt.show()
                raise ValueError(
                    f"Your text ('{text}') was not found on the screen. Please try again. If you're 100% sure the text should be there, consider using `computer.mouse.scroll(-10)` to scroll down.\n\nYou can use `computer.display.get_text()` to see all the text on the screen."
                )
            elif len(coordinates) > 1:
                if self.computer.emit_images:
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
                    f"Your text ('{text}') was found multiple times on the screen. Please review the attached image, then click/move over one of the following coordinates with computer.mouse.click(x=x, y=y) or computer.mouse.move(x=x, y=y):\n"
                    + "\n".join(coordinates)
                )
                raise ValueError(error_message)
            else:
                x, y = coordinates[0]
                x *= self.computer.display.width
                y *= self.computer.display.height
                x = int(x)
                y = int(y)

            # TESTING
            print(x, y)
            print("Width:", self.computer.display.width)
            print("Height:", self.computer.display.height)

        elif x is not None and y is not None:
            pass
        elif icon is not None:
            coordinates = self.computer.display.find_icon(icon)

            if len(coordinates) > 1:
                if self.computer.emit_images:
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
                    f"Your icon ('{text}') was found multiple times on the screen. Please click one of the following coordinates with computer.mouse.move(x=x, y=y):\n"
                    + "\n".join(coordinates)
                )
                raise ValueError(error_message)
            else:
                x, y = coordinates[0]
                x *= self.computer.display.width
                y *= self.computer.display.height
                x = int(x)
                y = int(y)

        else:
            raise ValueError("Either text, icon, or both x and y must be provided")

        if self.computer.verbose:
            if not screenshot:
                screenshot = self.computer.display.screenshot(show=False)

            # Convert the screenshot to a numpy array for drawing
            img_array = np.array(screenshot)
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            img_draw = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

            # Scale drawing_x and drawing_y from screen size to screenshot size for drawing purposes
            drawing_x = int(x * screenshot.width / self.computer.display.width)
            drawing_y = int(y * screenshot.height / self.computer.display.height)

            # Draw a solid blue circle around the place we're clicking
            cv2.circle(img_draw, (drawing_x, drawing_y), 20, (0, 0, 255), -1)

            plt.imshow(img_draw)
            plt.show()

            time.sleep(5)

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
