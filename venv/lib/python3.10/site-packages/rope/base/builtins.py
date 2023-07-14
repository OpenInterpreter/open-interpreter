"""This module tries to support builtin types and functions."""
import inspect
import io

import rope.base.evaluate
from rope.base import arguments, ast, pynames, pyobjects, utils


class BuiltinModule(pyobjects.AbstractModule):
    def __init__(self, name, pycore=None, initial={}):
        super().__init__()
        self.name = name
        self.pycore = pycore
        self.initial = initial

    parent = None

    def get_attributes(self):
        return self.attributes

    def get_doc(self):
        if self.module:
            return self.module.__doc__

    def get_name(self):
        return self.name.split(".")[-1]

    @property
    @utils.saveit
    def attributes(self):
        result = _object_attributes(self.module, self)
        result.update(self.initial)
        if self.pycore is not None:
            submodules = self.pycore._builtin_submodules(self.name)
            for name, module in submodules.items():
                result[name] = rope.base.builtins.BuiltinName(module)
        return result

    @property
    @utils.saveit
    def module(self):
        try:
            result = __import__(self.name)
            for token in self.name.split(".")[1:]:
                result = getattr(result, token, None)
            return result
        except ImportError:
            return


class _BuiltinElement:
    def __init__(self, builtin, parent=None):
        self.builtin = builtin
        self._parent = parent

    def get_doc(self):
        if self.builtin:
            return getattr(self.builtin, "__doc__", None)

    def get_name(self):
        if self.builtin:
            return getattr(self.builtin, "__name__", None)

    @property
    def parent(self):
        if self._parent is None:
            return builtins
        return self._parent


class BuiltinClass(_BuiltinElement, pyobjects.AbstractClass):
    def __init__(self, builtin, attributes, parent=None):
        _BuiltinElement.__init__(self, builtin, parent)
        pyobjects.AbstractClass.__init__(self)
        self.initial = attributes

    @utils.saveit
    def get_attributes(self):
        result = _object_attributes(self.builtin, self)
        result.update(self.initial)
        return result

    def get_module(self):
        return builtins


class BuiltinFunction(_BuiltinElement, pyobjects.AbstractFunction):
    def __init__(
        self, returned=None, function=None, builtin=None, argnames=[], parent=None
    ):
        _BuiltinElement.__init__(self, builtin, parent)
        pyobjects.AbstractFunction.__init__(self)
        self.argnames = argnames
        self.returned = returned
        self.function = function

    def get_returned_object(self, args):
        if self.function is not None:
            return self.function(_CallContext(self.argnames, args))
        else:
            return self.returned

    def get_param_names(self, special_args=True):
        return self.argnames


class BuiltinUnknown(_BuiltinElement, pyobjects.PyObject):
    def __init__(self, builtin):
        super().__init__(pyobjects.get_unknown())
        self.builtin = builtin
        self.type = pyobjects.get_unknown()

    def get_name(self):
        return getattr(type(self.builtin), "__name__", None)

    @utils.saveit
    def get_attributes(self):
        return _object_attributes(self.builtin, self)


def _object_attributes(obj, parent):
    attributes = {}
    for name in dir(obj):
        if name == "None":
            continue
        try:
            child = getattr(obj, name)
        except AttributeError:
            # descriptors are allowed to raise AttributeError
            # even if they are in dir()
            continue
        pyobject = None
        if inspect.isclass(child):
            pyobject = BuiltinClass(child, {}, parent=parent)
        elif inspect.isroutine(child):
            pyobject = BuiltinFunction(builtin=child, parent=parent)
        else:
            pyobject = BuiltinUnknown(builtin=child)
        attributes[name] = BuiltinName(pyobject)
    return attributes


def _create_builtin_type_getter(cls):
    def _get_builtin(*args):
        if not hasattr(cls, "_generated"):
            cls._generated = {}
        if args not in cls._generated:
            cls._generated[args] = cls(*args)
        return cls._generated[args]

    return _get_builtin


