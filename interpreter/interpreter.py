import asyncio
import dataclasses
import json
import os
import platform
import sys
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, cast

from readchar import readchar

from .misc.get_input import async_get_input

# Third-party imports
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import webbrowser
from urllib.parse import quote

import litellm

litellm.suppress_debug_info = True
litellm.REPEATED_STREAMING_CHUNK_LIMIT = 99999999
litellm.modify_params = True
# litellm.drop_params = True

from anthropic import Anthropic
from anthropic.types.beta import (
    BetaContentBlock,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaRawContentBlockDeltaEvent,
    BetaRawContentBlockStartEvent,
    BetaRawContentBlockStopEvent,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

from .commands import CommandHandler
from .misc.spinner import SimpleSpinner
from .profiles import Profile
from .tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult
from .ui.markdown import MarkdownRenderer
from .ui.tool import ToolRenderer

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

# Initialize markdown renderer
md = MarkdownRenderer()


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

    Examples
    --------
    >>> from interpreter import Interpreter

    # Basic usage
    interpreter = Interpreter()
    interpreter.chat()

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
        self._spinner = SimpleSpinner("")
        self._command_handler = CommandHandler(self)
        self._stop_flag = False  # Add stop flag

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

    def default_system_message(self):
        system_message = "<SYSTEM_CAPABILITY>\n"

        try:
            system_message += f"* You are an AI assistant with access to a machine running on {'Mac OS' if platform.system() == 'Darwin' else platform.system()} with internet access.\n"
        except:
            print("Error adding system capability for platform")

        try:
            system_message += (
                f"* The current date is {datetime.today().strftime('%A, %B %d, %Y')}.\n"
            )
        except:
            print("Error adding system capability for date")

        try:
            cwd_line = f"* The user's cwd is {os.getcwd()}"
            try:
                cwd_line += f" and username is {os.getlogin()}"
            except:
                print("Error adding system capability for username")
            system_message += cwd_line + "\n"
        except:
            print("Error adding system capability for cwd")

        system_message += "</SYSTEM_CAPABILITY>"

        # Add web search capability if enabled
        if (
            os.environ.get("INTERPRETER_EXPERIMENTAL_WEB_SEARCH", "false").lower()
            == "true"
        ):
            system_message = system_message.replace(
                "</SYSTEM_CAPABILITY>",
                "* For any web search requests, curl https://api.openinterpreter.com/v0/browser/search?query=your+search+query\n</SYSTEM_CAPABILITY>",
            )

        # Update system prompt for Mac OS, if computer tool is enabled
        if platform.system() == "Darwin" and "gui" in self.tools:
            system_message += """
            <IMPORTANT>
            * Open applications using Spotlight by using the computer tool to simulate pressing Command+Space, typing the application name, and pressing Enter.
            </IMPORTANT>"""

        return system_message

    async def async_respond(self, user_input=None):
        """
        Agentic sampling loop for the assistant/tool interaction.
        Yields chunks and maintains message history on the interpreter instance.
        """
        if user_input:
            self.messages.append({"role": "user", "content": user_input})

        tools = []
        if "interpreter" in self.tools:
            tools.append(BashTool())
        if "editor" in self.tools:
            tools.append(EditTool())
        if "gui" in self.tools:
            tools.append(ComputerTool())

        tool_collection = ToolCollection(*tools)

        # Get provider and max_tokens, with fallbacks
        provider = self.provider  # Keep existing provider if set
        max_tokens = self.max_tokens  # Keep existing max_tokens if set

        if provider is None and self.model in [
            "claude-3-5-sonnet-latest",
            "claude-3-5-sonnet-20241022",
        ]:
            # For some reason, Litellm can't find the model info for these
            provider = "anthropic"

        # Only try to get model info if we need either provider or max_tokens
        if provider is None or max_tokens is None:
            try:
                model_info = litellm.get_model_info(self.model)
                if provider is None:
                    provider = model_info["litellm_provider"]
                if max_tokens is None:
                    max_tokens = model_info["max_tokens"]
            except:
                # Fallback values if model info unavailable
                if provider is None:
                    provider = "openai"
                if max_tokens is None:
                    max_tokens = 4000

        if self.system_message is None:
            system_message = self.default_system_message()
        else:
            system_message = self.system_message

        system_message = (system_message + "\n\n" + self.instructions).strip()

        system = BetaTextBlockParam(
            type="text",
            text=system_message,
        )

        # Count turns
        turn_count = 0

        while True:
            if self._stop_flag:
                break

            turn_count += 1
            if turn_count > self.max_turns and self.max_turns != -1:
                print("\nMax turns reached, exiting\n")
                break

            self._spinner.start()

            betas = [COMPUTER_USE_BETA_FLAG]

            edit = ToolRenderer()

            if (
                provider == "anthropic" and not self.serve
            ):  # Server can't handle Anthropic yet
                if self._client is None:
                    anthropic_params = {}
                    if self.api_key is not None:
                        anthropic_params["api_key"] = self.api_key
                    if self.api_base is not None:
                        anthropic_params["base_url"] = self.api_base
                    self._client = Anthropic(**anthropic_params)

                if self.debug:
                    print("Sending messages:", self.messages, "\n")

                model = self.model
                if model.startswith("anthropic/"):
                    model = model[len("anthropic/") :]

                # Use Anthropic API which supports betas
                raw_response = self._client.beta.messages.create(
                    max_tokens=max_tokens,
                    messages=self.messages,
                    model=model,
                    system=system["text"],
                    tools=tool_collection.to_params(),
                    betas=betas,
                    stream=True,
                )

                response_content = []
                current_block = None
                first_token = True

                for chunk in raw_response:
                    yield chunk

                    if first_token:
                        self._spinner.stop()
                        first_token = False

                    if isinstance(chunk, BetaRawContentBlockStartEvent):
                        current_block = chunk.content_block
                    elif isinstance(chunk, BetaRawContentBlockDeltaEvent):
                        if chunk.delta.type == "text_delta":
                            md.feed(chunk.delta.text)
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
                                if edit.name is None:
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

                edit.close()

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

                # Only append if response has meaningful content
                if response.content:
                    self.messages.append(
                        {
                            "role": "assistant",
                            "content": cast(
                                list[BetaContentBlockParam], response.content
                            ),
                        }
                    )

                content_blocks = cast(list[BetaContentBlock], response.content)
                tool_use_blocks = [b for b in content_blocks if b.type == "tool_use"]

                # If there are no tool use blocks, we're done
                if not tool_use_blocks:
                    break

                user_approval = None
                if self.auto_run:
                    user_approval = "y"
                else:
                    if len(tool_use_blocks) > 1:
                        # Check if all tools are pre-approved
                        all_approved = all(
                            self._is_tool_approved(b) for b in tool_use_blocks
                        )
                        if all_approved:
                            user_approval = "y"
                        else:
                            print(f"\n\033[38;5;240mRun all actions above\033[0m?")
                            user_approval = self._ask_user_approval()

                        if not self.interactive:
                            user_approval = "n"
                    elif len(tool_use_blocks) == 1:
                        tool_block = tool_use_blocks[0]
                        if self._is_tool_approved(tool_block):
                            user_approval = "y"
                        elif not self.interactive:
                            user_approval = "n"
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

                            user_approval = self._ask_user_approval()

                            # Handle adding to allowed lists
                            if user_approval == "a":
                                if tool_block.name == "editor":
                                    path = tool_block.input.get("path")
                                    if path:
                                        self.allowed_paths.append(path)
                                        print(
                                            f"\n\033[38;5;240mEdits to {path} will be auto-approved in this session.\033[0m\n"
                                        )
                                else:  # bash/computer tools
                                    command = tool_block.input.get("command", "")
                                    if command:
                                        self.allowed_commands.append(command)
                                        print(
                                            f"\n\033[38;5;240mThe command '{command}' will be auto-approved in this session.\033[0m\n"
                                        )
                                user_approval = "y"

                tool_result_content: list[BetaToolResultBlockParam] = []
                for content_block in cast(list[BetaContentBlock], response.content):
                    if content_block.type == "tool_use":
                        if user_approval in ["y", "a"]:
                            result = await tool_collection.run(
                                name=content_block.name,
                                tool_input=cast(dict[str, Any], content_block.input),
                            )
                        else:
                            if self.interactive:
                                result = ToolResult(
                                    output="Tool execution cancelled by user"
                                )
                            else:
                                result = ToolResult(
                                    output="You can only run the following commands: "
                                    + ", ".join(self.allowed_commands)
                                    + "\nOr edit/view the following paths: "
                                    + ", ".join(self.allowed_paths)
                                )
                        tool_result_content.append(
                            _make_api_tool_result(result, content_block.id)
                        )

                if not tool_result_content:
                    break

                self.messages.append(
                    {
                        "content": tool_result_content,
                        "role": "user",
                    }
                )

                if user_approval == "n" and self.interactive:
                    break

            else:
                tools = []
                if "interpreter" in self.tools:
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "description": """Run commands in a bash shell\n
                                * When invoking this tool, the contents of the \"command\" parameter does NOT need to be XML-escaped.\n
                                * You don't have access to the internet via this tool.\n
                                * You do have access to a mirror of common linux and python packages via apt and pip.\n
                                * State is persistent across command calls and discussions with the user.\n
                                * To inspect a particular line range of a file, e.g. lines 10-25, try 'sed -n 10,25p /path/to/the/file'.\n
                                * Please avoid commands that may produce a very large amount of output.\n
                                * Please run long lived commands in the background, e.g. 'sleep 10 &' or start a server in the background.""",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": "The bash command to run.",
                                        }
                                    },
                                    "required": ["command"],
                                },
                            },
                        }
                    )
                if "editor" in self.tools:
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": "str_replace_editor",
                                "description": """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`""",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": "The command to execute: view, create, str_replace, insert, or undo_edit",
                                            "enum": [
                                                "view",
                                                "create",
                                                "str_replace",
                                                "insert",
                                                "undo_edit",
                                            ],
                                        },
                                        "path": {
                                            "type": "string",
                                            "description": "Absolute path to the file or directory",
                                        },
                                        "file_text": {
                                            "type": "string",
                                            "description": "File content for create command",
                                        },
                                        "view_range": {
                                            "type": "array",
                                            "description": "Two integers specifying start and end line numbers for view command",
                                            "items": {"type": "integer"},
                                            "minItems": 2,
                                            "maxItems": 2,
                                        },
                                        "old_str": {
                                            "type": "string",
                                            "description": "Text to replace for str_replace command",
                                        },
                                        "new_str": {
                                            "type": "string",
                                            "description": "Replacement text for str_replace or insert commands",
                                        },
                                        "insert_line": {
                                            "type": "integer",
                                            "description": "Line number where to insert text for insert command",
                                        },
                                    },
                                    "required": ["command", "path"],
                                },
                            },
                        }
                    )
                if "gui" in self.tools:
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": "computer",
                                "description": """Control the computer's mouse, keyboard and screen interactions
                        * Coordinates are scaled to standard resolutions (max 1366x768)
                        * Screenshots are automatically taken after most actions
                        * For key commands, use normalized key names (e.g. 'pagedown' -> 'pgdn', 'enter'/'return' are interchangeable)
                        * On macOS, 'super+' is automatically converted to 'command+'
                        * Mouse movements use smooth easing for natural motion""",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "action": {
                                            "type": "string",
                                            "description": "The action to perform",
                                            "enum": [
                                                "key",  # Send keyboard input (hotkeys or single keys)
                                                "type",  # Type text with a slight delay between characters
                                                "mouse_move",  # Move mouse cursor to coordinates
                                                "left_click",  # Perform left mouse click
                                                "left_click_drag",  # Click and drag from current pos to coordinates
                                                "right_click",  # Perform right mouse click
                                                "middle_click",  # Perform middle mouse click
                                                "double_click",  # Perform double left click
                                                "screenshot",  # Take a screenshot
                                                "cursor_position",  # Get current cursor coordinates
                                            ],
                                        },
                                        "text": {
                                            "type": "string",
                                            "description": "Text to type or key command to send (required for 'key' and 'type' actions)",
                                        },
                                        "coordinate": {
                                            "type": "array",
                                            "description": "X,Y coordinates for mouse actions (required for 'mouse_move' and 'left_click_drag')",
                                            "items": {"type": "integer"},
                                            "minItems": 2,
                                            "maxItems": 2,
                                        },
                                    },
                                    "required": ["action"],
                                },
                            },
                        }
                    )

                if self.model.startswith("ollama/"):
                    # Fix ollama
                    stream = False
                    actual_model = self.model.replace("ollama/", "openai/")
                    if self.api_base is None:
                        api_base = "http://localhost:11434/v1/"
                    else:
                        api_base = self.api_base
                else:
                    if (
                        not self.model.startswith("openai/")
                        and self.provider == "openai"
                    ):
                        actual_model = "openai/" + self.model
                    else:
                        actual_model = self.model

                    stream = True
                    api_base = self.api_base

                if not self.tool_calling:
                    system_message += "\n\nPLEASE write code to satisfy the user's request, use ```bash\n...\n``` to run code. You CAN run code."

                params = {
                    "model": actual_model,
                    "messages": [{"role": "system", "content": system_message}]
                    + self.messages,
                    "stream": stream,
                    "api_base": api_base,
                    "temperature": self.temperature,
                    "api_key": self.api_key,
                    "api_version": self.api_version,
                    # "parallel_tool_calls": True,
                }

                if self.tool_calling:
                    params["tools"] = tools
                else:
                    params["stream"] = False
                    stream = False

                if provider == "anthropic" and self.tool_calling:
                    params["tools"] = tool_collection.to_params()
                    for t in params["tools"]:
                        t["function"] = {"name": t["name"]}
                        if t["name"] == "computer":
                            t["function"]["parameters"] = {
                                "display_height_px": t["display_height_px"],
                                "display_width_px": t["display_width_px"],
                                "display_number": t["display_number"],
                            }
                    params["extra_headers"] = {
                        "anthropic-beta": "computer-use-2024-10-22"
                    }

                # if self.debug:
                #     print("Sending request...", params)
                #     time.sleep(3)

                if self.debug:
                    print("Messages:")
                    for m in self.messages:
                        if len(str(m)) > 1000:
                            print(str(m)[:1000] + "...")
                        else:
                            print(str(m))
                    print()

                raw_response = litellm.completion(**params)

                if not stream:
                    raw_response.choices[0].delta = raw_response.choices[0].message
                    raw_response = [raw_response]

                if not self.tool_calling:
                    # Add the original message to the messages list
                    self.messages.append(
                        {
                            "role": "assistant",
                            "content": raw_response[0].choices[0].delta.content,
                        }
                    )

                    # Extract code blocks from non-tool-calling response
                    content = raw_response[0].choices[0].delta.content
                    message = raw_response[0].choices[0].delta
                    message.tool_calls = []
                    message.content = ""

                    # Find all code blocks between backticks
                    while "```" in content:
                        try:
                            # Split on first ``` to get everything after it
                            before, rest = content.split("```", 1)
                            message.content += before

                            # Handle optional language identifier
                            if "\n" in rest:
                                maybe_lang, rest = rest.split("\n", 1)
                            else:
                                maybe_lang = ""

                            # Split on closing ``` to get code block
                            code, content = rest.split("```", 1)

                            # Create tool call for the code block
                            tool_call = type(
                                "ToolCall",
                                (),
                                {
                                    "id": f"call_{len(message.tool_calls)}",
                                    "function": type(
                                        "Function",
                                        (),
                                        {
                                            "name": "bash",
                                            "arguments": json.dumps(
                                                {"command": code.strip()}
                                            ),
                                        },
                                    ),
                                },
                            )
                            message.tool_calls.append(tool_call)

                        except ValueError:
                            # Handle malformed code blocks by breaking
                            break

                    # Add any remaining content after the last code block
                    message.content += content
                    raw_response = [raw_response[0]]

                message = None
                first_token = True

                for chunk in raw_response:
                    yield chunk

                    if first_token:
                        self._spinner.stop()
                        first_token = False

                    if message is None:
                        message = chunk.choices[0].delta

                    if chunk.choices[0].delta.content:
                        md.feed(chunk.choices[0].delta.content)
                        await asyncio.sleep(0)

                        if message.content is None:
                            message.content = chunk.choices[0].delta.content
                        elif chunk.choices[0].delta.content is not None:
                            message.content += chunk.choices[0].delta.content

                    if chunk.choices[0].delta.tool_calls:
                        if chunk.choices[0].delta.tool_calls[0].id:
                            if message.tool_calls is None or chunk.choices[
                                0
                            ].delta.tool_calls[0].id not in [
                                t.id for t in message.tool_calls
                            ]:
                                edit.close()
                                edit = ToolRenderer()
                                if message.tool_calls is None:
                                    message.tool_calls = []
                                message.tool_calls.append(
                                    chunk.choices[0].delta.tool_calls[0]
                                )
                            current_tool_call = [
                                t
                                for t in message.tool_calls
                                if t.id == chunk.choices[0].delta.tool_calls[0].id
                            ][0]

                        if chunk.choices[0].delta.tool_calls[0].function.name:
                            tool_name = (
                                chunk.choices[0].delta.tool_calls[0].function.name
                            )
                            if edit.name is None:
                                edit.name = tool_name
                            if current_tool_call.function.name is None:
                                current_tool_call.function.name = tool_name
                        if chunk.choices[0].delta.tool_calls[0].function.arguments:
                            arguments_delta = (
                                chunk.choices[0].delta.tool_calls[0].function.arguments
                            )
                            edit.feed(arguments_delta)

                            if chunk.choices[0].delta != message:
                                current_tool_call.function.arguments += arguments_delta

                    if chunk.choices[0].finish_reason:
                        edit.close()
                        edit = ToolRenderer()

                if self.tool_calling:
                    self.messages.append(message)

                print()

                if not message.tool_calls:
                    break

                if self.auto_run:
                    user_approval = "y"
                else:
                    user_approval = input("\nRun tool(s)? (y/n): ").lower().strip()

                user_content_to_add = []

                for tool_call in message.tool_calls:
                    function_arguments = json.loads(tool_call.function.arguments)

                    if user_approval == "y":
                        result = await tool_collection.run(
                            name=tool_call.function.name,
                            tool_input=cast(dict[str, Any], function_arguments),
                        )
                    else:
                        result = ToolResult(output="Tool execution cancelled by user")

                    if self.tool_calling:
                        if result.error:
                            output = result.error
                        else:
                            output = result.output

                        tool_output = ""

                        if output:
                            tool_output += output

                        if result.base64_image:
                            tool_output += (
                                "\nThe user will reply with the tool's image output."
                            )
                            user_content_to_add.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{result.base64_image}",
                                    },
                                }
                            )

                        if tool_output == "":
                            tool_output = "No output from tool."

                        self.messages.append(
                            {
                                "role": "tool",
                                "content": tool_output.strip(),
                                "tool_call_id": tool_call.id,
                            }
                        )
                    else:
                        text_content = (
                            "This was the output of the tool call. What does it mean/what's next?\n"
                            + (result.output or "")
                        )
                        if result.base64_image:
                            content = [
                                {"type": "text", "text": text_content},
                                {
                                    "type": "image",
                                    "image_url": {
                                        "url": "data:image/png;base64,"
                                        + result.base64_image
                                    },
                                },
                            ]
                        else:
                            content = text_content

                        self.messages.append({"role": "user", "content": content})

                if user_content_to_add:
                    self.messages.append(
                        {"role": "user", "content": user_content_to_add}
                    )

    def _ask_user_approval(self) -> str:
        """Ask user for approval to run a tool"""
        # print("\n\033[38;5;240m(\033[0my\033[38;5;240m)es (\033[0mn\033[38;5;240m)o (\033[0ma\033[38;5;240m)lways approve this command: \033[0m", end="", flush=True)
        # Simpler y/n prompt
        print(
            "\n\033[38;5;240m(\033[0my\033[38;5;240m/\033[0mn\033[38;5;240m): \033[0m",
            end="",
            flush=True,
        )
        try:
            user_approval = readchar().lower()
            print(user_approval, "\n")
            return user_approval
        except KeyboardInterrupt:
            print()
            return "n"

    def _handle_command(self, cmd: str, parts: list[str]) -> bool:
        return self._command_handler.handle_command(cmd, parts)

    def chat(self):
        """Chat with the interpreter. Handles both sync and async contexts."""
        try:
            loop = asyncio.get_running_loop()
            # If we get here, there is a running event loop
            loop.create_task(self.async_chat())
        except RuntimeError:
            # No running event loop, create one
            asyncio.run(self.async_chat())

    async def async_chat(self):
        original_message_length = len(self.messages)

        try:
            message_count = 0
            while True:
                try:
                    user_input = await async_get_input()
                except KeyboardInterrupt:
                    print()
                    return self.messages[original_message_length:]

                message_count += 1  # Increment counter after each message

                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=2)
                    cmd = parts[0].lower()
                    if self._handle_command(cmd, parts):
                        continue

                if user_input == "":
                    if message_count in range(8, 11):
                        print("Error: Cat is asleep on Enter key\n")
                    else:
                        print("Error: No input provided\n")
                    continue

                try:
                    print()
                    async for _ in self.async_respond(user_input):
                        pass
                except KeyboardInterrupt:
                    self._spinner.stop()
                except asyncio.CancelledError:
                    self._spinner.stop()

                print()
        except:
            self._spinner.stop()
            print(traceback.format_exc())
            print("\n\n\033[91mAn error has occurred.\033[0m")
            if self.interactive:
                print(
                    "\nOpen Interpreter is self-healing. If you report this error, it will be autonomously repaired."
                )
                if (
                    input(
                        "\n\033[1mReport error?\033[0m This opens Github. (y/N): "
                    ).lower()
                    == "y"
                ):
                    self._report_error("".join(traceback.format_exc()))
            exit(1)

    def respond(self, user_input=None, stream=False):
        """Sync method to respond to user input if provided, or to the messages in self.messages."""
        if user_input:
            self.messages.append({"role": "user", "content": user_input})

        if stream:
            return self._sync_respond_stream()
        else:
            original_message_length = len(self.messages)
            for _ in self._sync_respond_stream():
                pass
            return self.messages[original_message_length:]

    def _sync_respond_stream(self):
        """Synchronous generator that yields responses. Only use in synchronous contexts."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Convert async generator to sync generator
            async_gen = self.async_respond()
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    def server(self):
        """
        Start an OpenAI-compatible API server.
        """
        from .server import Server

        # Create and start server
        server = Server(self)
        try:
            host = server.host
            port = server.port

            print("\n" + "=" * 60)
            print(f"Open Interpreter API Server")
            print("=" * 60)
            print("\nTo use with an OpenAI-compatible client, configure:")
            print(f"  - API Base:     http://{host}:{port}")
            print(f"  - API Path:     /chat/completions")
            print(f"  - API Key:      (any value, authentication not required)")
            print(f"  - Model name:   (any value, ignored)")
            print("\nNOTE: The server will use the model configured in --model")
            print(f"      Currently using: {self.model}")
            print("=" * 60 + "\n")

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

    def _report_error(self, traceback_str) -> None:
        # Extract key information
        error_type = traceback_str.splitlines()[-1]
        system = platform.system()
        python_version = sys.version
        conversation = "\n\n".join(
            str(msg["role"].upper()) + ": " + str(msg["content"])
            for msg in self.messages
        )

        # Build error details sections
        error_section = "### Error Details\n\n" + traceback_str
        system_section = (
            "### System Information\n\nOS: " + system + "\nPython: " + python_version
        )
        convo_section = "### Conversation History\n\n" + conversation

        # Combine sections
        error_details = "\n\n".join([convo_section, error_section, system_section])

        # Create GitHub issue URL components
        title = quote("Error Report: " + error_type[:100])
        body = quote(error_details)
        labels = quote("bug,automated-report")

        # Generate and open GitHub issue URL
        base_url = "https://github.com/openinterpreter/open-interpreter/issues/new"
        params = "?title=" + title + "&body=" + body + "&labels=" + labels
        webbrowser.open(base_url + params)

        print(
            "\nThank you! A browser window has been opened. Please review the information before submitting.\n"
        )
        print(
            "\nFor more assistance, please join our Discord: https://discord.gg/Hvz9Axh84z\n"
        )
