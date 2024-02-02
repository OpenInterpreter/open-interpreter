from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Header, Footer, TextArea, Placeholder, Static
from textual.containers import Container, Horizontal, VerticalScroll

class Message_bubble(Static):
    position = reactive()


class Open_Interpreter_App(App):
    """A Textual app for a chat interface."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            with VerticalScroll():
                yield Placeholder()
            with Container():
                yield Static()
                with VerticalScroll():
                    for message in range(10):
                        yield Placeholder()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    # Additional methods for handling chat interactions can be added here

if __name__ == "__main__":
    app = Open_Interpreter_App()
    app.run()
