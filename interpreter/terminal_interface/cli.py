# cli.py
from ..core.core import OpenInterpreter
from .start_terminal_interface import start_terminal_interface


def main():
    interpreter = OpenInterpreter()
    try:
        start_terminal_interface(interpreter)
    except KeyboardInterrupt:
        print("Exited.")
