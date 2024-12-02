import asyncio
import sys
import threading
import time


class SimpleSpinner:
    """A simple text-based spinner for command line interfaces."""

    def __init__(self, text=""):
        self.spinner_cycle = ["   ", ".  ", ".. ", "..."]
        self.text = text
        self.keep_running = False
        self.spinner_thread = None

    async def _spin(self):
        while self.keep_running:
            for frame in self.spinner_cycle:
                if not self.keep_running:
                    break
                # Clear the line and write the new frame
                sys.stdout.write("\r" + self.text + frame)
                sys.stdout.flush()
                try:
                    await asyncio.sleep(0.2)  # Async sleep for better cancellation
                except asyncio.CancelledError:
                    break

    def start(self):
        """Start the spinner animation in a separate thread."""
        if not self.spinner_thread:
            self.keep_running = True
            loop = asyncio.new_event_loop()
            self.spinner_thread = threading.Thread(
                target=lambda: loop.run_until_complete(self._spin())
            )
            self.spinner_thread.daemon = True
            self.spinner_thread.start()

    def stop(self):
        """Stop the spinner animation and clear the line."""
        self.keep_running = False
        if self.spinner_thread:
            self.spinner_thread.join()
            self.spinner_thread = None
        # Clear the spinner from the line
        sys.stdout.write("\r" + " " * (len(self.text) + 3) + "\r")
        sys.stdout.flush()
