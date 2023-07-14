import collections
import numbers
import re
import warnings
from itertools import chain

from rope.base import ast, codeanalyze, exceptions

COMMA_IN_WITH_PATTERN = re.compile(r"\(.*?\)|(,)")


def get_patched_ast(source, sorted_children=False):
    """Adds ``region`` and ``sorted_children`` fields to nodes

    Adds ``sorted_children`` field only if `sorted_children` is True.

    """
    return patch_ast(ast.parse(source), source, sorted_children)


def patch_ast(node, source, sorted_children=False):
    """Patches the given node

    After calling, each node in `node` will have a new field named
    `region` that is a tuple containing the start and end offsets
    of the code that generated it.

    If `sorted_children` is true, a `sorted_children` field will
    be created for each node, too.  It is a list containing child
    nodes as well as whitespaces and comments that occur between
    them.

    """
    if hasattr(node, "region"):
        return node
    walker = _PatchingASTWalker(source, children=sorted_children)
    walker(node)
    return node


def node_region(patched_ast_node):
    """Get the region of a patched ast node"""
    return patched_ast_node.region


def write_ast(patched_ast_node):
    """Extract source form a patched AST node with `sorted_children` field

    If the node is patched with sorted_children turned off you can use
    `node_region` function for obtaining code using module source code.
    """
    result = []
    for child in patched_ast_node.sorted_children:
        if isinstance(child, ast.AST):
            result.append(write_ast(child))
        else:
            result.append(child)
    return "".join(result)


class MismatchedTokenError(exceptions.RopeError):
    pass


