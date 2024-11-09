import asyncio
import dataclasses
import json
import os
import platform
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, List, Optional, cast

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

prompt_session = PromptSession()

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility
    from enum import Enum as StrEnum

# Third-party imports
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm
import pyautogui
from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlock,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaRawContentBlockDeltaEvent,
    BetaRawContentBlockStartEvent,
    BetaRawContentBlockStopEvent,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)
from yaspin import yaspin
from yaspin.spinners import Spinners

# Local imports
from .profiles import Profile
from .tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult
from .ui.markdown import MarkdownRenderer
from .ui.tool import ToolRenderer

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

# Initialize markdown renderer
md = MarkdownRenderer()

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


# Helper function used in async_respond()
def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = result.error
    else:
        if result.output:
            tool_result_content.append({"type": "text", "text": result.output})
        if result.base64_image:
            tool_result_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result.base64_image,
                    },
                }
            )
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


class Interpreter:
    """
    Open Interpreter's main interface.

    The Interpreter class provides natural language interaction with your computer,
    executing commands and engaging in conversation based on user input.

    Examples
    --------
    >>> from interpreter import Interpreter

    # Basic usage
    interpreter = Interpreter()
    interpreter.chat("Hello, what can you help me with?")

    # With custom configuration
    from interpreter import Profile
    profile = Profile.from_file("~/custom_profile.json")
    interpreter = Interpreter(profile)

    # Save settings for later
    interpreter.save_profile("~/my_settings.json")

    Parameters
    ----------
    profile : Profile, optional
        Configuration object with settings. If None, uses default Profile.

    Attributes
    ----------
    model : str
        The model being used for interpretation
    provider : str
        The API provider being used
    api_base : str or None
        Custom API base URL if set
    api_key : str or None
        API key being used
    api_version : str or None
        API version being used
    max_budget : float
        Maximum budget in USD (-1 for unlimited)
    max_turns : int
        Maximum conversation turns (-1 for unlimited)
    """

    def __init__(self, profile=None):
        """
        Initialize interpreter with optional profile.
        If no profile provided, loads from default profile (~/.openinterpreter)
        """
        self._profile = profile or Profile()

        # Initialize all profile-based attributes
        for key, value in self._profile.to_dict().items():
            if key != "profile":
                setattr(self, key, value)

        self._client = None

    def to_dict(self):
        """Convert current settings to dictionary"""
        return {key: getattr(self, key) for key in self._profile.to_dict().keys()}

    def load_profile(self, path):
        """
        Load settings from a profile file

        Example:
        >>> interpreter.load_profile("~/work_settings.json")
        """
        self._profile.load(path)
        # Update interpreter attributes from new profile
        for key, value in self._profile.to_dict().items():
            setattr(self, key, value)

    def save_profile(self, path=None):
        """
        Save current settings as a profile

        Example:
        >>> interpreter.save_profile("~/my_preferred_settings.json")
        """
        # Update profile object with current values
        self._profile.from_dict(self.to_dict())
        # Save to file
        self._profile.save(path)

    @classmethod
    def from_profile(cls, path):
        """
        Create new interpreter instance from a profile file

        Example:
        >>> interpreter = Interpreter.from_profile("~/work_settings.json")
        """
        return cls(Profile.from_file(path))

    async def async_respond(self):
        """
        Agentic sampling loop for the assistant/tool interaction.
        Yields chunks and maintains message history on the interpreter instance.
        """
        tools = []
        if "interpreter" in self.tools:
            tools.append(BashTool())
        if "editor" in self.tools:
            tools.append(EditTool())
        if "gui" in self.tools:
            tools.append(ComputerTool())

        tool_collection = ToolCollection(*tools)
        system = BetaTextBlockParam(
            type="text",
            text=SYSTEM_PROMPT,
        )

        model_info = litellm.get_model_info(self.model)
        provider = model_info["litellm_provider"]
        max_tokens = model_info["max_tokens"]

        while True:
            spinner = yaspin(Spinners.simpleDots, text="")
            spinner.start()

            enable_prompt_caching = False
            betas = [COMPUTER_USE_BETA_FLAG]

            if enable_prompt_caching:
                betas.append(PROMPT_CACHING_BETA_FLAG)
                image_truncation_threshold = 50
                system["cache_control"] = {"type": "ephemeral"}

            edit = ToolRenderer()

            if self.provider == "anthropic":
                if self._client is None:
                    if self.api_key:
                        self._client = Anthropic(api_key=self.api_key)
                    else:
                        self._client = Anthropic()

                # Use Anthropic API which supports betas
                raw_response = self._client.beta.messages.create(
                    max_tokens=max_tokens,
                    messages=self.messages,
                    model=self.model,
                    system=system["text"],
                    tools=tool_collection.to_params(),
                    betas=betas,
                    stream=True,
                )

                response_content = []
                current_block = None
                first_token = True

                for chunk in raw_response:
                    if first_token:
                        spinner.stop()
                        first_token = False

                    if isinstance(chunk, BetaRawContentBlockStartEvent):
                        current_block = chunk.content_block
                    elif isinstance(chunk, BetaRawContentBlockDeltaEvent):
                        if chunk.delta.type == "text_delta":
                            md.feed(chunk.delta.text)
                            yield {"type": "chunk", "chunk": chunk.delta.text}
                            await asyncio.sleep(0)
                            if current_block and current_block.type == "text":
                                current_block.text += chunk.delta.text
                        elif chunk.delta.type == "input_json_delta":
                            if not hasattr(current_block, "partial_json"):
                                current_block.partial_json = ""
                                current_block.parsed_json = {}
                                current_block.current_key = None
                                current_block.current_value = ""

                            current_block.partial_json += chunk.delta.partial_json

                            if hasattr(current_block, "name"):
                                if edit.name == None:
                                    edit.name = current_block.name
                                edit.feed(chunk.delta.partial_json)

                    elif isinstance(chunk, BetaRawContentBlockStopEvent):
                        edit.close()
                        edit = ToolRenderer()
                        if current_block:
                            if hasattr(current_block, "partial_json"):
                                current_block.input = json.loads(
                                    current_block.partial_json
                                )
                                delattr(current_block, "partial_json")
                            else:
                                md.feed("\n")
                                yield {"type": "chunk", "chunk": "\n"}
                                await asyncio.sleep(0)

                            for attr in [
                                "partial_json",
                                "parsed_json",
                                "current_key",
                                "current_value",
                            ]:
                                if hasattr(current_block, attr):
                                    delattr(current_block, attr)
                            response_content.append(current_block)
                            current_block = None

                response = BetaMessage(
                    id=str(uuid.uuid4()),
                    content=response_content,
                    role="assistant",
                    model=self.model,
                    stop_reason=None,
                    stop_sequence=None,
                    type="message",
                    usage={"input_tokens": 0, "output_tokens": 0},
                )

                self.messages.append(
                    {
                        "role": "assistant",
                        "content": cast(list[BetaContentBlockParam], response.content),
                    }
                )

                user_approval = None
                if getattr(self, "auto_run", False):
                    user_approval = "y"
                else:
                    if not sys.stdin.isatty():
                        print(
                            "Error: Non-interactive environment requires auto_run=True"
                        )
                        exit(1)

                    content_blocks = cast(list[BetaContentBlock], response.content)
                    tool_use_blocks = [
                        b for b in content_blocks if b.type == "tool_use"
                    ]

                    if len(tool_use_blocks) > 1:
                        # Check if all tools are pre-approved
                        all_approved = all(
                            self._is_tool_approved(b) for b in tool_use_blocks
                        )
                        if all_approved:
                            user_approval = "y"
                        else:
                            print(f"\n\033[38;5;240mRun all actions above\033[0m?")
                            user_approval = input("\n(y/n/a): ").lower().strip()
                    elif len(tool_use_blocks) == 1:
                        tool_block = tool_use_blocks[0]
                        if self._is_tool_approved(tool_block):
                            user_approval = "y"
                        else:
                            if tool_block.name == "str_replace_editor":
                                path = tool_block.input.get("path")
                                if path.startswith(os.getcwd()):
                                    path = path[len(os.getcwd()) + 1 :]
                                    if path == "":
                                        path = "/"

                                if tool_block.input.get("command") == "create":
                                    print(
                                        f"\n\033[38;5;240mCreate \033[0m{path}\033[38;5;240m?\033[0m"
                                    )
                                elif tool_block.input.get("command") == "view":
                                    print(
                                        f"\n\033[38;5;240mView \033[0m{path}\033[38;5;240m?\033[0m"
                                    )
                                elif tool_block.input.get("command") in [
                                    "str_replace",
                                    "insert",
                                ]:
                                    print(
                                        f"\n\033[38;5;240mEdit \033[0m{path}\033[38;5;240m?\033[0m"
                                    )
                            elif tool_block.name == "bash":
                                command = tool_block.input.get("command")
                                print(f"\n\033[38;5;240mRun code?\033[0m")
                            else:
                                print(f"\n\033[38;5;240mRun tool?\033[0m")

                            user_approval = input("\n(y/n/a): ").lower().strip()

                            # Handle adding to allowed lists
                            if user_approval == "a":
                                if tool_block.name == "editor":
                                    path = tool_block.input.get("path")
                                    if path:
                                        self.allowed_paths.add(path)
                                        print(
                                            f"\n\033[38;5;240mEdits to {path} will be auto-approved in this session.\033[0m\n"
                                        )
                                else:  # bash/computer tools
                                    command = tool_block.input.get("command", "")
                                    if command:
                                        self.allowed_commands.add(command)
                                        print(
                                            f"\n\033[38;5;240mThe command '{command}' will be auto-approved in this session.\033[0m\n"
                                        )
                                user_approval = "y"

                tool_result_content: list[BetaToolResultBlockParam] = []
                for content_block in cast(list[BetaContentBlock], response.content):
                    if content_block.type == "tool_use":
                        edit.close()

                        if user_approval in ["y", "a"]:
                            result = await tool_collection.run(
                                name=content_block.name,
                                tool_input=cast(dict[str, Any], content_block.input),
                            )
                        else:
                            result = ToolResult(
                                output="Tool execution cancelled by user"
                            )
                        tool_result_content.append(
                            _make_api_tool_result(result, content_block.id)
                        )

                if user_approval == "n":
                    self.messages.append(
                        {"content": tool_result_content, "role": "user"}
                    )
                    yield {"type": "messages", "messages": self.messages}
                    break

                if not tool_result_content:
                    yield {"type": "messages", "messages": self.messages}
                    break

                self.messages.append(
                    {
                        "content": tool_result_content,
                        "role": "user" if self.provider == "anthropic" else "tool",
                    }
                )

            else:
                # LiteLLM implementation would go here
                # (I can add this if you'd like, but focusing on the Anthropic path for now)
                pass

    def _handle_command(self, cmd: str, parts: list[str]) -> bool:
        """Handle / commands for controlling interpreter settings"""

        SETTINGS = {
            "model": (str, "Model (e.g. claude-3-5-sonnet-20241022)"),
            "provider": (str, "Provider (e.g. anthropic, openai)"),
            "system_message": (str, "System message"),
            "tools": (list, "Enabled tools (comma-separated: interpreter,editor,gui)"),
            "auto_run": (bool, "Auto-run tools without confirmation"),
            "tool_calling": (bool, "Enable/disable tool calling"),
            "api_base": (str, "Custom API endpoint"),
            "api_key": (str, "API key"),
            "api_version": (str, "API version"),
            "temperature": (float, "Sampling temperature (0-1)"),
            "max_budget": (float, "Maximum budget in USD (-1 for unlimited)"),
            "max_turns": (int, "Maximum conversation turns (-1 for unlimited)"),
        }

        def parse_value(value_str: str, type_hint: type):
            """Convert string value to appropriate type"""
            if type_hint == bool:
                return True
            if type_hint == list:
                return value_str.split(",")
            if type_hint == float:
                return float(value_str)
            if type_hint == int:
                return int(value_str)
            return value_str

        def print_help():
            print("Available Commands:")
            print("  /help                Show this help message")
            print("\nProfile Management:")
            print("  /profile show        Show current profile location")
            print(
                "  /profile save [path] Save settings to profile (default: ~/.openinterpreter)"
            )
            print("  /profile load <path> Load settings from profile")
            print("  /profile reset       Reset settings to defaults")
            print("\nSettings:")
            for name, (_, help_text) in SETTINGS.items():
                print(f"  /set {name} <value>    {help_text}")
            print("  /set no_<setting>    Disable boolean settings")
            print()

        # Handle /help
        if cmd == "/help":
            print_help()
            return True

        # Handle /profile commands
        if cmd == "/profile":
            if len(parts) < 2:
                print(
                    "Error: Missing profile command. Use /help to see available commands."
                )
                return True

            subcmd = parts[1].lower()
            path = parts[2] if len(parts) > 2 else None

            if subcmd == "show":
                path = os.path.expanduser(self._profile.profile_path)
                if not os.path.exists(path):
                    print(f"Profile does not exist yet. Current path would be: {path}")
                    return True

                if platform.system() == "Darwin":  # macOS
                    os.system(f"open -R '{path}'")
                elif platform.system() == "Windows":
                    os.system(f"explorer /select,{path}")
                else:
                    print(f"Current profile path: {path}")
                return True

            elif subcmd == "save":
                try:
                    self.save_profile(path)
                    if path:
                        print(f"Settings saved to: {path}")
                    else:
                        print("Settings saved to default profile (~/.openinterpreter)")
                except Exception as e:
                    print(f"Error saving profile: {str(e)}")
                return True

            elif subcmd == "load":
                if not path:
                    print("Error: Missing path for profile load")
                    return True
                try:
                    self.load_profile(path)
                    print(f"Settings loaded from: {path}")
                except Exception as e:
                    print(f"Error loading profile: {str(e)}")
                return True

            elif subcmd == "reset":
                path = os.path.expanduser(self._profile.profile_path)
                if os.path.exists(path):
                    print(
                        f"\n\033[38;5;240mThis will reset all settings to defaults and overwrite:\033[0m {path}"
                    )
                    confirmation = input("\nAre you sure? (y/n): ").lower().strip()
                    if confirmation != "y":
                        print("Reset cancelled")
                        return True

                # Create new profile with defaults
                self._profile = Profile()
                # Update interpreter attributes
                for key, value in self._profile.to_dict().items():
                    if key != "profile":
                        setattr(self, key, value)
                # Save to file
                self._profile.save()
                print("Settings reset to defaults")
                return True

            else:
                print(f"Unknown profile command: {subcmd}")
                print("Use /help to see available commands")
                return True

        # Handle /set commands
        if cmd == "/set":
            if len(parts) < 2:
                print("Error: Missing parameter name")
                return True

            param = parts[1].lower()
            value_str = parts[2] if len(parts) > 2 else ""

            # Provider resets client
            if param == "provider":
                self._client = None

            # Handle boolean negation (no_<setting>)
            if param.startswith("no_"):
                actual_param = param[3:]
                if actual_param in SETTINGS and SETTINGS[actual_param][0] == bool:
                    setattr(self, actual_param, False)
                    print(f"Set {actual_param} = False")
                    return True

            if param not in SETTINGS:
                print(f"Unknown parameter: {param}")
                return True

            type_hint, _ = SETTINGS[param]
            try:
                value = parse_value(value_str, type_hint)
                setattr(self, param, value)
                print(f"Set {param} = {value}")
            except (ValueError, TypeError) as e:
                print(f"Error setting {param}: {str(e)}")
            return True

        # Not a recognized command
        return False

    def chat(self):
        """
        Interactive mode
        """
        try:
            placeholder_color = "ansigray"

            while True:
                # Get first line of input with placeholder
                placeholder = HTML(
                    f'<{placeholder_color}>Use """ for multi-line prompts</{placeholder_color}>'
                )
                user_input = prompt_session.prompt(
                    "> ", placeholder=placeholder
                ).strip()
                print()

                # Handle multi-line input
                if user_input == '"""':
                    user_input = ""
                    print('> """')
                    while True:
                        placeholder = HTML(
                            f'<{placeholder_color}>Use """ again to finish</{placeholder_color}>'
                        )
                        line = prompt_session.prompt(
                            "", placeholder=placeholder
                        ).strip()
                        if line == '"""':
                            break
                        user_input += line + "\n"
                    print()

                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=2)
                    cmd = parts[0].lower()
                    if self._handle_command(cmd, parts):
                        continue

                self.messages.append({"role": "user", "content": user_input})

                for _ in self.respond():
                    pass

                print()
        except KeyboardInterrupt:
            print()
            pass

    async def _consume_generator(self, generator):
        """Consume the async generator from async_respond"""
        async for chunk in generator:
            yield chunk

    def respond(self):
        """
        Synchronous wrapper around async_respond.
        Yields chunks from the async generator.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def run():
            async for chunk in self.async_respond():
                yield chunk

        agen = run()
        while True:
            try:
                chunk = loop.run_until_complete(anext(agen))
                yield chunk
            except StopAsyncIteration:
                break

        return self.messages

    def server(self):
        """
        Start an OpenAI-compatible API server.
        """
        from .server import Server

        # Initialize messages if not already set
        if not hasattr(self, "messages"):
            self.messages = []

        # Set auto_run to True for server mode
        self.auto_run = True

        # Create and start server
        server = Server(self)
        try:
            server.run()
        except KeyboardInterrupt:
            print("\nShutting down server...")

    def _is_tool_approved(self, tool_block: BetaContentBlock) -> bool:
        """Check if a tool use is pre-approved based on stored paths/commands"""
        if tool_block.name == "editor":
            path = tool_block.input.get("path")
            return path in self.allowed_paths
        else:  # bash/computer tools
            command = tool_block.input.get("command", "")
            return command in self.allowed_commands
