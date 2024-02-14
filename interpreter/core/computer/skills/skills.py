import glob
import os

import aifs


class Skills:
    def __init__(self, computer):
        self.computer = computer
        self.skills_dir = None

    def search(self, query):
        result = aifs.search(self.skills_dir, query, python_docstrings_only=True)
        return result

    def import_skills(self):
        self.computer.save_skills = False
        for file in glob.glob(os.path.join(self.skills_dir, "*.py")):
            with open(file, "r") as f:
                self.computer.run("python", f.read())
        self.computer.save_skills = True