def _create_builtin_getter(cls):
    type_getter = _create_builtin_type_getter(cls)

    def _get_builtin(*args):
        return pyobjects.PyObject(type_getter(*args))

    return _get_builtin


class _CallContext:
    def __init__(self, argnames, args):
        self.argnames = argnames
        self.args = args

    def _get_scope_and_pyname(self, pyname):
        if pyname is not None and isinstance(pyname, pynames.AssignedName):
            pymodule, lineno = pyname.get_definition_location()
            if pymodule is None:
                return None, None
            if lineno is None:
                lineno = 1
            scope = pymodule.get_scope().get_inner_scope_for_line(lineno)
            name = None
            while name is None and scope is not None:
                for current in scope.get_names():
                    if scope[current] is pyname:
                        name = current
                        break
                else:
                    scope = scope.parent
            return scope, name
        return None, None

    def get_argument(self, name):
        if self.args:
            args = self.args.get_arguments(self.argnames)
            return args[self.argnames.index(name)]

    def get_pyname(self, name):
        if self.args:
            args = self.args.get_pynames(self.argnames)
            if name in self.argnames:
                return args[self.argnames.index(name)]

    def get_arguments(self, argnames):
        if self.args:
            return self.args.get_arguments(argnames)

    def get_pynames(self, argnames):
        if self.args:
            return self.args.get_pynames(argnames)

    def get_per_name(self):
        if self.args is None:
            return None
        pyname = self.args.get_instance_pyname()
        scope, name = self._get_scope_and_pyname(pyname)
        if name is not None:
            pymodule = pyname.get_definition_location()[0]
            return pymodule.pycore.object_info.get_per_name(scope, name)
        return None

    def save_per_name(self, value):
        if self.args is None:
            return None
        pyname = self.args.get_instance_pyname()
        scope, name = self._get_scope_and_pyname(pyname)
        if name is not None:
            pymodule = pyname.get_definition_location()[0]
            pymodule.pycore.object_info.save_per_name(scope, name, value)


class _AttributeCollector:
    def __init__(self, type):
        self.attributes = {}
        self.type = type

    def __call__(
        self,
        name,
        returned=None,
        function=None,
        argnames=["self"],
        check_existence=True,
        parent=None,
    ):
        try:
            builtin = getattr(self.type, name)
        except AttributeError:
            if check_existence:
                raise
            builtin = None
        self.attributes[name] = BuiltinName(
            BuiltinFunction(
                returned=returned,
                function=function,
                argnames=argnames,
                builtin=builtin,
                parent=parent,
            )
        )

    def __setitem__(self, name, value):
        self.attributes[name] = value


class List(BuiltinClass):
    def __init__(self, holding=None):
        self.holding = holding
        collector = _AttributeCollector(list)

        collector("__iter__", function=self._iterator_get, parent=self)
        collector("__new__", function=self._new_list, parent=self)

        # Adding methods
        collector(
            "append", function=self._list_add, argnames=["self", "value"], parent=self
        )
        collector(
            "__setitem__",
            function=self._list_add,
            argnames=["self", "index", "value"],
            parent=self,
        )
        collector(
            "insert",
            function=self._list_add,
            argnames=["self", "index", "value"],
            parent=self,
        )
        collector(
            "extend",
            function=self._self_set,
            argnames=["self", "iterable"],
            parent=self,
        )

        # Getting methods
        collector("__getitem__", function=self._list_get, parent=self)
        collector("pop", function=self._list_get, parent=self)
        try:
            collector("__getslice__", function=self._list_get)
        except AttributeError:
            pass

        super().__init__(list, collector.attributes)

    def _new_list(self, args):
        return _create_builtin(args, get_list)

    def _list_add(self, context):
        if self.holding is not None:
            return
        holding = context.get_argument("value")
        if holding is not None and holding != pyobjects.get_unknown():
            context.save_per_name(holding)

    def _self_set(self, context):
        if self.holding is not None:
            return
        iterable = context.get_pyname("iterable")
        holding = _infer_sequence_for_pyname(iterable)
        if holding is not None and holding != pyobjects.get_unknown():
            context.save_per_name(holding)

    def _list_get(self, context):
        if self.holding is not None:
            args = context.get_arguments(["self", "key"])
            if (
                len(args) > 1
                and args[1] is not None
                and args[1].get_type() == builtins["slice"].get_object()
            ):
                return get_list(self.holding)
            return self.holding
        return context.get_per_name()

    def _iterator_get(self, context):
        return get_iterator(self._list_get(context))

    def _self_get(self, context):
        return get_list(self._list_get(context))


