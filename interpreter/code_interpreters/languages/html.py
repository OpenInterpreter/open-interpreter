import webbrowser
import tempfile
import os
from ..base_code_interpreter import BaseCodeInterpreter
from ..container_utils.upload_file import copy_file_to_container

class HTML(BaseCodeInterpreter):
    file_extension = "html"
    proper_name = "HTML"

    def __init__(self, **kwargs): ## accept the kwargs though we dont use them, since its easier this way.
        super().__init__() 
        self.kwargs = kwargs
    def run(self, code):
        # Create a temporary HTML file with the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(code.encode())

        save_dir = os.path.realpath(f.name)

        if self.kwargs.get("use_containers"):
            save_dir = copy_file_to_container(
                local_path=os.path.realpath(f.name),
                path_in_container=os.path.join("/mnt/data", f.name),
                container_id=self.kwargs.get("session_id"),
                pbar=False
            )

        # Open the HTML file with the default web browser
        webbrowser.open('file://' + os.path.realpath(f.name))

        yield {"output": f"Saved to {save_dir} and opened with the user's default web browser."}