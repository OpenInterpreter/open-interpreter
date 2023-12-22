from .terminal.terminal import Terminal

try:
    from .clipboard.clipboard import Clipboard
    from .display.display import Display
    from .keyboard.keyboard import Keyboard
    from .mouse.mouse import Mouse
    from .os.os import Os
except:
    pass


class Computer:
    def __init__(self):
        self.terminal = Terminal()

        self.offline = False  # Soon, inherit this, and many other settings on import
        self.debug_mode = False

        # OS mode
        try:
            self.mouse = Mouse(
                self
            )  # Mouse will use the computer's display, so we give it a reference to ourselves
            self.keyboard = Keyboard()
            self.display = Display(self)
            self.clipboard = Clipboard()
            self.os = Os(self)
        except:
            pass

    # Shortcut for computer.terminal.languages
    @property
    def languages(self):
        return self.terminal.languages

    @languages.setter
    def languages(self, value):
        self.terminal.languages = value

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