get_list = _create_builtin_getter(List)
get_list_type = _create_builtin_type_getter(List)


class Dict(BuiltinClass):
    def __init__(self, keys=None, values=None):
        self.keys = keys
        self.values = values
        collector = _AttributeCollector(dict)
        collector("__new__", function=self._new_dict, parent=self)
        collector("__setitem__", function=self._dict_add, parent=self)
        collector("popitem", function=self._item_get, parent=self)
        collector("pop", function=self._value_get, parent=self)
        collector("get", function=self._key_get, parent=self)
        collector("keys", function=self._key_list, parent=self)
        collector("values", function=self._value_list, parent=self)
        collector("items", function=self._item_list, parent=self)
        collector("copy", function=self._self_get, parent=self)
        collector("__getitem__", function=self._value_get, parent=self)
        collector("__iter__", function=self._key_iter, parent=self)
        collector("update", function=self._self_set, parent=self)
        super().__init__(dict, collector.attributes)

    def _new_dict(self, args):
        def do_create(holding=None):
            if holding is None:
                return get_dict()
            type = holding.get_type()
            if isinstance(type, Tuple) and len(type.get_holding_objects()) == 2:
                return get_dict(*type.get_holding_objects())

        return _create_builtin(args, do_create)

    def _dict_add(self, context):
        if self.keys is not None:
            return
        key, value = context.get_arguments(["self", "key", "value"])[1:]
        if key is not None and key != pyobjects.get_unknown():
            context.save_per_name(get_tuple(key, value))

    def _item_get(self, context):
        if self.keys is not None:
            return get_tuple(self.keys, self.values)
        item = context.get_per_name()
        if item is None or not isinstance(item.get_type(), Tuple):
            return get_tuple(self.keys, self.values)
        return item

    def _value_get(self, context):
        item = self._item_get(context).get_type()
        return item.get_holding_objects()[1]

    def _key_get(self, context):
        item = self._item_get(context).get_type()
        return item.get_holding_objects()[0]

    def _value_list(self, context):
        return get_list(self._value_get(context))

    def _key_list(self, context):
        return get_list(self._key_get(context))

    def _item_list(self, context):
        return get_list(self._item_get(context))

    def _value_iter(self, context):
        return get_iterator(self._value_get(context))

    def _key_iter(self, context):
        return get_iterator(self._key_get(context))

    def _item_iter(self, context):
        return get_iterator(self._item_get(context))

    def _self_get(self, context):
        item = self._item_get(context).get_type()
        key, value = item.get_holding_objects()[:2]
        return get_dict(key, value)

    def _self_set(self, context):
        if self.keys is not None:
            return
        new_dict = context.get_pynames(["self", "d"])[1]
        if new_dict and isinstance(new_dict.get_object().get_type(), Dict):
            args = arguments.ObjectArguments([new_dict])
            items = (
                new_dict.get_object()["popitem"].get_object().get_returned_object(args)
            )
            context.save_per_name(items)
        else:
            holding = _infer_sequence_for_pyname(new_dict)
            if holding is not None and isinstance(holding.get_type(), Tuple):
                context.save_per_name(holding)


