"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""
from ..cli.cli import cli
from ..utils.get_config import get_config
from .respond import respond
from ..llm.setup_llm import setup_llm
from ..display.interactive_display import interactive_display

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

        # LLM settings
        self.model = ""
        self.temperature = 0
        self.system_message = ""
        self.context_window = None
        self.max_tokens = None
        self._llm = None

        # Load config defaults
        config = get_config()
        self.__dict__.update(config)

    def chat(self, message=None, display=True, stream=False):
        if stream:
            return self._streaming_chat(message=message, display=display)
        
        # If stream=False, *pull* from the stream.
        for chunk in self._streaming_chat(message=message, display=display):
            pass
        
        return self.messages
    
    def _streaming_chat(self, message=None, display=True):

        # We need an LLM
        if not self._llm:
            self._llm = setup_llm(self)

        # Display mode actually runs interpreter.chat(display=False, stream=True) from within a display.
        # wraps the vanilla .chat(display=False) generator in a display.
        # Quite different from the plain generator stuff. So redirect to that
        if display:
            yield from interactive_display(self, message)
            return
        
        # One-off message
        if message:
            self.messages.append({"role": "user", "message": message})
            yield from self._respond()
            return
        
        raise Exception("`interpreter.chat()` requires a display. Set `display=True`.")

    def _respond(self):
        yield from respond(self)

    def reset(self):
        self.messages = []
        for code_interpreter in self._code_interpreters:
            code_interpreter.terminate()
        self._code_interpreters = {}