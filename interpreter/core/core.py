"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""
from ..cli.cli import cli
from ..utils.get_config import get_config
from .respond import respond
from ..llm.setup_llm import setup_llm
from ..display.display import display as display_

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

        # sometimes to get a simple user experience
        # we need the code to be a little more complex

        if stream == False:
            # Pull from the generator. This is so interpreter.chat() works magically
            for chunk in self.chat(display=display, stream=True):
                pass
            return
        
        # Display mode actually runs interpreter.chat(display=False) from within a display.
        # wraps the vanilla .chat(display=False) generator in a display.
        # Quite different from the plain generator stuff. So redirect to that
        if display:
            # We only imported this as `display_` 
            # so we could reserve `display` for this parameter name
            yield from display_(self, message)
            return
        
        # We need an LLM
        if not self._llm:
            self._llm = setup_llm(self)
        
        # One-off message
        if message:
            self.messages.append({"role": "user", "content": message})
            yield from self._respond()
            return

        # Chat loop
        while True:
            message = input("> ").strip()
            self.messages.append({"role": "user", "content": message})
            yield from self._respond()

    def _respond(self):
        yield from respond(self)

    def reset(self):
        self.messages = []
        for code_interpreter in self._code_interpreters:
            code_interpreter.terminate()
        self._code_interpreters = {}