get_dict = _create_builtin_getter(Dict)
get_dict_type = _create_builtin_type_getter(Dict)


class Tuple(BuiltinClass):
    def __init__(self, *objects):
        self.objects = objects
        first = None
        if objects:
            first = objects[0]
        attributes = {
            "__getitem__": BuiltinName(
                BuiltinFunction(first)
            ),  # TODO: add slice support
            "__getslice__": BuiltinName(BuiltinFunction(pyobjects.PyObject(self))),
            "__new__": BuiltinName(BuiltinFunction(function=self._new_tuple)),
            "__iter__": BuiltinName(BuiltinFunction(get_iterator(first))),
        }
        super().__init__(tuple, attributes)

    def get_holding_objects(self):
        return self.objects

    def _new_tuple(self, args):
        return _create_builtin(args, get_tuple)


get_tuple = _create_builtin_getter(Tuple)
get_tuple_type = _create_builtin_type_getter(Tuple)


class Set(BuiltinClass):
    def __init__(self, holding=None):
        self.holding = holding
        collector = _AttributeCollector(set)
        collector("__new__", function=self._new_set)

        self_methods = [
            "copy",
            "difference",
            "intersection",
            "symmetric_difference",
            "union",
        ]
        for method in self_methods:
            collector(method, function=self._self_get, parent=self)
        collector("add", function=self._set_add, parent=self)
        collector("update", function=self._self_set, parent=self)
        collector("update", function=self._self_set, parent=self)
        collector("symmetric_difference_update", function=self._self_set, parent=self)
        collector("difference_update", function=self._self_set, parent=self)

        collector("pop", function=self._set_get, parent=self)
        collector("__iter__", function=self._iterator_get, parent=self)
        super().__init__(set, collector.attributes)

    def _new_set(self, args):
        return _create_builtin(args, get_set)

    def _set_add(self, context):
        if self.holding is not None:
            return
        holding = context.get_arguments(["self", "value"])[1]
        if holding is not None and holding != pyobjects.get_unknown():
            context.save_per_name(holding)

    def _self_set(self, context):
        if self.holding is not None:
            return
        iterable = context.get_pyname("iterable")
        holding = _infer_sequence_for_pyname(iterable)
        if holding is not None and holding != pyobjects.get_unknown():
            context.save_per_name(holding)

    def _set_get(self, context):
        if self.holding is not None:
            return self.holding
        return context.get_per_name()

    def _iterator_get(self, context):
        return get_iterator(self._set_get(context))

    def _self_get(self, context):
        return get_list(self._set_get(context))


get_set = _create_builtin_getter(Set)
get_set_type = _create_builtin_type_getter(Set)


class Str(BuiltinClass):
    def __init__(self):
        self_object = pyobjects.PyObject(self)
        collector = _AttributeCollector(str)
        collector("__iter__", get_iterator(self_object), check_existence=False)

        self_methods = [
            "__getitem__",
            "capitalize",
            "center",
            "encode",
            "expandtabs",
            "join",
            "ljust",
            "lower",
            "lstrip",
            "replace",
            "rjust",
            "rstrip",
            "strip",
            "swapcase",
            "title",
            "translate",
            "upper",
            "zfill",
        ]
        for method in self_methods:
            collector(method, self_object, parent=self)

        py2_self_methods = ["__getslice__", "decode"]
        for method in py2_self_methods:
            try:
                collector(method, self_object)
            except AttributeError:
                pass

        for method in ["rsplit", "split", "splitlines"]:
            collector(method, get_list(self_object), parent=self)

        super().__init__(str, collector.attributes)

    def get_doc(self):
        return str.__doc__


get_str = _create_builtin_getter(Str)
get_str_type = _create_builtin_type_getter(Str)


class BuiltinName(pynames.PyName):
    def __init__(self, pyobject):
        self.pyobject = pyobject

    def get_object(self):
        return self.pyobject

    def get_definition_location(self):
        return (None, None)


