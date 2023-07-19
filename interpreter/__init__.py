from .interpreter import Interpreter
import sys

sys.modules["interpreter"] = Interpreter()