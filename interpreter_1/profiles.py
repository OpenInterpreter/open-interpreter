import json
import os
import platform
from datetime import datetime

# System prompt with dynamic values
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are an AI assistant with access to a machine running on {"Mac OS" if platform.system() == "Darwin" else platform.system()} with internet access.
* When using your computer function calls, they take a while to run and send back to you. Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %d, %Y')}.
* The user's cwd is {os.getcwd()} and username is {os.getlogin()}.
</SYSTEM_CAPABILITY>"""

# Update system prompt for Mac OS
if platform.system() == "Darwin":
    SYSTEM_PROMPT += """
<IMPORTANT>
* Open applications using Spotlight by using the computer tool to simulate pressing Command+Space, typing the application name, and pressing Enter.
</IMPORTANT>"""


class Profile:
    """
    Profile management for Open Interpreter.

    Handles loading and saving settings from profile files,
    with defaults that fall back to ~/.openinterpreter if no profile is specified.

    Examples
    --------
    >>> from interpreter import Profile

    # Load defaults (and ~/.openinterpreter if it exists)
    profile = Profile()

    # Load from specific profile
    profile = Profile.from_file("~/custom_profile.json")

    # Save current settings
    profile.save("~/my_settings.json")
    """

    DEFAULT_PROFILE_PATH = "~/.openinterpreter"

    def __init__(self):
        # Default values if no profile exists
        # Model configuration
        self.model = "claude-3-5-sonnet-20241022"  # The LLM model to use
        self.provider = (
            None  # The model provider (e.g. anthropic, openai) None will auto-detect
        )
        self.temperature = 0  # Sampling temperature for model outputs (0-1)

        # API configuration
        self.api_base = None  # Custom API endpoint URL
        self.api_key = None  # API authentication key
        self.api_version = None  # API version to use

        # Runtime limits
        self.max_turns = -1  # Maximum conversation turns (-1 for unlimited)

        # Conversation state
        self.messages = []  # List of conversation messages
        self.system_message = SYSTEM_PROMPT  # System prompt override
        self.instructions = ""  # Additional model instructions
        self.input = None  # Input message override

        # Available tools and settings
        self.tools = ["interpreter", "editor"]  # Enabled tool modules
        self.auto_run = False  # Whether to auto-run tools without confirmation
        self.tool_calling = True  # Whether to allow tool/function calling

        # Server settings
        self.serve = False  # Whether to start the server

        # Allowed paths and commands
        self.allowed_paths = []  # List of allowed paths
        self.allowed_commands = []  # List of allowed commands

        # Debug settings
        self.debug = False  # Whether to enable debug mode

        # Set default path but don't load from it
        self.profile_path = self.DEFAULT_PROFILE_PATH

    def to_dict(self):
        """Convert settings to dictionary for serialization"""
        return {
            key: value
            for key, value in vars(self).items()
            if not key.startswith("_")  # Skip private attributes
        }

    def from_dict(self, data):
        """Update settings from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def save(self, path=None):
        """Save current settings to a profile file"""
        path = os.path.expanduser(path or self.profile_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.path.exists(path):
            print(f"\n\033[38;5;240mThis will overwrite:\033[0m {path}")
            confirmation = input("\nAre you sure? (y/n): ").lower().strip()
            if confirmation != "y":
                print("Save cancelled")
                return

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self, path):
        """Load settings from a profile file if it exists"""
        path = os.path.expanduser(path)

        try:
            with open(path) as f:
                data = json.load(f)
                self.from_dict(data)
        except FileNotFoundError:
            # If file doesn't exist, if it's the default, that's fine
            if os.path.abspath(os.path.expanduser(path)) == os.path.abspath(
                os.path.expanduser(self.DEFAULT_PROFILE_PATH)
            ):
                pass
            else:
                raise FileNotFoundError(f"Profile file not found at {path}")
        except json.JSONDecodeError as e:
            # If JSON is invalid, raise descriptive error
            raise json.JSONDecodeError(
                f"Failed to parse profile at {path}. Error: {str(e)}", e.doc, e.pos
            )

    @classmethod
    def from_file(cls, path):
        """Create a new profile instance from a file"""
        profile = cls()
        profile.load(path)
        return profile
