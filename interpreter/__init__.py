import sys

if sys.version_info < (3, 10) or sys.version_info >= (3, 12):
    print(
        "\nYou are running Open Interpreter on an unsupported version of Python, so you may encounter unexpected errors. Please install Python 3.10 or 3.11 at https://www.python.org/downloads/\n"
    )

from .core.core import OpenInterpreter

interpreter = OpenInterpreter()

#     ____                      ____      __                            __
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/
#      /_/                                         /_/
