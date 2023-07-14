def __rope_start_everything():
    import os
    import socket
    import sys

    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    import base64
    import hashlib
    import hmac
    import inspect
    import marshal
    import threading
    import types

    class _MessageSender:
        def send_data(self, data):
            pass

    class _SocketSender(_MessageSender):
        def __init__(self, port, key):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            self.my_file = s.makefile("wb")
            self.key = base64.b64decode(key)

        def send_data(self, data):
            if not self.my_file.closed:
                pickled_data = base64.b64encode(
                    pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
                )
                dgst = hmac.new(self.key, pickled_data, hashlib.sha256).digest()
                self.my_file.write(base64.b64encode(dgst) + b":" + pickled_data + b"\n")

        def close(self):
            self.my_file.close()

    class _FileSender(_MessageSender):
        def __init__(self, file_name):
            self.my_file = open(file_name, "wb")

        def send_data(self, data):
            if not self.my_file.closed:
                marshal.dump(data, self.my_file)

        def close(self):
            self.my_file.close()

    def _cached(func):
        cache = {}

        def newfunc(self, arg):
            if arg in cache:
                return cache[arg]
            result = func(self, arg)
            cache[arg] = result
            return result

        return newfunc

    class _FunctionCallDataSender:
        def __init__(self, send_info, project_root):
            self.project_root = project_root
            if send_info[0].isdigit():
                port, key = send_info.split(":", 1)
                self.sender = _SocketSender(int(port), key)
            else:
                self.sender = _FileSender(send_info)

            def global_trace(frame, event, arg):
                # HACK: Ignoring out->in calls
                # This might lose some information
                if self._is_an_interesting_call(frame):
                    return self.on_function_call

            sys.settrace(global_trace)
            threading.settrace(global_trace)

        def on_function_call(self, frame, event, arg):
            if event != "return":
                return
            args = []
            returned = ("unknown",)
            code = frame.f_code
            for argname in code.co_varnames[: code.co_argcount]:
                try:
                    argvalue = self._object_to_persisted_form(frame.f_locals[argname])
                    args.append(argvalue)
                except (TypeError, AttributeError):
                    args.append(("unknown",))
            try:
                returned = self._object_to_persisted_form(arg)
            except (TypeError, AttributeError):
                pass
            try:
                data = (
                    self._object_to_persisted_form(frame.f_code),
                    tuple(args),
                    returned,
                )
                self.sender.send_data(data)
            except (TypeError):
                pass
            return self.on_function_call

        def _is_an_interesting_call(self, frame):
            # if frame.f_code.co_name in ['?', '<module>']:
            #    return False
            # return not frame.f_back or
            #    not self._is_code_inside_project(frame.f_back.f_code)
            if not self._is_code_inside_project(frame.f_code) and (
                not frame.f_back
                or not self._is_code_inside_project(frame.f_back.f_code)
            ):
                return False
            return True

        def _is_code_inside_project(self, code):
            source = self._path(code.co_filename)
            return (
                source is not None
                and os.path.exists(source)
                and _realpath(source).startswith(self.project_root)
            )

        @_cached
        def _get_persisted_code(self, object_):
            source = self._path(object_.co_filename)
            if not os.path.exists(source):
                raise TypeError("no source")
            return ("defined", _realpath(source), str(object_.co_firstlineno))

        @_cached
        def _get_persisted_class(self, object_):
            try:
                return (
                    "defined",
                    _realpath(inspect.getsourcefile(object_)),
                    object_.__name__,
                )
            except (TypeError, AttributeError):
                return ("unknown",)

        def _get_persisted_builtin(self, object_):
            if isinstance(object_, str):
                return ("builtin", "str")
            if isinstance(object_, list):
                holding = None
                if len(object_) > 0:
                    holding = object_[0]
                return ("builtin", "list", self._object_to_persisted_form(holding))
            if isinstance(object_, dict):
                keys = None
                values = None
                if len(object_) > 0:
                    # @todo - fix it properly, why is __locals__ being
                    # duplicated ?
                    keys = [key for key in object_.keys() if key != "__locals__"][0]
                    values = object_[keys]
                return (
                    "builtin",
                    "dict",
                    self._object_to_persisted_form(keys),
                    self._object_to_persisted_form(values),
                )
            if isinstance(object_, tuple):
                objects = []
                if len(object_) < 3:
                    for holding in object_:
                        objects.append(self._object_to_persisted_form(holding))
                else:
                    objects.append(self._object_to_persisted_form(object_[0]))
                return tuple(["builtin", "tuple"] + objects)
            if isinstance(object_, set):
                holding = None
                if len(object_) > 0:
                    for o in object_:
                        holding = o
                        break
                return ("builtin", "set", self._object_to_persisted_form(holding))
            return ("unknown",)

        def _object_to_persisted_form(self, object_):
            if object_ is None:
                return ("none",)
            if isinstance(object_, types.CodeType):
                return self._get_persisted_code(object_)
            if isinstance(object_, types.FunctionType):
                return self._get_persisted_code(object_.__code__)
            if isinstance(object_, types.MethodType):
                return self._get_persisted_code(object_.__func__.__code__)
            if isinstance(object_, types.ModuleType):
                return self._get_persisted_module(object_)
            if isinstance(object_, (str, list, dict, tuple, set)):
                return self._get_persisted_builtin(object_)
            if isinstance(object_, type):
                return self._get_persisted_class(object_)
            return ("instance", self._get_persisted_class(type(object_)))

        @_cached
        def _get_persisted_module(self, object_):
            path = self._path(object_.__file__)
            if path and os.path.exists(path):
                return ("defined", _realpath(path))
            return ("unknown",)

        def _path(self, path):
            if path.endswith(".pyc"):
                path = path[:-1]
            if path.endswith(".py"):
                return path

        def close(self):
            self.sender.close()
            sys.settrace(None)

    def _realpath(path):
        return os.path.realpath(os.path.abspath(os.path.expanduser(path)))

    send_info = sys.argv[1]
    project_root = sys.argv[2]
    file_to_run = sys.argv[3]
    run_globals = globals()
    run_globals.update(
        {"__name__": "__main__", "__builtins__": __builtins__, "__file__": file_to_run}
    )

    if send_info != "-":
        data_sender = _FunctionCallDataSender(send_info, project_root)
    del sys.argv[1:4]
    with open(file_to_run) as f:
        code = compile(f.read(), file_to_run, "exec")
        exec(code, run_globals)
    if send_info != "-":
        data_sender.close()


if __name__ == "__main__":
    __rope_start_everything()
