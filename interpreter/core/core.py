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
from .computer.computer import Computer
from .generate_system_message import generate_system_message
from .llm.setup_llm import setup_llm
from .respond import respond
from .utils.truncate_output import truncate_output


class Interpreter:
    def start_terminal_interface(self):
        start_terminal_interface(self)

    def __init__(self):
        # State
        self.messages = []

        self.config_file = user_config_path

        # Settings
        self.local = False
        self.auto_run = False
        self.debug_mode = False
        self.max_output = 2000
        self.safe_mode = "off"
        self.disable_procedures = False
        self.force_task_completion = False

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
        self.api_version = None
        self.max_budget = None
        self._llm = None
        self.function_calling_llm = None
        self.vision = False  # LLM supports vision

        # Computer settings
        self.computer = Computer()
        # Permitted languages, all lowercase
        self.languages = [i.name.lower() for i in self.computer.terminal.languages]
        # (Not implemented) Permitted functions
        # self.functions = [globals]
        # OS control mode
        self.os = False

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

        initial_message_count = len(self.messages)

        # If stream=False, *pull* from the stream.
        for _ in self._streaming_chat(message=message, display=display):
            pass

        # Return new messages
        return self.messages[initial_message_count:]

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
                self.messages.append(
                    {"role": "user", "type": "message", "content": message}
                )
            # List (this is like the OpenAI API)
            elif isinstance(message, list):
                self.messages = message

            # DISABLED because I think we should just not transmit images to non-multimodal models?
            # REENABLE this when multimodal becomes more common:

            # Make sure we're using a model that can handle this
            # if not self.vision:
            #     for message in self.messages:
            #         if message["type"] == "image":
            #             raise Exception(
            #                 "Use a multimodal model and set `interpreter.vision` to True to handle image messages."
            #             )

            # This is where it all happens!
            yield from self._respond_and_store()

            # Save conversation if we've turned conversation_history on
            if self.conversation_history:
                # If it's the first message, set the conversation name
                if not self.conversation_filename:
                    first_few_words = "_".join(
                        self.messages[0]["content"][:25].split(" ")[:-1]
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

    def _respond_and_store(self):
        """
        Pulls from the respond stream, adding delimiters. Some things, like active_line, console, confirmation... these act specially.
        Also assembles new messages and adds them to `self.messages`.
        """

        # Utility function
        def is_active_line_chunk(chunk):
            return "format" in chunk and chunk["format"] == "active_line"

        last_flag_base = None

        for chunk in respond(self):
            if chunk["content"] == "":
                continue

            # Handle the special "confirmation" chunk, which neither triggers a flag or creates a message
            if chunk["type"] == "confirmation":
                # Emit a end flag for the last message type, and reset last_flag_base
                if last_flag_base:
                    yield {**last_flag_base, "end": True}
                    last_flag_base = None
                yield chunk
                # We want to append this now, so even if content is never filled, we know that the execution didn't produce output.
                self.messages.append(
                    {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": "",
                    }
                )
                continue

            # Check if the chunk's role, type, and format (if present) match the last_flag_base
            if (
                last_flag_base
                and "role" in chunk
                and "type" in chunk
                and last_flag_base["role"] == chunk["role"]
                and last_flag_base["type"] == chunk["type"]
                and (
                    "format" not in last_flag_base
                    or (
                        "format" in chunk
                        and chunk["format"] == last_flag_base["format"]
                    )
                )
            ):
                # If they match, append the chunk's content to the current message's content
                # (Except active_line, which shouldn't be stored)
                if not is_active_line_chunk(chunk):
                    self.messages[-1]["content"] += chunk["content"]
            else:
                # If they don't match, yield a end message for the last message type and a start message for the new one
                if last_flag_base:
                    yield {**last_flag_base, "end": True}

                last_flag_base = {"role": chunk["role"], "type": chunk["type"]}

                # Don't add format to type: "console" flags, to accomodate active_line AND output formats
                if "format" in chunk and chunk["type"] != "console":
                    last_flag_base["format"] = chunk["format"]

                yield {**last_flag_base, "start": True}

                # Add the chunk as a new message
                if not is_active_line_chunk(chunk):
                    self.messages.append(chunk)

            # Yield the chunk itself
            yield chunk

            # Truncate output if it's console output
            if chunk["type"] == "console" and chunk["format"] == "output":
                self.messages[-1]["content"] = truncate_output(
                    self.messages[-1]["content"], self.max_output
                )

        # Yield a final end flag
        if last_flag_base:
            yield {**last_flag_base, "end": True}

    def reset(self):
        self.computer.terminate()  # Terminates all languages

        # Reset the function below, in case the user set it
        self.generate_system_message = lambda: generate_system_message(self)

        self.__init__()

    # These functions are worth exposing to developers
    # I wish we could just dynamically expose all of our functions to devs...
    def generate_system_message(self):
        return generate_system_message(self)
