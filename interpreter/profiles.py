import json
import os
import platform
import sys
from datetime import datetime


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

    DEFAULT_PROFILE_FOLDER = "~/.openinterpreter"
    DEFAULT_PROFILE_PATH = os.path.join(DEFAULT_PROFILE_FOLDER, "default_profile.py")

    def __init__(self):
        # Default values if no profile exists
        # Model configuration
        self.model = "claude-3-5-sonnet-20241022"  # The LLM model to use
        self.provider = (
            None  # The model provider (e.g. anthropic, openai) None will auto-detect
        )
        self.temperature = 0  # Sampling temperature for model outputs (0-1)
        self.max_tokens = None  # Maximum tokens in a message

        # API configuration
        self.api_base = None  # Custom API endpoint URL
        self.api_key = None  # API authentication key
        self.api_version = None  # API version to use

        # Runtime limits
        self.max_turns = -1  # Maximum conversation turns (-1 for unlimited)

        # Conversation state
        self.messages = []  # List of conversation messages
        self.system_message = None  # System message override
        self.instructions = ""  # Additional model instructions
        self.input = None  # Pre-filled first user message

        # Available tools and settings
        self.tools = ["interpreter", "editor"]  # Enabled tool modules
        self.auto_run = False  # Whether to auto-run tools without confirmation
        self.tool_calling = True  # Whether to allow tool/function calling
        self.interactive = sys.stdin.isatty()  # Whether to prompt for input

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
        if not path.endswith(".py"):
            path += ".py"
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.path.exists(path):
            print(f"\n\033[38;5;240mThis will overwrite:\033[0m {path}")
            confirmation = input("\nAre you sure? (y/n): ").lower().strip()
            if confirmation != "y":
                print("Save cancelled")
                return

        # Get default values to compare against
        default_profile = Profile()

        with open(path, "w") as f:
            f.write("from interpreter import interpreter\n\n")

            # Compare each attribute with default and write if different
            for key, value in self.to_dict().items():
                if key == "messages":
                    continue

                if value != getattr(default_profile, key):
                    if isinstance(value, str):
                        f.write(f'interpreter.{key} = """{value}"""\n')
                    elif isinstance(value, list):
                        f.write(f"interpreter.{key} = {repr(value)}\n")
                    else:
                        f.write(f"interpreter.{key} = {repr(value)}\n")

        print(f"Profile saved to {path}")

    def load(self, path):
        """Load settings from a profile file if it exists"""
        path = os.path.expanduser(path)
        if not path.endswith(".py"):
            path += ".py"

        if not os.path.exists(path):
            # If file doesn't exist, if it's the default, that's fine
            if os.path.abspath(os.path.expanduser(path)) == os.path.abspath(
                os.path.expanduser(self.DEFAULT_PROFILE_PATH)
            ):
                return
            raise FileNotFoundError(f"Profile file not found at {path}")

        # Create a temporary namespace to execute the profile in
        namespace = {}
        try:
            with open(path) as f:
                # Read the profile content
                content = f.read()

                # Replace the import with a dummy class definition
                # This avoids loading the full interpreter module which is resource intensive
                content = content.replace(
                    "from interpreter import interpreter",
                    "class Interpreter:\n    pass\ninterpreter = Interpreter()",
                )

                # Execute the modified profile content
                exec(content, namespace)

            # Extract settings from the interpreter object in the namespace
            if "interpreter" in namespace:
                for key in self.to_dict().keys():
                    if hasattr(namespace["interpreter"], key):
                        setattr(self, key, getattr(namespace["interpreter"], key))
            else:
                print("Failed to load profile, no interpreter object found")
        except Exception as e:
            raise ValueError(f"Failed to load profile at {path}. Error: {str(e)}")

    @classmethod
    def from_file(cls, path):
        """Create a new profile instance from a file"""
        profile = cls()
        profile.load(path)
        return profile
