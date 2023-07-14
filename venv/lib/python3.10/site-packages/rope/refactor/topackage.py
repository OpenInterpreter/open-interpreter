import rope.refactor.importutils
from rope.base.change import ChangeContents, ChangeSet, CreateFolder, MoveResource


class ModuleToPackage:
    def __init__(self, project, resource):
        self.project = project
        self.resource = resource

    def get_changes(self):
        changes = ChangeSet("Transform <%s> module to package" % self.resource.path)
        new_content = self._transform_relatives_to_absolute(self.resource)
        if new_content is not None:
            changes.add_change(ChangeContents(self.resource, new_content))
        parent = self.resource.parent
        name = self.resource.name[:-3]
        changes.add_change(CreateFolder(parent, name))
        parent_path = parent.path + "/"
        if not parent.path:
            parent_path = ""
        new_path = parent_path + "%s/__init__.py" % name
        if self.resource.project == self.project:
            changes.add_change(MoveResource(self.resource, new_path))
        return changes

    def _transform_relatives_to_absolute(self, resource):
        pymodule = self.project.get_pymodule(resource)
        import_tools = rope.refactor.importutils.ImportTools(self.project)
        return import_tools.relatives_to_absolutes(pymodule)
