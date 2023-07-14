# Based on super lightweight Simple Top-Down Parser from http://effbot.org/zone/simple-top-down-parsing.htm
# and https://bitbucket.org/emacsway/sqlbuilder/src/default/sqlbuilder/smartsql/contrib/evaluate.py
import re

from rope.base import utils as base_utils
from rope.base.oi.type_hinting import utils


class SymbolBase:

    name = None  # node/token type name

    def __init__(self):
        self.value = None  # used by name and literals
        self.first = None
        self.second = None
        self.third = None  # used by tree nodes

    def nud(self, parser):
        raise SyntaxError("Syntax error (%r)." % self.name)

    def led(self, left, parser):
        raise SyntaxError("Unknown operator (%r)." % self.name)

    def evaluate(self, pyobject):
        raise NotImplementedError(self.name, self)

    def __repr__(self):
        if self.name == "(name)":
            return f"({self.name[1:-1]} {self.value})"
        out = [repr(self.name), self.first, self.second, self.third]
        out = [str(i) for i in out if i]
        return "(" + " ".join(out) + ")"


class SymbolTable:
    def multi(func):
        def _inner(self, names, *a, **kw):
            for name in names.split():
                func(self, name, *a, **kw)

        return _inner

    def __init__(self):
        self.symbol_table = {}

    def get(self, name, default=None):
        return self.symbol_table.get(name, default)

    def __getitem__(self, name):
        return self.symbol_table[name]

    def __iter__(self):
        return iter(self.symbol_table)

    def symbol(self, name, bp=0):
        try:
            s = self.symbol_table[name]
        except KeyError:

            class S(SymbolBase):
                pass

            s = S
            s.__name__ = "symbol-" + name  # for debugging
            s.name = name
            s.lbp = bp
            self.symbol_table[name] = s
        else:
            s.lbp = max(bp, s.lbp)
        return s

    @multi
    def infix(self, name, bp):
        symbol = self.symbol(name, bp)

        @method(symbol)
        def led(self, left, parser):
            self.first = left
            self.second = parser.expression(bp)
            return self

    @multi
    def infix_r(self, name, bp):
        symbol = self.symbol(name, bp)

        @method(symbol)
        def led(self, left, parser):
            self.first = left
            self.second = parser.expression(bp - 0.1)
            return self

    def ternary(self, name, name2, bp):
        symbol = self.symbol(name, bp)
        symbol2 = self.symbol(name2)

        @method(symbol)
        def led(self, left, parser):
            self.first = left
            self.second = parser.expression(symbol2.lbp)
            parser.advance(symbol2.name)
            self.third = parser.expression(symbol2.lbp + 0.1)
            return self

    @multi
    def prefix(self, name, bp):
        symbol = self.symbol(name, bp)

        @method(symbol)
        def nud(self, parser):
            self.first = parser.expression(bp)
            return self

    @multi
    def postfix(self, name, bp):
        symbol = self.symbol(name, bp)

        @method(symbol)
        def led(self, left, parser):
            self.first = left
            return self

    multi = staticmethod(multi)  # Just for code checker


symbol_table = SymbolTable()


class Lexer:

    _token_pattern = re.compile(
        r"""
        \s*
        (?:
              (
                    [,()\[\]|]
                  | ->
                  | (?<=\s)(?:or)\b
              )  # operator
            | ([a-zA-Z](?:\w|\.)*)  # name
        )
        """,
        re.U | re.S | re.X,
    )

    def __init__(self, symbol_table):
        self.symbol_table = symbol_table

    def tokenize(self, program):
        for name, value in self._tokenize_expr(program):
            symbol = symbol_table.get(value)
            if symbol:
                s = symbol()
            elif name == "(name)":
                symbol = symbol_table[name]
                s = symbol()
                s.value = value
            else:
                raise SyntaxError(
                    "Unknown operator ({}). Possible operators are {!r}".format(
                        value, list(self.symbol_table)
                    )
                )

            yield s

    def _tokenize_expr(self, program):
        if isinstance(program, bytes):
            program = program.decode("utf-8")
        # import pprint; pprint.pprint(self._token_pattern.findall(program))
        for operator, name in self._token_pattern.findall(program):
            if operator:
                yield "(operator)", operator
            elif name:
                yield "(name)", name
            else:
                raise SyntaxError
        yield "(end)", "(end)"


