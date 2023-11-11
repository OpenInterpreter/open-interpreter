import base64
import os
import platform
import subprocess
import tempfile


def display_output(output):
    if is_running_in_jupyter():
        from IPython.display import HTML, Image, Javascript, display

        if "output" in output:
            print(output["output"])
        elif "image" in output:
            # Decode the base64 image data
            image_data = base64.b64decode(output["image"])
            display(Image(image_data, format="png"))
        elif "html" in output:
            display(HTML(output["html"]))
        elif "javascript" in output:
            display(Javascript(output["javascript"]))
    else:
        display_output_cli(output)

    # Return a message for the LLM.
    # We should make this specific to what happened in the future,
    # like saying WHAT temporary file we made, ect. Keep the LLM informed.
    return "Displayed on the user's machine."


def display_output_cli(output):
    if "output" in output:
        print(output["output"])
    elif "image" in output:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            image_data = output["image"]
            tmp_file.write(base64.b64decode(image_data))
            open_file(tmp_file.name)
            print(f"Image saved and opened from {tmp_file.name}")
    elif "html" in output:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w"
        ) as tmp_file:
            html = output["html"]
            if "<html>" not in html:
                html = "<html>\n" + html + "\n</html>"
            tmp_file.write(html)
            open_file(tmp_file.name)
            print(f"HTML content saved and opened from {tmp_file.name}")
    elif "javascript" in output:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".js", mode="w"
        ) as tmp_file:
            tmp_file.write(output["javascript"])
            open_file(tmp_file.name)
            print(f"JavaScript content saved and opened from {tmp_file.name}")


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


def is_running_in_jupyter():
    try:
        from IPython import get_ipython

        if "IPKernelApp" in get_ipython().config:
            print("You are in Jupyter.")
            return True
    except:
        return False
