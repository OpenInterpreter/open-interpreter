from rich.console import Console
from rich.live import Live

from .spinner import OISpinner


class BaseBlock:
    """
    a visual "block" on the terminal.
    """

    def __init__(self, no_live_response: bool = False):
        self.live = Live(
            auto_refresh=False, console=Console(), vertical_overflow="visible"
        )
        self.live.start()
        self.spinner = OISpinner()
        self.no_live_response = no_live_response

    def update_from_message(self, message):
        raise NotImplementedError("Subclasses must implement this method")

    def end(self):
        self.refresh(cursor=False, end=True)
        self.live.stop()

    def refresh(self, cursor=True, end=False):
        raise NotImplementedError("Subclasses must implement this method")