class Parser:

    token = None
    next = None

    def __init__(self, lexer):
        self.lexer = lexer

    def parse(self, program):
        generator = self.lexer.tokenize(program)
        self.next = generator.__next__
        self.token = self.next()
        return self.expression()

    def expression(self, rbp=0):
        t = self.token
        self.token = self.next()
        left = t.nud(self)
        while rbp < self.token.lbp:
            t = self.token
            self.token = self.next()
            left = t.led(left, self)
        return left

    def advance(self, name=None):
        if name and self.token.name != name:
            raise SyntaxError(f"Expected {name!r} but found {self.token.name!r}")
        self.token = self.next()


def method(s):
    assert issubclass(s, SymbolBase)

    def bind(fn):
        setattr(s, fn.__name__, fn)
        return fn

    return bind


symbol, infix, infix_r, prefix, postfix, ternary = (
    symbol_table.symbol,
    symbol_table.infix,
    symbol_table.infix_r,
    symbol_table.prefix,
    symbol_table.postfix,
    symbol_table.ternary,
)

symbol("(", 270)
symbol(")")
symbol("[", 250)  # Parameters
symbol("]")
symbol("->", 230)
infix("|", 170)
infix("or", 170)
symbol(",")

symbol("(name)")
symbol("(end)")


@method(symbol("(name)"))
def nud(self, parser):
    return self


@method(symbol("(name)"))
def evaluate(self, pyobject):
    return utils.resolve_type(self.value, pyobject)


# Parametrized objects
@method(symbol("["))
def led(self, left, parser):
    self.first = left
    self.second = []
    if parser.token.name != "]":
        while 1:
            if parser.token.name == "]":
                break
            self.second.append(parser.expression())
            if parser.token.name != ",":
                break
            parser.advance(",")
    parser.advance("]")
    return self


@method(symbol("["))
def evaluate(self, pyobject):
    return utils.parametrize_type(
        self.first.evaluate(pyobject), *[i.evaluate(pyobject) for i in self.second]
    )


# Anonymous Function Calls
@method(symbol("("))
def nud(self, parser):
    self.second = []
    if parser.token.name != ")":
        while 1:
            self.second.append(parser.expression())
            if parser.token.name != ",":
                break
            parser.advance(",")
    parser.advance(")")
    parser.advance("->")
    self.third = parser.expression(symbol("->").lbp + 0.1)
    return self


# Function Calls
@method(symbol("("))
def led(self, left, parser):
    self.first = left
    self.second = []
    if parser.token.name != ")":
        while 1:
            self.second.append(parser.expression())
            if parser.token.name != ",":
                break
            parser.advance(",")
    parser.advance(")")
    parser.advance("->")
    self.third = parser.expression(symbol("->").lbp + 0.1)
    return self


@method(symbol("("))
def evaluate(self, pyobject):
    # TODO: Implement me
    raise NotImplementedError


@method(symbol("or"))
@method(symbol("|"))
def evaluate(self, pyobject):
    # TODO: Implement me
    raise NotImplementedError


class Compiler:

    parser_factory = Parser
    lexer_factory = Lexer
    symbol_table = symbol_table

    def _make_parser(self):
        return self.parser_factory(self.lexer_factory(self.symbol_table))

    @base_utils.cached(500)
    def __call__(self, program):
        """
        :type program: str
        :rtype: rope.base.oi.type_hinting.evaluate.SymbolBase
        """
        return self._make_parser().parse(program)


compile = Compiler()


class Evaluator:

    compile = compile

    def __call__(self, program, pyobject):
        """Evaluates the program string or AST

        :type program: str or rope.base.oi.type_hinting.evaluate.SymbolBase
        :rtype: rope.base.pyobjects.PyDefinedObject | rope.base.pyobjects.PyObject or None
        """
        ast = self.compile(program) if isinstance(program, str) else program
        return ast.evaluate(pyobject)


evaluate = Evaluator()
