import base64
import os
import random
import string

from html2image import Html2Image


def html_to_base64(code):
    # Convert the HTML into an image using html2image
    hti = Html2Image()

    # Generate a random filename for the temporary image
    temp_filename = "".join(random.choices(string.digits, k=10)) + ".png"
    hti.screenshot(html_str=code, save_as=temp_filename, size=(1280, 720))

    # Convert the image to base64
    with open(temp_filename, "rb") as image_file:
        screenshot_base64 = base64.b64encode(image_file.read()).decode()

    # Delete the temporary image file
    os.remove(temp_filename)

    return screenshot_base64
