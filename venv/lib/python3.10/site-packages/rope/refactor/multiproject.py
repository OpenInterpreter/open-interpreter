"""This module can be used for performing cross-project refactorings

See the "cross-project refactorings" section of ``docs/library.rst``
file.

"""

from rope.base import libutils, resources


class MultiProjectRefactoring:
    def __init__(self, refactoring, projects, addpath=True):
        """Create a multiproject proxy for the main refactoring

        `projects` are other project.

        """
        self.refactoring = refactoring
        self.projects = projects
        self.addpath = addpath

    def __call__(self, project, *args, **kwds):
        """Create the refactoring"""
        return _MultiRefactoring(
            self.refactoring, self.projects, self.addpath, project, *args, **kwds
        )


class _MultiRefactoring:
    def __init__(self, refactoring, other_projects, addpath, project, *args, **kwds):
        self.refactoring = refactoring
        self.projects = [project] + other_projects
        for other_project in other_projects:
            for folder in self.project.get_source_folders():
                other_project.get_prefs().add("python_path", folder.real_path)
        self.refactorings = []
        for other in self.projects:
            args, kwds = self._resources_for_args(other, args, kwds)
            self.refactorings.append(self.refactoring(other, *args, **kwds))

    def get_all_changes(self, *args, **kwds):
        """Get a project to changes dict"""
        result = []
        for project, refactoring in zip(self.projects, self.refactorings):
            args, kwds = self._resources_for_args(project, args, kwds)
            result.append((project, refactoring.get_changes(*args, **kwds)))
        return result

    def __getattr__(self, name):
        return getattr(self.main_refactoring, name)

    def _resources_for_args(self, project, args, kwds):
        newargs = [self._change_project_resource(project, arg) for arg in args]
        newkwds = {
            name: self._change_project_resource(project, value)
            for name, value in kwds.items()
        }
        return newargs, newkwds

    def _change_project_resource(self, project, obj):
        if isinstance(obj, resources.Resource) and obj.project != project:
            return libutils.path_to_resource(project, obj.real_path)
        return obj

    @property
    def project(self):
        return self.projects[0]

    @property
    def main_refactoring(self):
        return self.refactorings[0]


def perform(project_changes):
    for project, changes in project_changes:
        project.do(changes)
