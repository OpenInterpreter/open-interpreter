from rich.spinner import Spinner


class OISpinner(Spinner):
    def __init__(self):
        super().__init__(name="dots", text="Generating responses...")
        self.frames = ["●", "•"]
