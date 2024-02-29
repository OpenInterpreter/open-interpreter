import glob
import inspect
import os
from pathlib import Path

from ....terminal_interface.utils.oi_dir import oi_dir
from ...utils.lazy_import import lazy_import

# Lazy import of aifs, imported when needed to speed up start time
aifs = lazy_import("aifs")


class Skills:
    def __init__(self, computer):
        self.computer = computer
        self.path = str(Path(oi_dir) / "skills")

    def search(self, query):
        return aifs.search(query, self.path, python_docstrings_only=True)

    def import_skills(self):
        self.computer.save_skills = False
        for file in glob.glob(os.path.join(self.path, "*.py")):
            with open(file, "r") as f:
                self.computer.run("python", f.read())
        self.computer.save_skills = True


class Teach:
    def __init__(self):
        self.steps = []
        print(
            "Welcome to the teaching session. Please add steps using .add_step('step text')"
        )

    def add_step(self, step_text):
        self.steps.append(step_text)
        print("Step added. Run .finish() when you are done.")

    def finish(self):
        print("Teaching session finished. Here are the steps you added:")
        for i, step in enumerate(self.steps, start=1):
            print(f"Step {i}: {step}")
