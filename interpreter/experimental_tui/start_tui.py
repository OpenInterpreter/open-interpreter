from interpreter import interpreter
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Static, TextArea

TEXT = """\
Docking a widget removes it from the layout and fixes its position, aligned to either the top, right, bottom, or left edges of a container.

Docked widgets will not scroll out of view, making them ideal for sticky headers, footers, and sidebars.

"""

class Open_Interpreter_App(App):
    CSS_PATH = "style.tcss"

    def compose(self) -> ComposeResult:
        with Container(id="sidebar"):
            yield Static("USERNAME")
            with VerticalScroll(id="chat-history"):
                pass
        
        with Container(id="chat"):
            with VerticalScroll(id="chat-scroll"):
                pass #yield messages
            yield TextArea("test", language="python")

if __name__ == "__main__":
    oia = Open_Interpreter_App()
    oia.run()