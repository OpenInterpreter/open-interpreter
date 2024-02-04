import os

import aifs

from ....terminal_interface.utils.oi_dir import oi_dir

skills_dir = os.path.join(oi_dir, "skills")


class Skills:
    def __init__(self, computer):
        self.computer = computer
        self.path = skills_dir

    def search(self, query):
        os.environ["AIFS_MINIMAL_PYTHON_INDEXING"] = "True"
        result = aifs.search(skills_dir, query)
        os.environ["AIFS_MINIMAL_PYTHON_INDEXING"] = "False"
        return result