class Iterator(pyobjects.AbstractClass):
    def __init__(self, holding=None):
        super().__init__()
        self.holding = holding
        self.attributes = {
            "next": BuiltinName(BuiltinFunction(self.holding)),
            "__iter__": BuiltinName(BuiltinFunction(self)),
        }

    def get_attributes(self):
        return self.attributes

    def get_returned_object(self, args):
        return self.holding


get_iterator = _create_builtin_getter(Iterator)


class Generator(pyobjects.AbstractClass):
    def __init__(self, holding=None):
        super().__init__()
        self.holding = holding
        self.attributes = {
            "next": BuiltinName(BuiltinFunction(self.holding)),
            "__iter__": BuiltinName(BuiltinFunction(get_iterator(self.holding))),
            "close": BuiltinName(BuiltinFunction()),
            "send": BuiltinName(BuiltinFunction()),
            "throw": BuiltinName(BuiltinFunction()),
        }

    def get_attributes(self):
        return self.attributes

    def get_returned_object(self, args):
        return self.holding


get_generator = _create_builtin_getter(Generator)


class File(BuiltinClass):
    def __init__(self, filename=None, mode="r", *args):
        self.filename = filename
        self.mode = mode
        self.args = args
        str_object = get_str()
        str_list = get_list(get_str())
        attributes = {}

        def add(name, returned=None, function=None):
            builtin = getattr(io.TextIOBase, name, None)
            attributes[name] = BuiltinName(
                BuiltinFunction(returned=returned, function=function, builtin=builtin)
            )

        add("__iter__", get_iterator(str_object))
        add("__enter__", returned=pyobjects.PyObject(self))
        for method in ["next", "read", "readline", "readlines"]:
            add(method, str_list)
        for method in [
            "close",
            "flush",
            "lineno",
            "isatty",
            "seek",
            "tell",
            "truncate",
            "write",
            "writelines",
        ]:
            add(method)
        super().__init__(open, attributes)


get_file = _create_builtin_getter(File)
get_file_type = _create_builtin_type_getter(File)


class Property(BuiltinClass):
    def __init__(self, fget=None, fset=None, fdel=None, fdoc=None):
        self._fget = fget
        self._fdoc = fdoc
        attributes = {
            "fget": BuiltinName(BuiltinFunction()),
            "fset": BuiltinName(pynames.UnboundName()),
            "fdel": BuiltinName(pynames.UnboundName()),
            "__new__": BuiltinName(BuiltinFunction(function=_property_function)),
        }
        super().__init__(property, attributes)

    def get_property_object(self, args):
        if isinstance(self._fget, pyobjects.AbstractFunction):
            return self._fget.get_returned_object(args)


def _property_function(args):
    parameters = args.get_arguments(["fget", "fset", "fdel", "fdoc"])
    return pyobjects.PyObject(Property(parameters[0]))


class Lambda(pyobjects.AbstractFunction):
    def __init__(self, node, scope):
        super().__init__()
        self.node = node
        self.arguments = node.args
        self.scope = scope

    def get_returned_object(self, args):
        result = rope.base.evaluate.eval_node(self.scope, self.node.body)
        if result is not None:
            return result.get_object()
        else:
            return pyobjects.get_unknown()

    def get_module(self):
        return self.parent.get_module()

    def get_scope(self):
        return self.scope

    def get_kind(self):
        return "lambda"

    def get_ast(self):
        return self.node

    def get_attributes(self):
        return {}

    def get_name(self):
        return "lambda"

    def get_param_names(self, special_args=True):
        result = [node.arg for node in self.arguments.args if isinstance(node, ast.arg)]
        if self.arguments.vararg:
            result.append("*" + self.arguments.vararg.arg)
        if self.arguments.kwarg:
            result.append("**" + self.arguments.kwarg.arg)
        return result

    @property
    def parent(self):
        return self.scope.pyobject


