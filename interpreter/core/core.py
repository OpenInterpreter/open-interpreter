"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""

import json
import os
from datetime import datetime

from ..terminal_interface.start_terminal_interface import start_terminal_interface
from ..terminal_interface.terminal_interface import terminal_interface
from ..terminal_interface.utils.get_config import get_config, user_config_path
from ..terminal_interface.utils.local_storage_path import get_storage_path
from .generate_system_message import generate_system_message
from .llm.setup_llm import setup_llm
from .respond import respond


class Interpreter:
    def start_terminal_interface(self):
        start_terminal_interface(self)

    def __init__(self):
        # State
        self.messages = []
        self._code_interpreters = {}

        self.config_file = user_config_path

        # Settings
        self.local = False
        self.auto_run = False
        self.debug_mode = False
        self.max_output = 2000
        self.safe_mode = "off"
        self.disable_procedures = False
        # In the future, we'll use this to start with all languages
        # self.languages = [i.name for i in self.computer.interfaces]

        # Conversation history
        self.conversation_history = True
        self.conversation_filename = None
        self.conversation_history_path = get_storage_path("conversations")

        # LLM settings
        self.model = ""
        self.temperature = None
        self.system_message = ""
        self.context_window = None
        self.max_tokens = None
        self.api_base = None
        self.api_key = None
        self.max_budget = None
        self._llm = None
        self.function_calling_llm = None
        self.vision = False  # LLM supports vision

        # Load config defaults
        self.extend_config(self.config_file)

        # Expose class so people can make new instances
        self.Interpreter = Interpreter

    def extend_config(self, config_path):
        if self.debug_mode:
            print(f"Extending configuration from `{config_path}`")

        config = get_config(config_path)
        self.__dict__.update(config)

    def chat(self, message=None, display=True, stream=False):
        if stream:
            return self._streaming_chat(message=message, display=display)

        # If stream=False, *pull* from the stream.
        for _ in self._streaming_chat(message=message, display=display):
            pass

        return self.messages

    def _streaming_chat(self, message=None, display=True):
        # Setup the LLM
        if not self._llm:
            self._llm = setup_llm(self)

        # Sometimes a little more code -> a much better experience!
        # Display mode actually runs interpreter.chat(display=False, stream=True) from within the terminal_interface.
        # wraps the vanilla .chat(display=False) generator in a display.
        # Quite different from the plain generator stuff. So redirect to that
        if display:
            yield from terminal_interface(self, message)
            return

        # One-off message
        if message or message == "":
            if message == "":
                message = "No entry from user - please suggest something to enter."

            ## We support multiple formats for the incoming message:
            # Dict (these are passed directly in)
            if isinstance(message, dict):
                if "role" not in message:
                    message["role"] = "user"
                self.messages.append(message)
            # String (we construct a user message dict)
            elif isinstance(message, str):
                self.messages.append({"role": "user", "message": message})
            # List (this is like the OpenAI API)
            elif isinstance(message, list):
                self.messages = message

            yield from self._respond()

            # Save conversation if we've turned conversation_history on
            if self.conversation_history:
                # If it's the first message, set the conversation name
                if not self.conversation_filename:
                    first_few_words = "_".join(
                        self.messages[0]["message"][:25].split(" ")[:-1]
                    )
                    for char in '<>:"/\\|?*!':  # Invalid characters for filenames
                        first_few_words = first_few_words.replace(char, "")

                    date = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
                    self.conversation_filename = (
                        "__".join([first_few_words, date]) + ".json"
                    )

                # Check if the directory exists, if not, create it
                if not os.path.exists(self.conversation_history_path):
                    os.makedirs(self.conversation_history_path)
                # Write or overwrite the file
                with open(
                    os.path.join(
                        self.conversation_history_path, self.conversation_filename
                    ),
                    "w",
                ) as f:
                    json.dump(self.messages, f)
            return

        raise Exception(
            "`interpreter.chat()` requires a display. Set `display=True` or pass a message into `interpreter.chat(message)`."
        )

    def _respond(self):
        yield from respond(self)

    def reset(self):
        for code_interpreter in self._code_interpreters.values():
            code_interpreter.terminate()
        self._code_interpreters = {}

        # Reset the function below, in case the user set it
        self.generate_system_message = lambda: generate_system_message(self)

        self.__init__()

    # These functions are worth exposing to developers
    # I wish we could just dynamically expose all of our functions to devs...
    def generate_system_message(self):
        return generate_system_message(self)
