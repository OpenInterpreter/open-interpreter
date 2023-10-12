"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""
from interpreter.utils import display_markdown_message
from ..cli.cli import cli
from ..utils.get_config import get_config, user_config_path
from ..utils.local_storage_path import get_storage_path
from .respond import respond
from ..llm.setup_llm import setup_llm
from ..terminal_interface.terminal_interface import terminal_interface
from ..terminal_interface.validate_llm_settings import validate_llm_settings
from .generate_system_message import generate_system_message
import appdirs
import os
from datetime import datetime
from ..rag.get_relevant_procedures_string import get_relevant_procedures_string
import json
from ..utils.check_for_update import check_for_update
from ..utils.display_markdown_message import display_markdown_message
from ..utils.embed import embed_function


class Interpreter:
    def cli(self):
        cli(self)

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

        # Conversation history
        self.conversation_history = True
        self.conversation_filename = None
        self.conversation_history_path = get_storage_path("conversations")

        # LLM settings
        self.model = ""
        self.temperature = 0
        self.system_message = ""
        self.context_window = None
        self.max_tokens = None
        self.api_base = None
        self.api_key = None
        self.max_budget = None
        self._llm = None
        self.gguf_quality = None

        # Procedures / RAG
        self.procedures = None
        self._procedures_db = {}
        self.download_open_procedures = True
        self.embed_function = embed_function
        # Number of procedures to add to the system message
        self.num_procedures = 2

        # Load config defaults
        self.extend_config(self.config_file)

        # Check for update
        if not self.local:
            # This should actually be pushed into the utility
            if check_for_update():
                display_markdown_message("> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---")

    def extend_config(self, config_path):
        if self.debug_mode:
            print(f'Extending configuration from `{config_path}`')

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

        # If we have a display,
        # we can validate our LLM settings w/ the user first
        if display:
            validate_llm_settings(self)

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
                message = "No entry from user - please suggest something to enter"
            self.messages.append({"role": "user", "message": message})
            yield from self._respond()

            # Save conversation if we've turned conversation_history on
            if self.conversation_history:

                # If it's the first message, set the conversation name
                if not self.conversation_filename:

                    first_few_words = "_".join(self.messages[0]["message"][:25].split(" ")[:-1])
                    for char in "<>:\"/\\|?*!": # Invalid characters for filenames
                        first_few_words = first_few_words.replace(char, "")

                    date = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
                    self.conversation_filename = "__".join([first_few_words, date]) + ".json"

                # Check if the directory exists, if not, create it
                if not os.path.exists(self.conversation_history_path):
                    os.makedirs(self.conversation_history_path)
                # Write or overwrite the file
                with open(os.path.join(self.conversation_history_path, self.conversation_filename), 'w') as f:
                    json.dump(self.messages, f)
                
            return
        raise Exception("`interpreter.chat()` requires a display. Set `display=True` or pass a message into `interpreter.chat(message)`.")

    def _respond(self):
        yield from respond(self)
            
    def reset(self):
        for code_interpreter in self._code_interpreters.values():
            code_interpreter.terminate()
        self._code_interpreters = {}

        # Reset the two functions below, in case the user set them
        self.generate_system_message = lambda: generate_system_message(self)
        self.get_relevant_procedures_string = lambda: get_relevant_procedures_string(self)

        self.__init__()


    # These functions are worth exposing to developers
    # I wish we could just dynamically expose all of our functions to devs...
    def generate_system_message(self):
        return generate_system_message(self)
    def get_relevant_procedures_string(self):
        return get_relevant_procedures_string(self)
