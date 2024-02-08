import os

import aifs

from ....terminal_interface.utils.oi_dir import oi_dir

skills_dir = os.path.join(oi_dir, "skills")


class Skills:
    def __init__(self, computer):
        self.computer = computer
        self.path = skills_dir

    def search(self, query):
        result = aifs.search(skills_dir, query, python_docstrings_only=True)
        return result
