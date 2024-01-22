import base64
import os
import platform
import subprocess
import tempfile

from .in_jupyter_notebook import in_jupyter_notebook


def display_output(output):
    if in_jupyter_notebook():
        from IPython.display import HTML, Image, Javascript, display

        if output["type"] == "console":
            print(output["content"])
        elif output["type"] == "image":
            if "base64" in output["format"]:
                # Decode the base64 image data
                image_data = base64.b64decode(output["content"])
                display(Image(image_data))
            elif output["format"] == "path":
                # Display the image file on the system
                display(Image(filename=output["content"]))
        elif "format" in output and output["format"] == "html":
            display(HTML(output["content"]))
        elif "format" in output and output["format"] == "javascript":
            display(Javascript(output["content"]))
    else:
        display_output_cli(output)

    # Return a message for the LLM.
    # We should make this specific to what happened in the future,
    # like saying WHAT temporary file we made, ect. Keep the LLM informed.
    return "Displayed on the user's machine."


def display_output_cli(output):
    if output["type"] == "console":
        print(output["content"])
    elif output["type"] == "image":
        if "base64" in output["format"]:
            if "." in output["format"]:
                extension = output["format"].split(".")[-1]
            else:
                extension = "png"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix="." + extension
            ) as tmp_file:
                image_data = base64.b64decode(output["content"])
                tmp_file.write(image_data)

                # # Display in Terminal (DISABLED, i couldn't get it to work)
                # from term_image.image import from_file
                # image = from_file(tmp_file.name)
                # image.draw()

                open_file(tmp_file.name)
        elif output["format"] == "path":
            open_file(output["content"])
    elif "format" in output and output["format"] == "html":
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w"
        ) as tmp_file:
            html = output["content"]
            tmp_file.write(html)
            open_file(tmp_file.name)
    elif "format" in output and output["format"] == "javascript":
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".js", mode="w"
        ) as tmp_file:
            tmp_file.write(output["content"])
            open_file(tmp_file.name)


def open_file(file_path):
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path])
        else:  # Linux and other Unix-like
            subprocess.run(["xdg-open", file_path])
    except Exception as e:
        print(f"Error opening file: {e}")
