class BaseLanguage:
    def __init__(self):
        pass

    def run(self, code):
        """
        Generator that yields a dict in LMC format:
        {"type": "console", "format": "output", "content": "a printed statement"}
        {"type": "console", "format": "active_line", "content": "1"}
        {"type": "image", "format": "base64", "content": "{base64}"}
        """
        pass

    def stop(self):
        """
        Halts code execution, but does not terminate state.
        """
        pass

    def terminate(self):
        pass
