import glob
import inspect
import os
import re
from pathlib import Path

from ....terminal_interface.utils.oi_dir import oi_dir
from ...utils.lazy_import import lazy_import
from ..utils.recipient_utils import format_to_recipient

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
        previous_save_skills_setting = self.computer.save_skills
        self.computer.save_skills = False

        code_to_run = ""
        for file in glob.glob(os.path.join(self.path, "*.py")):
            with open(file, "r") as f:
                code_to_run += f.read() + "\n"

        if self.computer.interpreter.debug:
            print("IMPORTING SKILLS:\n", code_to_run)

        self.computer.run("python", code_to_run)
        self.computer.save_skills = previous_save_skills_setting


class NewSkill:
    def __init__(self):
        self.path = ""

    def create(self):
        self.steps = []
        self._name = "Untitled"
        print(
            """
@@@SEND_MESSAGE_AS_USER@@@
INSTRUCTIONS
You are creating a new skill. Follow these steps exactly:
1. Ask me what the name of this skill is.
2. When I respond, write the following (including the markdown code block):

---
Got it. Give me one second.
```python
computer.skills.new_skill.name = "{my chosen skill name}"`.
```
---
        
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
@@@SEND_MESSAGE_AS_USER@@@
Skill named. Now, follow these next INSTRUCTIONS exactly:

1. Ask me what the first step is.
2. When I reply, execute code to accomplish that step.
3. Ask me if you completed the step correctly.
    a. (!!!!!!!!!!!! >>>>>> THIS IS CRITICAL. DO NOT FORGET THIS.) IF you completed it correctly, run `computer.skills.new_skill.add_step(step, code)` where step is a generalized, natural language description of the step, and code is the code you ran to complete it.
    b. IF you did not complete it correctly, try to fix your code and ask me again.
4. If I say the skill is complete, or that that was the last step, run `computer.skills.new_skill.save()`.

YOU MUST FOLLOW THESE 4 INSTRUCTIONS **EXACTLY**. I WILL TIP YOU $200.

              """.strip()
        )

    def add_step(self, step, code):
        self.steps.append(step + "\n\n```python\n" + code + "\n```")
        print(
            """
@@@SEND_MESSAGE_AS_USER@@@
Step added. Now, follow these next INSTRUCTIONS exactly:

1. Ask me what the next step is.
2. When I reply, execute code to accomplish that step.
3. Ask me if you completed the step correctly.
    a. (!!!!!!!!!!!! >>>>>> THIS IS CRITICAL. DO NOT FORGET THIS!!!!!!!!.) IF you completed it correctly, run `computer.skills.new_skill.add_step(step, code)` where step is a generalized, natural language description of the step, and code is the code you ran to complete it.
    b. IF you did not complete it correctly, try to fix your code and ask me again.
4. If I say the skill is complete, or that that was the last step, run `computer.skills.new_skill.save()`.

YOU MUST FOLLOW THESE 4 INSTRUCTIONS **EXACTLY**. I WILL TIP YOU $200.

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

    print("To complete this task / run this skill, flexibly follow the following tutorial, swapping out parts as necessary to fulfill the user's task:")

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
