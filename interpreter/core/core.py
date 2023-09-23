"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""
from interpreter.utils import display_markdown_message
from ..cli.cli import cli
from ..utils.get_config import get_config
from .respond import respond
from ..llm.setup_llm import setup_llm
from ..terminal_interface.terminal_interface import terminal_interface
from ..terminal_interface.validate_llm_settings import validate_llm_settings
import appdirs
import os
import json
from datetime import datetime
from ..utils.check_for_update import check_for_update
from ..utils.display_markdown_message import display_markdown_message

class Interpreter:
    def cli(self):
        cli(self)

    def __init__(self):
        # State
        self.messages = []
        self._code_interpreters = {}

        # Settings
        self.local = False
        self.auto_run = False
        self.debug_mode = False
        self.max_output = 2000

        # Conversation history
        self.conversation_history = True
        self.conversation_name = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
        self.conversation_history_path = os.path.join(appdirs.user_data_dir("Open Interpreter"), "conversations")

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

        # Load config defaults
        config = get_config()
        self.__dict__.update(config)

        # Check for update
        if not self.local:
            # This should actually be pushed into the utility
            if check_for_update():
                display_markdown_message("> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---")

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
        if message:
            self.messages.append({"role": "user", "message": message})
            
            yield from self._respond()

            # Save conversation
            if self.conversation_history:
                # Check if the directory exists, if not, create it
                if not os.path.exists(self.conversation_history_path):
                    os.makedirs(self.conversation_history_path)
                # Write or overwrite the file
                with open(os.path.join(self.conversation_history_path, self.conversation_name + '.json'), 'w') as f:
                    json.dump(self.messages, f)
                
            return
        
        raise Exception("`interpreter.chat()` requires a display. Set `display=True` or pass a message into `interpreter.chat(message)`.")

    def _respond(self):
        yield from respond(self)
            
    def reset(self):
        self.messages = []
        self.conversation_name = datetime.now().strftime("%B %d, %Y")
        for code_interpreter in self._code_interpreters.values():
            code_interpreter.terminate()
        self._code_interpreters = {}