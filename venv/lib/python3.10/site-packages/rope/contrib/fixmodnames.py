"""Fix the name of modules

This module is useful when you want to rename many of the modules in
your project.  That can happen specially when you want to change their
naming style.

For instance::

  fixer = FixModuleNames(project)
  changes = fixer.get_changes(fixer=str.lower)
  project.do(changes)

Here it renames all modules and packages to use lower-cased chars.
You can tell it to use any other style by using the ``fixer``
argument.

"""
from rope.base import taskhandle
from rope.contrib import changestack
from rope.refactor import rename


class FixModuleNames:
    def __init__(self, project):
        self.project = project

    def get_changes(self, fixer=str.lower, task_handle=taskhandle.DEFAULT_TASK_HANDLE):
        """Fix module names

        `fixer` is a function that takes and returns a `str`.  Given
        the name of a module, it should return the fixed name.

        """
        stack = changestack.ChangeStack(self.project, "Fixing module names")
        jobset = task_handle.create_jobset(
            "Fixing module names", self._count_fixes(fixer) + 1
        )
        try:
            while True:
                for resource in self._tobe_fixed(fixer):
                    jobset.started_job(resource.path)
                    renamer = rename.Rename(self.project, resource)
                    changes = renamer.get_changes(fixer(self._name(resource)))
                    stack.push(changes)
                    jobset.finished_job()
                    break
                else:
                    break
        finally:
            jobset.started_job("Reverting to original state")
            stack.pop_all()
            jobset.finished_job()
        return stack.merged()

    def _count_fixes(self, fixer):
        return len(list(self._tobe_fixed(fixer)))

    def _tobe_fixed(self, fixer):
        for resource in self.project.get_python_files():
            modname = self._name(resource)
            if modname != fixer(modname):
                yield resource

    def _name(self, resource):
        modname = resource.name.rsplit(".", 1)[0]
        if modname == "__init__":
            modname = resource.parent.name
        return modname
