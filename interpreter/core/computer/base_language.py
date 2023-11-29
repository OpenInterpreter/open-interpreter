class BaseLanguage:
    def __init__(self):
        pass

    def run(self, code):
        """
        Generator that yields a dict with attributes: active_line, output
        """
        pass

    def stop(self):
        """
        Halts code execution, but does not terminate state.
        """
        pass

    def terminate(self):
        pass
