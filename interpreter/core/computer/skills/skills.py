import glob
import inspect
import os
import re
from pathlib import Path

from ....terminal_interface.utils.oi_dir import oi_dir
from ...utils.lazy_import import lazy_import

# Lazy import of aifs, imported when needed to speed up start time
aifs = lazy_import("aifs")


class Skills:
    def __init__(self, computer):
        self.computer = computer
        self.path = str(Path(oi_dir) / "skills")
        self.new_skill = NewSkill()
        self.new_skill.path = self.path

    def search(self, query):
        return aifs.search(query, self.path, python_docstrings_only=True)

    def import_skills(self):
        self.computer.save_skills = False
        for file in glob.glob(os.path.join(self.path, "*.py")):
            with open(file, "r") as f:
                self.computer.run("python", f.read())
        self.computer.save_skills = True


class NewSkill:
    def __init__(self):
        self.path = ""

    def create(self):
        self.steps = []
        self._name = "Untitled"
        print(
            """
        
You are creating a new skill.
To begin, ask the user what the name of this skill is. Then, run `computer.skills.new_skill.name = "Name of the skill"`.
        
        """.strip()
        )

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        print(
            """
        
You just named this skill. Great!
Now, ask the user what the first step is, then try to execute code to accomplish that step.
Then, ask the user if you completed the step correctly.
Repeat this until the user said you completed the step correctly.
Then, run `computer.skills.new_skill.add_step(step, code)` where step is a natural language description of the step, and code is the code you ran to complete it.
If the user says the skill is complete, or that that was the last step, run `computer.skills.new_skill.save()`.

              """.strip()
        )

    def add_step(self, step, code):
        self.steps.append(step + "\n\n```python\n" + code + "\n```")
        print(
            """
        
Step added.
Now, ask the user what the next step is, then try to execute code to accomplish that step.
Then, ask the user if you completed the step correctly.
Repeat this until the user said you completed the step correctly.
Then, run `computer.skills.new_skill.add_step(step, code)` where step is a natural language description of the step, and code is the code you ran to complete it.
If the user says the skill is complete, or that that was the last step, run `computer.skills.new_skill.save()`.

        """.strip()
        )

    def save(self):
        normalized_name = re.sub("[^0-9a-zA-Z]+", "_", self.name.lower())
        steps_string = "\n".join(
            [f"Step {i+1}:\n{step}\n" for i, step in enumerate(self.steps)]
        )
        steps_string = steps_string.replace('"""', "'''")
        skill_string = f'''
        
def {normalized_name}():
    """
    {normalized_name}
    """

    print("To complete this task / run this skill, flexibly follow the following tutorial, swapping out parts as necessary to fulfill the user's task:\n")

    print("""{steps_string}""")
        
        '''.strip()

        if not os.path.exists(self.path):
            os.makedirs(self.path)
        with open(f"{self.path}/{normalized_name}.py", "w") as file:
            file.write(skill_string)

        print("SKILL SAVED:", self.name.upper())
        print(
            "Teaching session finished. Tell the user that the skill above has been saved. Great work!"
        )
