"""
This file defines the Interpreter class.
It's the main file. `import interpreter` will import an instance of this class.
"""
from ..cli.cli import cli
from get_config import get_config
import pkg_resources

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

    def chat(self, message=None, display=True):
        # We need an LLM.
        if not self._llm:
            self._llm = setup_llm(self)

        # sometimes to get a simple user experience
        # we need the code to be a little more complex

        # Display mode actually runs interpreter.chat(display=False) from within a display.
        # wraps the vanilla .chat(display=False) generator in a display.
        # Quite different from the plain generator stuff. So redirect to that
        if display:
            yield from chat_with_display(self, message)
            return
        
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
        messages = tt.trim(self.messages)
        for chunk in self.llm.chat(messages):
            pass

    def reset(self):
        self.messages = []
        # I think we need to teardown the code_interpreters actually.
        self.code_interpreters = {}