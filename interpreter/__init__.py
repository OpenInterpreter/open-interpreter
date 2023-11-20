from .core.core import Interpreter

_singleton_instance = None


def get_instance():
    global _singleton_instance
    if _singleton_instance is None:
        print("CREATING A NEW INSTANCE")
        _singleton_instance = Interpreter()
    return _singleton_instance


def __getattr__(name):
    return getattr(get_instance(), name)


# ^ This is done so when users `import interpreter`,
# they are basically controlling the singleton instance — e.g. interpreter.chat() will work.

# **This is a controversial thing to do,**
# because perhaps modules ought to behave like modules.

# But I think it saves a step, removes friction, and looks good.

#     ____                      ____      __                            __
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/
#      /_/                                         /_/
