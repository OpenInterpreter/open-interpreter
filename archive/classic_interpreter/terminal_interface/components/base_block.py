from rich.console import Console
from rich.live import Live


class BaseBlock:
    """
    a visual "block" on the terminal.
    """

    def __init__(self):
        self.live = Live(
            auto_refresh=False, console=Console(), vertical_overflow="visible"
        )
        self.live.start()

    def update_from_message(self, message):
        raise NotImplementedError("Subclasses must implement this method")

    def end(self):
        self.refresh(cursor=False)
        self.live.stop()

    def refresh(self, cursor=True):
        raise NotImplementedError("Subclasses must implement this method")
