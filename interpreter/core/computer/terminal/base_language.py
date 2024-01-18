class BaseLanguage:
    """

    Attributes

    name = "baselanguage" # Name as it is seen by the LLM
    file_extension = "sh" # (OPTIONAL) File extension, used for safe_mode code scanning
    aliases = ["bash", "sh", "zsh"] # (OPTIONAL) Aliases that will also point to this language if the LLM runs them

    Methods

    run (Generator that yields a dictionary in LMC format)
    stop (Halts code execution, but does not terminate state)
    terminate (Terminates state)
    """

    def run(self, code):
        """
        Generator that yields a dictionary in LMC format:
        {"type": "console", "format": "output", "content": "a printed statement"}
        {"type": "console", "format": "active_line", "content": "1"}
        {"type": "image", "format": "base64", "content": "{base64}"}
        """
        return {"type": "console", "format": "output", "content": code}

    def stop(self):
        """
        Halts code execution, but does not terminate state.
        """
        pass

    def terminate(self):
        """
        Terminates state.
        """
        pass