class _PatchingASTWalker:
    def __init__(self, source, children=False):
        self.source = _Source(source)
        self.children = children
        self.lines = codeanalyze.SourceLinesAdapter(source)
        self.children_stack = []

    Number = object()
    String = object()
    with_or_comma_context_manager = object()
    empty_tuple = object()

    def __call__(self, node):
        method = getattr(self, "_" + node.__class__.__name__, None)
        if method is not None:
            return method(node)
        # ???: Unknown node; what should we do here?
        warnings.warn(
            "Unknown node type <%s>; please report!" % node.__class__.__name__,
            RuntimeWarning,
        )
        node.region = (self.source.offset, self.source.offset)
        if self.children:
            node.sorted_children = [child for field, child in ast.iter_fields(node)]

    def _handle(self, node, base_children, eat_parens=False, eat_spaces=False):
        if hasattr(node, "region"):
            # ???: The same node was seen twice; what should we do?
            warnings.warn(
                "Node <%s> has been already patched; please report!"
                % node.__class__.__name__,
                RuntimeWarning,
            )
            return

        base_children = collections.deque(base_children)
        self.children_stack.append(base_children)
        children = collections.deque()
        formats = []
        suspected_start = self.source.offset
        start = suspected_start
        first_token = True
        while base_children:
            child = base_children.popleft()
            if child is None:
                continue
            offset = self.source.offset
            if isinstance(child, ast.AST):
                self(child)
                token_start = child.region[0]
            else:
                if child is self.String:
                    region = self.source.consume_string(
                        end=self._find_next_statement_start()
                    )
                elif child is self.Number:
                    region = self.source.consume_number()
                elif child == self.empty_tuple:
                    region = self.source.consume_empty_tuple()
                elif child == self.with_or_comma_context_manager:
                    region = self.source.consume_with_or_comma_context_manager()
                elif isinstance(node, (ast.JoinedStr, ast.FormattedValue)):
                    region = self.source.consume_joined_string(child)
                else:
                    region = self.source.consume(child)
                child = self.source[region[0] : region[1]]
                token_start = region[0]
            if not first_token:
                if not isinstance(node, ast.JoinedStr):
                    formats.append(self.source[offset:token_start])
                if self.children:
                    children.append(self.source[offset:token_start])
            else:
                first_token = False
                start = token_start
            if self.children:
                children.append(child)
        start = self._handle_parens(children, start, formats)
        if eat_parens:
            start = self._eat_surrounding_parens(children, suspected_start, start)
        if eat_spaces:
            if self.children:
                children.appendleft(self.source[0:start])
            end_spaces = self.source[self.source.offset :]
            self.source.consume(end_spaces)
            if self.children:
                children.append(end_spaces)
            start = 0
        if self.children:
            node.sorted_children = children
        node.region = (start, self.source.offset)
        self.children_stack.pop()

    def _handle_parens(self, children, start, formats):
        """Changes `children` and returns new start"""
        opens, closes = self._count_needed_parens(formats)
        old_end = self.source.offset
        new_end = None
        for i in range(closes):
            new_end = self.source.consume(")")[1]
        if new_end is not None and self.children:
            children.append(self.source[old_end:new_end])
        new_start = start
        for i in range(opens):
            new_start = self.source.rfind_token("(", 0, new_start)
        if new_start != start:
            if self.children:
                children.appendleft(self.source[new_start:start])
            start = new_start
        return start

    def _eat_surrounding_parens(self, children, suspected_start, start):
        index = self.source.rfind_token("(", suspected_start, start)
        if index is not None:
            old_start = start
            old_offset = self.source.offset
            start = index
            if self.children:
                children.appendleft(self.source[start + 1 : old_start])
                children.appendleft("(")
            token_start, token_end = self.source.consume(")")
            if self.children:
                children.append(self.source[old_offset:token_start])
                children.append(")")
        return start

    def _count_needed_parens(self, children):
        start = 0
        opens = 0
        for child in children:
            if not isinstance(child, (str, bytes)):
                continue
            if child == "" or child[0] in "'\"":
                continue
            index = 0
            while index < len(child):
                if child[index] == ")":
                    if opens > 0:
                        opens -= 1
                    else:
                        start += 1
                if child[index] == "(":
                    opens += 1
                if child[index] == "#":
                    try:
                        index = child.index("\n", index)
                    except ValueError:
                        break
                index += 1
        return start, opens

    def _find_next_statement_start(self):
        for children in reversed(self.children_stack):
            for child in children:
                if isinstance(child, ast.stmt):
                    return child.col_offset + self.lines.get_line_start(child.lineno)
        return len(self.source.source)

    def _join(self, iterable, separator):
        iterable = iter(iterable)
        try:
            yield next(iterable)
        except StopIteration:
            return
        for child in iterable:
            yield separator
            yield child

    def _flatten_keywords(self, iterable):
        iterable = ([attr, "=", pattern] for attr, pattern in iterable)
        iterable = self._join(iterable, separator=[","])
        return chain.from_iterable(iterable)

    def _child_nodes(self, nodes, separator):
        return list(self._join(nodes, separator=separator))

    _operators = {
        "And": "and",
        "Or": "or",
        "Add": "+",
        "Sub": "-",
        "Mult": "*",
        "Div": "/",
        "Mod": "%",
        "Pow": "**",
        "MatMult": "@",
        "LShift": "<<",
        "RShift": ">>",
        "BitOr": "|",
        "BitAnd": "&",
        "BitXor": "^",
        "FloorDiv": "//",
        "Invert": "~",
        "Not": "not",
        "UAdd": "+",
        "USub": "-",
        "Eq": "==",
        "NotEq": "!=",
        "Lt": "<",
        "LtE": "<=",
        "Gt": ">",
        "GtE": ">=",
        "Is": "is",
        "IsNot": "is not",
        "In": "in",
        "NotIn": "not in",
    }

    def _get_op(self, node):
        return self._operators[node.__class__.__name__].split(" ")

    def _Attribute(self, node):
        self._handle(node, [node.value, ".", node.attr])

    def _Assert(self, node):
        children = ["assert", node.test]
        if node.msg:
            children.append(",")
            children.append(node.msg)
        self._handle(node, children)

    def _Assign(self, node):
        children = [*self._child_nodes(node.targets, "="), "=", node.value]
        self._handle(node, children)

    def _AugAssign(self, node):
        children = [node.target, *self._get_op(node.op), "=", node.value]
        self._handle(node, children)

    def _AnnAssign(self, node):
        children = [node.target, ":", node.annotation]
        if node.value is not None:
            children.append("=")
            children.append(node.value)
        self._handle(node, children)

    def _BinOp(self, node):
        children = [node.left] + self._get_op(node.op) + [node.right]
        self._handle(node, children)

    def _BoolOp(self, node):
        self._handle(node, self._child_nodes(node.values, self._get_op(node.op)[0]))

    def _Break(self, node):
        self._handle(node, ["break"])

    def _Call(self, node):
        def _arg_sort_key(node):
            if isinstance(node, ast.keyword):
                return (node.value.lineno, node.value.col_offset)
            return (node.lineno, node.col_offset)

        children = [node.func, "("]
        args = sorted([*node.args, *node.keywords], key=_arg_sort_key)
        children.extend(self._child_nodes(args, ","))
        children.append(")")
        self._handle(node, children)

    def _ClassDef(self, node):
        children = []
        for decorator in node.decorator_list:
            children.extend(("@", decorator))
        children.extend(["class", node.name])
        if node.bases:
            children.append("(")
            children.extend(self._child_nodes(node.bases, ","))
            children.append(")")
        children.append(":")
        children.extend(node.body)
        self._handle(node, children)

    def _Compare(self, node):
        children = []
        children.append(node.left)
        for op, expr in zip(node.ops, node.comparators):
            children.extend(self._get_op(op))
            children.append(expr)
        self._handle(node, children)

    def _Delete(self, node):
        self._handle(node, ["del"] + self._child_nodes(node.targets, ","))

    def _Constant(self, node):
        if isinstance(node.value, (str, bytes)):
            self._handle(node, [self.String])
            return

        if any(node.value is v for v in [True, False, None]):
            self._handle(node, [str(node.value)])
            return

        if isinstance(node.value, numbers.Number):
            self._handle(node, [self.Number])
            return

        if node.value is Ellipsis:
            self._handle(node, ["..."])
            return

        assert False

    def _Num(self, node):
        self._handle(node, [self.Number])

    def _Str(self, node):
        self._handle(node, [self.String])

    def _Bytes(self, node):
        self._handle(node, [self.String])

    def _JoinedStr(self, node):
        def start_quote_char():
            possible_quotes = [
                (self.source.source.find(q, start, end), q) for q in QUOTE_CHARS
            ]
            quote_pos, quote_char = min(
                (pos, q) for pos, q in possible_quotes if pos != -1
            )
            return self.source[start : quote_pos + len(quote_char)]

        def end_quote_char():
            possible_quotes = [
                (self.source.source.rfind(q, start, end), q)
                for q in reversed(QUOTE_CHARS)
            ]
            _, quote_pos, quote_char = max(
                (len(q), pos, q) for pos, q in possible_quotes if pos != -1
            )
            return self.source[end - len(quote_char) : end]

        QUOTE_CHARS = ['"""', "'''", '"', "'"]
        offset = self.source.offset
        start, end = self.source.consume_string(
            end=self._find_next_statement_start(),
        )
        self.source.offset = offset

        children = []
        children.append(start_quote_char())
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                children.append(part)
        children.append(end_quote_char())
        self._handle(node, children)

    def _FormattedValue(self, node):
        children = []
        children.append("{")
        children.append(node.value)
        if node.format_spec:
            children.append(":")
            for val in node.format_spec.values:
                if isinstance(val, ast.FormattedValue):
                    children.append(val.value)
                else:
                    children.append(val.s)
        children.append("}")
        self._handle(node, children)

    def _Continue(self, node):
        self._handle(node, ["continue"])

    def _Dict(self, node):
        children = []
        children.append("{")
        if node.keys:
            for index, (key, value) in enumerate(zip(node.keys, node.values)):
                if key is None:
                    # PEP-448 dict unpacking: {a: b, **unpack}
                    children.extend(["**", value])
                else:
                    children.extend([key, ":", value])
                if index < len(node.keys) - 1:
                    children.append(",")
        children.append("}")
        self._handle(node, children)

    def _Ellipsis(self, node):
        self._handle(node, ["..."])

    def _Expr(self, node):
        self._handle(node, [node.value])

    def _NamedExpr(self, node):
        children = [node.target, ":=", node.value]
        self._handle(node, children)

    def _ExtSlice(self, node):
        children = []
        for index, dim in enumerate(node.dims):
            if index > 0:
                children.append(",")
            children.append(dim)
        self._handle(node, children)

    def _handle_for_loop_node(self, node, is_async):
        children = ["async", "for"] if is_async else ["for"]
        children.extend([node.target, "in", node.iter, ":"])
        children.extend(node.body)
        if node.orelse:
            children.extend(["else", ":"])
            children.extend(node.orelse)
        self._handle(node, children)

    def _For(self, node):
        self._handle_for_loop_node(node, is_async=False)

    def _AsyncFor(self, node):
        self._handle_for_loop_node(node, is_async=True)

    def _ImportFrom(self, node):
        children = ["from"]
        if node.level:
            children.extend("." * node.level)
        if node.module:
            children.extend(node.module.split("."))
        children.append("import")
        children.extend(self._child_nodes(node.names, ","))
        self._handle(node, children)

    def _alias(self, node):
        children = node.name.split(".")
        if node.asname:
            children.extend(["as", node.asname])
        self._handle(node, children)

    def _handle_function_def_node(self, node, is_async):
        children = []
        for decorator in node.decorator_list:
            children.extend(("@", decorator))
        children.extend(["async", "def"] if is_async else ["def"])
        children.append(node.name)
        children.extend(["(", node.args, ")"])
        children.append(":")
        children.extend(node.body)
        self._handle(node, children)

    def _FunctionDef(self, node):
        self._handle_function_def_node(node, is_async=False)

    def _AsyncFunctionDef(self, node):
        self._handle_function_def_node(node, is_async=True)

    def _arguments(self, node):
        children = []
        args = list(node.args)
        defaults = [None] * (len(args) - len(node.defaults)) + list(node.defaults)
        for index, (arg, default) in enumerate(zip(args, defaults)):
            if index > 0:
                children.append(",")
            self._add_args_to_children(children, arg, default)
        if node.vararg is not None:
            if args:
                children.append(",")
            children.extend(["*", node.vararg.arg])
        if node.kwarg is not None:
            if args or node.vararg is not None:
                children.append(",")
            children.extend(["**", node.kwarg.arg])
        self._handle(node, children)

    def _add_args_to_children(self, children, arg, default):
        if isinstance(arg, (list, tuple)):
            self._add_tuple_parameter(children, arg)
        else:
            children.append(arg)
        if default is not None:
            children.append("=")
            children.append(default)

    def _add_tuple_parameter(self, children, arg):
        children.append("(")
        for index, token in enumerate(arg):
            if index > 0:
                children.append(",")
            if isinstance(token, (list, tuple)):
                self._add_tuple_parameter(children, token)
            else:
                children.append(token)
        children.append(")")

    def _GeneratorExp(self, node):
        children = [node.elt, *node.generators]
        self._handle(node, children, eat_parens=True)

    def _comprehension(self, node):
        children = ["for", node.target, "in", node.iter]
        for if_ in node.ifs:
            children.extend(["if", if_])
        self._handle(node, children)

    def _Global(self, node):
        children = ["global", *self._child_nodes(node.names, ",")]
        self._handle(node, children)

    def _If(self, node):
        children = ["elif"] if self._is_elif(node) else ["if"]
        children.extend([node.test, ":"])
        children.extend(node.body)
        if node.orelse:
            if len(node.orelse) == 1 and self._is_elif(node.orelse[0]):
                pass
            else:
                children.extend(["else", ":"])
            children.extend(node.orelse)
        self._handle(node, children)

    def _is_elif(self, node):
        if not isinstance(node, ast.If):
            return False
        offset = self.lines.get_line_start(node.lineno) + node.col_offset
        word = self.source[offset : offset + 4]
        # XXX: This is a bug; the offset does not point to the first
        alt_word = self.source[offset - 5 : offset - 1]
        return "elif" in (word, alt_word)

    def _IfExp(self, node):
        return self._handle(node, [node.body, "if", node.test, "else", node.orelse])

    def _Import(self, node):
        children = ["import", *self._child_nodes(node.names, ",")]
        self._handle(node, children)

    def _keyword(self, node):
        if node.arg is None:
            children = [node.value]
        else:
            children = [node.arg, "=", node.value]
        self._handle(node, children)

    def _Lambda(self, node):
        self._handle(node, ["lambda", node.args, ":", node.body])

    def _List(self, node):
        self._handle(node, ["[", *self._child_nodes(node.elts, ","), "]"])

    def _ListComp(self, node):
        children = ["[", node.elt, *node.generators, "]"]
        self._handle(node, children)

    def _Set(self, node):
        if node.elts:
            self._handle(node, ["{", *self._child_nodes(node.elts, ","), "}"])
            return
        # Python doesn't have empty set literals
        warnings.warn(
            "Tried to handle empty <Set> literal; please report!", RuntimeWarning
        )
        self._handle(node, ["set(", ")"])

    def _SetComp(self, node):
        children = ["{", node.elt, *node.generators, "}"]
        self._handle(node, children)

    def _DictComp(self, node):
        children = ["{", *[node.key, ":", node.value], *node.generators, "}"]
        self._handle(node, children)

    def _Module(self, node):
        self._handle(node, list(node.body), eat_spaces=True)

    def _Name(self, node):
        self._handle(node, [node.id])

    def _NameConstant(self, node):
        self._handle(node, [str(node.value)])

    def _arg(self, node):
        self._handle(node, [node.arg])

    def _Pass(self, node):
        self._handle(node, ["pass"])

    def _Raise(self, node):
        children = ["raise"]
        if node.exc:
            children.append(node.exc)
        if node.cause:
            children.append("from")
            children.append(node.cause)
        self._handle(node, children)

    def _Return(self, node):
        children = ["return"]
        if node.value:
            children.append(node.value)
        self._handle(node, children)

    def _Index(self, node):
        self._handle(node, [node.value])

    def _Subscript(self, node):
        self._handle(node, [node.value, "[", node.slice, "]"])

    def _Slice(self, node):
        children = []
        if node.lower:
            children.append(node.lower)
        children.append(":")
        if node.upper:
            children.append(node.upper)
        if node.step:
            children.append(":")
            children.append(node.step)
        self._handle(node, children)

    def _TryFinally(self, node):
        # @todo fixme
        is_there_except_handler = False
        not_empty_body = True
        if len(node.finalbody) == 1:
            try:
                is_there_except_handler = isinstance(
                    node.handlers[0], ast.ExceptHandler
                )
                not_empty_body = True
            except IndexError:
                pass
        children = []
        if not_empty_body or not is_there_except_handler:
            children.extend(["try", ":"])
        children.extend(node.body)
        children.extend(node.handlers)
        children.extend(["finally", ":"])
        children.extend(node.finalbody)
        self._handle(node, children)

    def _TryExcept(self, node):
        children = ["try", ":"]
        children.extend(node.body)
        children.extend(node.handlers)
        if node.orelse:
            children.extend(["else", ":"])
            children.extend(node.orelse)
        self._handle(node, children)

    def _Try(self, node):
        if len(node.finalbody):
            self._TryFinally(node)
        else:
            self._TryExcept(node)

    def _ExceptHandler(self, node):
        self._excepthandler(node)

    def _excepthandler(self, node):
        children = ["except"]
        if node.type:
            children.append(node.type)
        if node.name:
            children.append("as")
            children.append(node.name)
        children.append(":")
        children.extend(node.body)

        self._handle(node, children)

    def _Tuple(self, node):
        if node.elts:
            self._handle(node, self._child_nodes(node.elts, ","), eat_parens=True)
        else:
            self._handle(node, [self.empty_tuple])

    def _UnaryOp(self, node):
        children = self._get_op(node.op)
        children.append(node.operand)
        self._handle(node, children)

    def _Await(self, node):
        children = ["await"]
        if node.value:
            children.append(node.value)
        self._handle(node, children)

    def _Yield(self, node):
        children = ["yield"]
        if node.value:
            children.append(node.value)
        self._handle(node, children)

    def _YieldFrom(self, node):
        children = ["yield", "from", node.value]
        self._handle(node, children)

    def _While(self, node):
        children = ["while", node.test, ":"]
        children.extend(node.body)
        if node.orelse:
            children.extend(["else", ":"])
            children.extend(node.orelse)
        self._handle(node, children)

    def _handle_with_node(self, node, is_async):
        children = []

        if is_async:
            children.extend(["async"])
        for item in node.items:
            children.extend([self.with_or_comma_context_manager, item.context_expr])
            if item.optional_vars:
                children.extend(["as", item.optional_vars])
        children.append(":")
        children.extend(node.body)
        self._handle(node, children)

    def _With(self, node):
        self._handle_with_node(node, is_async=False)

    def _AsyncWith(self, node):
        self._handle_with_node(node, is_async=True)

    def _Starred(self, node):
        self._handle(node, [node.value])

    def _Match(self, node):
        children = ["match", node.subject, ":"]
        children.extend(node.cases)
        self._handle(node, children)

    def _match_case(self, node):
        children = ["case", node.pattern]
        if node.guard:
            children.extend(["if", node.guard])
        children.append(":")
        children.extend(node.body)
        self._handle(node, children)

    def _MatchAs(self, node):
        if node.pattern:
            children = [node.pattern, "as", node.name]
        elif node.name is None:
            children = ["_"]
        else:
            children = [node.name]
        self._handle(node, children)

    def _MatchClass(self, node):
        children = [
            node.cls,
            "(",
            *self._child_nodes(node.patterns, ","),
            *self._flatten_keywords(zip(node.kwd_attrs, node.kwd_patterns)),
            ")",
        ]
        self._handle(node, children)

    def _MatchValue(self, node):
        self._handle(node, [node.value])

    def _MatchMapping(self, node):
        children = []
        children.append("{")
        for index, (key, value) in enumerate(zip(node.keys, node.patterns)):
            children.extend([key, ":", value])
            if index < len(node.keys) - 1:
                children.append(",")
        children.append("}")
        self._handle(node, children)


