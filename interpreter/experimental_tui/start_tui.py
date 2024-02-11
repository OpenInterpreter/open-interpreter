from typing import Type
from textual.app import App, ComposeResult
from textual import events
from textual.driver import Driver
from textual.reactive import reactive
from textual.widget import AwaitMount
from textual.widgets import Header, Footer, TextArea, Placeholder, Static, Button, ListView, ListItem, Label
from textual.containers import Container, Horizontal, VerticalScroll
from pathlib import Path
import json

import re
import appdirs

def get_chat_conversations():
    # Use appdirs to get the user configuration directory for "conversations"
    path = Path(appdirs.user_config_dir("Open Interpreter") + "/conversations")

    # Initialize an empty dictionary
    conversations = {}

    # Ensure the path exists and is a directory
    if not path.is_dir():
        print(f"The path {path} is not a directory.")
        return conversations

    # Regular expression to match the initial part of the filename before the date
    pattern = re.compile(r"^(.*?)__")

    # Iterate over each file in the directory
    for file_path in path.iterdir():
        # Match only files
        if file_path.is_file():
            # Extract the filename as a string
            filename = file_path.name
            # Check if the file matches the expected pattern
            match = pattern.match(filename)
            if match:
                # Extract the part of the filename before the date
                extracted_name = match.group(1)
                # Replace underscores with spaces to form the key
                key = extracted_name.replace('_', ' ')
                # Use the file_path as the value
                conversations[key] = str(file_path)

    return conversations

class Open_Interpreter_App(App):
    """A Textual app for a chat interface."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]
    CSS_PATH = "style.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal(id="main"):
            with ListView(id="sidebar"):
                for conversation in get_chat_conversations():
                    yield ListItem(Label(conversation))

            with Container():
                with VerticalScroll():
                    for message in range(10):
                        yield Placeholder()
    
    def load_messages(self, event: events.Event) -> None:
        """Load messages from a .diffs file."""
        # Get the selected ListItem
        item = event.item
        # Extract the conversation name from the Label
        conversation_name = item.label.text
        # Find the corresponding .diffs file
        path = Path(appdirs.user_config_dir("Open Interpreter") + "/conversations")
        for file_path in path.glob(f"*{conversation_name}__*.json"):
            if file_path.is_file():
                with open(file_path, "r") as f:
                    messages = json.load(f)
                # Do something with the messages here
                print("Loaded messages:", messages)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark


# Additional methods for handling chat interactions can be added here

def main():
    app = Open_Interpreter_App()
    app.run()

if __name__ == "__main__":
    main()