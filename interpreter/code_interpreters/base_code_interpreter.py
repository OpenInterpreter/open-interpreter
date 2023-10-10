from typing import Optional


class BaseCodeInterpreter:
    """
    .run is a generator that yields a dict with attributes: active_line, output
    """
    def __init__(self, sandbox: bool, e2b_api_key: Optional[str]):
        pass

    def run(self, code):
        pass

    def terminate(self):
        pass