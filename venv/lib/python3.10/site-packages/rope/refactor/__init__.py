"""rope refactor package

This package contains modules that perform python refactorings.
Refactoring classes perform refactorings in 4 steps:

1. Collect some data for performing the refactoring and use them
   to construct a refactoring class.  Like::

     renamer = Rename(project, resource, offset)

2. Some refactorings give you useful information about the
   refactoring after their construction.  Like::

     print(renamer.get_old_name())

3. Give the refactoring class more information about how to
   perform the refactoring and get the changes this refactoring is
   going to make.  This is done by calling `get_changes` method of the
   refactoring class.  Like::

     changes = renamer.get_changes(new_name)

4. You can commit the changes.  Like::

     project.do(changes)

These steps are like the steps IDEs usually do for performing a
refactoring.  These are the things an IDE does in each step:

1. Construct a refactoring object by giving it information like
   resource, offset and ... .  Some of the refactoring problems (like
   performing rename refactoring on language keywords) can be reported
   here.
2. Print some information about the refactoring and ask the user
   about the information that are necessary for completing the
   refactoring (like new name).
3. Call the `get_changes` by passing it information asked from
   the user (if necessary) and get and preview the changes returned by
   it.
4. perform the refactoring.

From ``0.5m5`` release the `get_changes()` method of some time-
consuming refactorings take an optional `rope.base.taskhandle.
TaskHandle` parameter.  You can use this object for stopping or
monitoring the progress of refactorings.

"""
from rope.refactor.importutils import ImportOrganizer  # noqa
from rope.refactor.topackage import ModuleToPackage  # noqa

__all__ = [
    "rename",
    "move",
    "inline",
    "extract",
    "restructure",
    "topackage",
    "importutils",
    "usefunction",
    "change_signature",
    "encapsulate_field",
    "introduce_factory",
    "introduce_parameter",
    "localtofield",
    "method_object",
    "multiproject",
]