class BuiltinObject(BuiltinClass):
    def __init__(self):
        super().__init__(object, {})


class BuiltinType(BuiltinClass):
    def __init__(self):
        super().__init__(type, {})


def _infer_sequence_for_pyname(pyname):
    if pyname is None:
        return None
    seq = pyname.get_object()
    args = arguments.ObjectArguments([pyname])
    if "__iter__" in seq:
        obj = seq["__iter__"].get_object()
        if not isinstance(obj, pyobjects.AbstractFunction):
            return None
        iter = obj.get_returned_object(args)
        if iter is not None and "next" in iter:
            holding = iter["next"].get_object().get_returned_object(args)
            return holding


def _create_builtin(args, creator):
    passed = args.get_pynames(["sequence"])[0]
    if passed is None:
        holding = None
    else:
        holding = _infer_sequence_for_pyname(passed)
    if holding is not None:
        return creator(holding)
    else:
        return creator()


def _open_function(args):
    return _create_builtin(args, get_file)


def _range_function(args):
    return get_list()


def _reversed_function(args):
    return _create_builtin(args, get_iterator)


def _sorted_function(args):
    return _create_builtin(args, get_list)


def _super_function(args):
    passed_class, passed_self = args.get_arguments(["type", "self"])
    if passed_self is None:
        return passed_class
    else:
        # pyclass = passed_self.get_type()
        pyclass = passed_class
        if isinstance(pyclass, pyobjects.AbstractClass):
            supers = pyclass.get_superclasses()
            if supers:
                return pyobjects.PyObject(supers[0])
        return passed_self


def _zip_function(args):
    args = args.get_pynames(["sequence"])
    objects = []
    for seq in args:
        if seq is None:
            holding = None
        else:
            holding = _infer_sequence_for_pyname(seq)
        objects.append(holding)
    tuple = get_tuple(*objects)
    return get_list(tuple)


def _enumerate_function(args):
    passed = args.get_pynames(["sequence"])[0]
    if passed is None:
        holding = None
    else:
        holding = _infer_sequence_for_pyname(passed)
    tuple = get_tuple(None, holding)
    return get_iterator(tuple)


def _iter_function(args):
    passed = args.get_pynames(["sequence"])[0]
    if passed is None:
        holding = None
    else:
        holding = _infer_sequence_for_pyname(passed)
    return get_iterator(holding)


def _input_function(args):
    return get_str()


_initial_builtins = {
    "list": BuiltinName(get_list_type()),
    "dict": BuiltinName(get_dict_type()),
    "tuple": BuiltinName(get_tuple_type()),
    "set": BuiltinName(get_set_type()),
    "str": BuiltinName(get_str_type()),
    "open": BuiltinName(BuiltinFunction(function=_open_function, builtin=open)),
    "range": BuiltinName(BuiltinFunction(function=_range_function, builtin=range)),
    "reversed": BuiltinName(
        BuiltinFunction(function=_reversed_function, builtin=reversed)
    ),
    "sorted": BuiltinName(BuiltinFunction(function=_sorted_function, builtin=sorted)),
    "super": BuiltinName(BuiltinFunction(function=_super_function, builtin=super)),
    "property": BuiltinName(
        BuiltinFunction(function=_property_function, builtin=property)
    ),
    "zip": BuiltinName(BuiltinFunction(function=_zip_function, builtin=zip)),
    "enumerate": BuiltinName(
        BuiltinFunction(function=_enumerate_function, builtin=enumerate)
    ),
    "object": BuiltinName(BuiltinObject()),
    "type": BuiltinName(BuiltinType()),
    "iter": BuiltinName(BuiltinFunction(function=_iter_function, builtin=iter)),
    "input": BuiltinName(BuiltinFunction(function=_input_function, builtin=input)),
}

builtins = BuiltinModule("builtins", initial=_initial_builtins)