class _Source:
    def __init__(self, source):
        self.source = source
        self.offset = 0

    def consume(self, token, skip_comment=True):
        try:
            while True:
                new_offset = self.source.index(token, self.offset)
                if self._good_token(token, new_offset) or not skip_comment:
                    break
                else:
                    self._skip_comment()
        except (ValueError, TypeError):
            raise MismatchedTokenError(
                f"Token <{token}> at {self._get_location()} cannot be matched"
            )
        self.offset = new_offset + len(token)
        return (new_offset, self.offset)

    def consume_joined_string(self, token):
        new_offset = self.source.index(token, self.offset)
        self.offset = new_offset + len(token)
        return (new_offset, self.offset)

    def consume_string(self, end=None):
        if _Source._string_pattern is None:
            string_pattern = codeanalyze.get_string_pattern()
            formatted_string_pattern = codeanalyze.get_formatted_string_pattern()
            original = r"(?:{})|(?:{})".format(
                string_pattern,
                formatted_string_pattern,
            )
            pattern = r"({})((\s|\\\n|#[^\n]*\n)*({}))*".format(
                original,
                original,
            )
            _Source._string_pattern = re.compile(pattern)
        repattern = _Source._string_pattern
        return self._consume_pattern(repattern, end)

    def consume_number(self):
        if _Source._number_pattern is None:
            _Source._number_pattern = re.compile(self._get_number_pattern())
        repattern = _Source._number_pattern
        return self._consume_pattern(repattern)

    def consume_empty_tuple(self):
        return self._consume_pattern(re.compile(r"\(\s*\)"))

    def consume_with_or_comma_context_manager(self):
        repattern = re.compile(r"with|,")
        return self._consume_pattern(repattern)

    def _good_token(self, token, offset, start=None):
        """Checks whether consumed token is in comments"""
        if start is None:
            start = self.offset
        try:
            comment_index = self.source.rindex("#", start, offset)
        except ValueError:
            return True
        try:
            new_line_index = self.source.rindex("\n", start, offset)
        except ValueError:
            return False
        return comment_index < new_line_index

    def _skip_comment(self):
        self.offset = self.source.index("\n", self.offset + 1)

    def _get_location(self):
        lines = self.source[: self.offset].split("\n")
        return (len(lines), len(lines[-1]))

    def _consume_pattern(self, repattern, end=None):
        while True:
            if end is None:
                end = len(self.source)
            match = repattern.search(self.source, self.offset, end)
            if self._good_token(match.group(), match.start()):
                break
            else:
                self._skip_comment()
        self.offset = match.end()
        return match.start(), match.end()

    def till_token(self, token):
        new_offset = self.source.index(token, self.offset)
        return self[self.offset : new_offset]

    def rfind_token(self, token, start, end):
        index = start
        while True:
            try:
                index = self.source.rindex(token, start, end)
                if self._good_token(token, index, start=start):
                    return index
                else:
                    end = index
            except ValueError:
                return None

    def from_offset(self, offset):
        return self[offset : self.offset]

    def find_backwards(self, pattern, offset):
        return self.source.rindex(pattern, 0, offset)

    def __getitem__(self, index):
        return self.source[index]

    def __getslice__(self, i, j):
        return self.source[i:j]

    def _get_number_pattern(self):
        # HACK: It is merely an approaximation and does the job
        integer = r"\-?(0[xo][\da-fA-F]+|\d+)"
        return r"(%s(\.\d*)?|(\.\d+))([eE][-+]?\d+)?[jJ]?" % integer

    _string_pattern = None
    _number_pattern = None
