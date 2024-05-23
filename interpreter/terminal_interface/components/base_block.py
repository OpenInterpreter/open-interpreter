from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner


class BaseBlock:
    """
    a visual "block" on the terminal.
    """

    def __init__(self):
        self.live = Live(
            auto_refresh=False, console=Console(), vertical_overflow="visible"
        )
        self.live.start()
        self.spinner = Spinner(name="dots", text="Generating responses...")

    def update_from_message(self, message):
        raise NotImplementedError("Subclasses must implement this method")

    def end(self):
        self.refresh(cursor=False, end=True)
        self.live.stop()

    def refresh(self, cursor=True, end=False):
        raise NotImplementedError("Subclasses must implement this method")
