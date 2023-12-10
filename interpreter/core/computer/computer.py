from .terminal.terminal import Terminal

try:
    from .display.display import Display
    from .keyboard.keyboard import Keyboard
    from .mouse.mouse import Mouse
except ImportError or ModuleNotFoundError:
    raise
    pass


class Computer:
    def __init__(self):
        self.terminal = Terminal()
        try:
            self.mouse = Mouse(
                self
            )  # Mouse will use the computer's display, so we give it a reference to ourselves
            self.keyboard = Keyboard()
            self.display = Display()
        except:
            raise
            pass

    def run(self, *args, **kwargs):
        """
        Shortcut for computer.terminal.run
        """
        return self.terminal.run(*args, **kwargs)

    def stop(self):
        """
        Shortcut for computer.terminal.stop
        """
        return self.terminal.stop()

    def terminate(self):
        """
        Shortcut for computer.terminal.terminate
        """
        return self.terminal.terminate()

    def screenshot(self, *args, **kwargs):
        """
        Shortcut for computer.display.screenshot
        """
        return self.display.screenshot(*args, **kwargs)
