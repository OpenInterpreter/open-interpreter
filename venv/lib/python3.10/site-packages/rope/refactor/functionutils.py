from rope.base import pyobjects, worder
from rope.base.builtins import Lambda


class DefinitionInfo:
    def __init__(
        self, function_name, is_method, args_with_defaults, args_arg, keywords_arg
    ):
        self.function_name = function_name
        self.is_method = is_method
        self.args_with_defaults = args_with_defaults
        self.args_arg = args_arg
        self.keywords_arg = keywords_arg

    def to_string(self):
        return f"{self.function_name}({self.arguments_to_string()})"

    def arguments_to_string(self, from_index=0):
        params = []
        for arg, default in self.args_with_defaults:
            if default is not None:
                params.append(f"{arg}={default}")
            else:
                params.append(arg)
        if self.args_arg is not None:
            params.append("*" + self.args_arg)
        if self.keywords_arg:
            params.append("**" + self.keywords_arg)
        return ", ".join(params[from_index:])

    @staticmethod
    def _read(pyfunction, code):
        kind = pyfunction.get_kind()
        is_method = kind == "method"
        is_lambda = kind == "lambda"
        info = _FunctionParser(code, is_method, is_lambda)
        args, keywords = info.get_parameters()
        args_arg = None
        keywords_arg = None
        if args and args[-1].startswith("**"):
            keywords_arg = args[-1][2:]
            del args[-1]
        if args and args[-1].startswith("*"):
            args_arg = args[-1][1:]
            del args[-1]
        args_with_defaults = [(name, None) for name in args]
        args_with_defaults.extend(keywords)
        return DefinitionInfo(
            info.get_function_name(),
            is_method,
            args_with_defaults,
            args_arg,
            keywords_arg,
        )

    @staticmethod
    def read(pyfunction):
        pymodule = pyfunction.get_module()
        word_finder = worder.Worder(pymodule.source_code)
        lineno = pyfunction.get_ast().lineno
        start = pymodule.lines.get_line_start(lineno)
        if isinstance(pyfunction, Lambda):
            call = word_finder.get_lambda_and_args(start)
        else:
            call = word_finder.get_function_and_args_in_header(start)
        return DefinitionInfo._read(pyfunction, call)


class CallInfo:
    def __init__(
        self,
        function_name,
        args,
        keywords,
        args_arg,
        keywords_arg,
        implicit_arg,
        constructor,
    ):
        self.function_name = function_name
        self.args = args
        self.keywords = keywords
        self.args_arg = args_arg
        self.keywords_arg = keywords_arg
        self.implicit_arg = implicit_arg
        self.constructor = constructor

    def to_string(self):
        function = self.function_name
        if self.implicit_arg:
            function = self.args[0] + "." + self.function_name
        params = []
        start = 0
        if self.implicit_arg or self.constructor:
            start = 1
        if self.args[start:]:
            params.extend(self.args[start:])
        if self.keywords:
            params.extend([f"{name}={value}" for name, value in self.keywords])
        if self.args_arg is not None:
            params.append("*" + self.args_arg)
        if self.keywords_arg:
            params.append("**" + self.keywords_arg)
        return "{}({})".format(function, ", ".join(params))

    @staticmethod
    def read(primary, pyname, definition_info, code):
        is_method_call = CallInfo._is_method_call(primary, pyname)
        is_constructor = CallInfo._is_class(pyname)
        is_classmethod = CallInfo._is_classmethod(pyname)
        info = _FunctionParser(code, is_method_call or is_classmethod)
        args, keywords = info.get_parameters()
        args_arg = None
        keywords_arg = None
        if args and args[-1].startswith("**"):
            keywords_arg = args[-1][2:]
            del args[-1]
        if args and args[-1].startswith("*"):
            args_arg = args[-1][1:]
            del args[-1]
        if is_constructor:
            args.insert(0, definition_info.args_with_defaults[0][0])
        return CallInfo(
            info.get_function_name(),
            args,
            keywords,
            args_arg,
            keywords_arg,
            is_method_call or is_classmethod,
            is_constructor,
        )

    @staticmethod
    def _is_method_call(primary, pyname):
        return (
            primary is not None
            and isinstance(primary.get_object().get_type(), pyobjects.PyClass)
            and CallInfo._is_method(pyname)
        )

    @staticmethod
    def _is_class(pyname):
        return pyname is not None and isinstance(pyname.get_object(), pyobjects.PyClass)

    @staticmethod
    def _is_method(pyname):
        if pyname is not None and isinstance(pyname.get_object(), pyobjects.PyFunction):
            return pyname.get_object().get_kind() == "method"
        return False

    @staticmethod
    def _is_classmethod(pyname):
        if pyname is not None and isinstance(pyname.get_object(), pyobjects.PyFunction):
            return pyname.get_object().get_kind() == "classmethod"
        return False


class ArgumentMapping:
    def __init__(self, definition_info, call_info):
        self.call_info = call_info
        self.param_dict = {}
        self.keyword_args = []
        self.args_arg = []
        for index, value in enumerate(call_info.args):
            if index < len(definition_info.args_with_defaults):
                name = definition_info.args_with_defaults[index][0]
                self.param_dict[name] = value
            else:
                self.args_arg.append(value)
        for name, value in call_info.keywords:
            index = -1
            for pair in definition_info.args_with_defaults:
                if pair[0] == name:
                    self.param_dict[name] = value
                    break
            else:
                self.keyword_args.append((name, value))

    def to_call_info(self, definition_info):
        args = []
        keywords = []
        for index in range(len(definition_info.args_with_defaults)):
            name = definition_info.args_with_defaults[index][0]
            if name in self.param_dict:
                args.append(self.param_dict[name])
            else:
                for i in range(index, len(definition_info.args_with_defaults)):
                    name = definition_info.args_with_defaults[i][0]
                    if name in self.param_dict:
                        keywords.append((name, self.param_dict[name]))
                break
        args.extend(self.args_arg)
        keywords.extend(self.keyword_args)
        return CallInfo(
            self.call_info.function_name,
            args,
            keywords,
            self.call_info.args_arg,
            self.call_info.keywords_arg,
            self.call_info.implicit_arg,
            self.call_info.constructor,
        )


class _FunctionParser:
    def __init__(self, call, implicit_arg, is_lambda=False):
        self.call = call
        self.implicit_arg = implicit_arg
        self.word_finder = worder.Worder(self.call)
        if is_lambda:
            self.last_parens = self.call.rindex(":")
        else:
            self.last_parens = self.call.rindex(")")
        self.first_parens = self.word_finder._find_parens_start(self.last_parens)

    def get_parameters(self):
        args, keywords = self.word_finder.get_parameters(
            self.first_parens, self.last_parens
        )
        if self.is_called_as_a_method():
            instance = self.call[: self.call.rindex(".", 0, self.first_parens)]
            args.insert(0, instance.strip())
        return args, keywords

    def get_instance(self):
        if self.is_called_as_a_method():
            return self.word_finder.get_primary_at(
                self.call.rindex(".", 0, self.first_parens) - 1
            )

    def get_function_name(self):
        if self.is_called_as_a_method():
            return self.word_finder.get_word_at(self.first_parens - 1)
        else:
            return self.word_finder.get_primary_at(self.first_parens - 1)

    def is_called_as_a_method(self):
        return self.implicit_arg and "." in self.call[: self.first_parens]
