import logging
from typing import Optional, Union

import rope.base.utils as base_utils
from rope.base import evaluate
from rope.base.exceptions import AttributeNotFoundError
from rope.base.pyobjects import PyClass, PyDefinedObject, PyFunction, PyObject


def get_super_func(pyfunc):

    if not isinstance(pyfunc.parent, PyClass):
        return

    for cls in get_mro(pyfunc.parent)[1:]:
        try:
            superfunc = cls.get_attribute(pyfunc.get_name()).get_object()
        except AttributeNotFoundError:
            pass
        else:
            if isinstance(superfunc, PyFunction):
                return superfunc


def get_super_assignment(pyname):
    """
    :type pyname: rope.base.pynamesdef.AssignedName
    :type: rope.base.pynamesdef.AssignedName
    """
    try:
        pyclass, attr_name = get_class_with_attr_name(pyname)
    except TypeError:
        return
    else:
        for super_pyclass in get_mro(pyclass)[1:]:
            if attr_name in super_pyclass:
                return super_pyclass[attr_name]


def get_class_with_attr_name(pyname):
    """
    :type pyname: rope.base.pynamesdef.AssignedName
    :return: rope.base.pyobjectsdef.PyClass, str
    :rtype: tuple
    """
    lineno = get_lineno_for_node(pyname.assignments[0].ast_node)
    holding_scope = pyname.module.get_scope().get_inner_scope_for_line(lineno)
    pyobject = holding_scope.pyobject
    if isinstance(pyobject, PyClass):
        pyclass = pyobject
    elif isinstance(pyobject, PyFunction) and isinstance(pyobject.parent, PyClass):
        pyclass = pyobject.parent
    else:
        return
    for name, attr in pyclass.get_attributes().items():
        if attr is pyname:
            return (pyclass, name)


def get_lineno_for_node(assign_node):
    if hasattr(assign_node, "lineno") and assign_node.lineno is not None:
        return assign_node.lineno
    return 1


def get_mro(pyclass):
    # FIXME: to use real mro() result
    class_list = [pyclass]
    for cls in class_list:
        for super_cls in cls.get_superclasses():
            if isinstance(super_cls, PyClass) and super_cls not in class_list:
                class_list.append(super_cls)
    return class_list


def resolve_type(type_name, pyobject):
    # type: (str, Union[PyDefinedObject, PyObject]) -> Optional[PyDefinedObject, PyObject]
    """
    Find proper type object from its name.
    """
    deprecated_aliases = {"collections": "collections.abc"}
    ret_type = None
    logging.debug("Looking for %s", type_name)
    if "." not in type_name:
        try:
            ret_type = (
                pyobject.get_module().get_scope().get_name(type_name).get_object()
            )
        except AttributeNotFoundError:
            logging.exception("Cannot resolve type %s", type_name)
    else:
        mod_name, attr_name = type_name.rsplit(".", 1)
        try:
            mod_finder = evaluate.ScopeNameFinder(pyobject.get_module())
            mod = mod_finder._find_module(mod_name).get_object()
            ret_type = mod.get_attribute(attr_name).get_object()
        except AttributeNotFoundError:
            if mod_name in deprecated_aliases:
                try:
                    logging.debug(
                        "Looking for %s in %s", attr_name, deprecated_aliases[mod_name]
                    )
                    mod = mod_finder._find_module(
                        deprecated_aliases[mod_name]
                    ).get_object()
                    ret_type = mod.get_attribute(attr_name).get_object()
                except AttributeNotFoundError:
                    logging.exception(
                        "Cannot resolve type %s in %s", attr_name, dir(mod)
                    )
    logging.debug("ret_type = %s", ret_type)
    return ret_type


class ParametrizeType:

    _supported_mapping = {
        "builtins.list": "rope.base.builtins.get_list",
        "builtins.tuple": "rope.base.builtins.get_tuple",
        "builtins.set": "rope.base.builtins.get_set",
        "builtins.dict": "rope.base.builtins.get_dict",
        "_collections_abc.Iterable": "rope.base.builtins.get_iterator",
        "_collections_abc.Iterator": "rope.base.builtins.get_iterator",
        "collections.abc.Iterable": "rope.base.builtins.get_iterator",  # Python3.3
        "collections.abc.Iterator": "rope.base.builtins.get_iterator",  # Python3.3
    }

    def __call__(self, pyobject, *args, **kwargs):
        """
        :type pyobject: rope.base.pyobjects.PyObject
        :rtype: rope.base.pyobjects.PyDefinedObject | rope.base.pyobjects.PyObject or None
        """
        type_factory = self._get_type_factory(pyobject)
        if type_factory:
            parametrized_type = type_factory(*args, **kwargs)
            if parametrized_type:
                return parametrized_type
        return pyobject

    def _get_type_factory(self, pyobject):
        type_str = "{}.{}".format(
            pyobject.get_module().get_name(),
            pyobject.get_name(),
        )
        if type_str in self._supported_mapping:
            return base_utils.resolve(self._supported_mapping[type_str])


parametrize_type = ParametrizeType()
