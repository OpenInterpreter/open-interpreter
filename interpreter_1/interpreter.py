import asyncio
import dataclasses
import json
import os
import platform
import sys
import traceback
import uuid
from datetime import datetime
from typing import Any, cast

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from readchar import readchar

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility
    from enum import Enum as StrEnum

# Third-party imports
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import webbrowser
from urllib.parse import quote

import litellm

litellm.suppress_debug_info = True
litellm.REPEATED_STREAMING_CHUNK_LIMIT = 99999999
litellm.modify_params = True

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

# Local imports
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
        self._prompt_session = None
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
        system_message = f"""<SYSTEM_CAPABILITY>
        * You are an AI assistant with access to a machine running on {"Mac OS" if platform.system() == "Darwin" else platform.system()} with internet access.
        * The current date is {datetime.today().strftime('%A, %B %d, %Y')}.
        * The user's cwd is {os.getcwd()} and username is {os.getlogin()}.
        </SYSTEM_CAPABILITY>"""

        # Add web search capability if enabled
        if (
            os.environ.get("INTERPRETER_EXPERIMENTAL_WEB_SEARCH", "false").lower()
            == "true"
        ):
            system_message = system_message.replace(
                "</SYSTEM_CAPABILITY>",
                "* For fast web searches (like up-to-date docs) curl https://api.openinterpreter.com/v0/browser/search?query=your+search+query\n</SYSTEM_CAPABILITY>",
            )

        # Update system prompt for Mac OS, if computer tool is enabled
        if platform.system() == "Darwin" and "gui" in self.tools:
            system_message += """
            <IMPORTANT>
            * Open applications using Spotlight by using the computer tool to simulate pressing Command+Space, typing the application name, and pressing Enter.
            </IMPORTANT>"""

        return system_message

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

        model_info = litellm.get_model_info(self.model)

        if self.provider == None:
            provider = model_info["litellm_provider"]
        else:
            provider = self.provider

        max_tokens = model_info["max_tokens"]

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

            enable_prompt_caching = False
            betas = [COMPUTER_USE_BETA_FLAG]

            if enable_prompt_caching:
                betas.append(PROMPT_CACHING_BETA_FLAG)
                image_truncation_threshold = 50
                system["cache_control"] = {"type": "ephemeral"}

            edit = ToolRenderer()

            if (
                provider == "anthropic" and not self.serve
            ):  # Server can't handle Anthropic yet
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

                self.messages.append(
                    {
                        "role": "assistant",
                        "content": cast(list[BetaContentBlockParam], response.content),
                    }
                )

                content_blocks = cast(list[BetaContentBlock], response.content)
                tool_use_blocks = [b for b in content_blocks if b.type == "tool_use"]

                # If there are no tool use blocks, we're done
                if not tool_use_blocks:
                    break

                user_approval = None
                if getattr(self, "auto_run", False):
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
                            print(
                                "Error: Non-interactive environment requires auto_run=True to run tools"
                            )
                            exit(1)
                    elif len(tool_use_blocks) == 1:
                        tool_block = tool_use_blocks[0]
                        if self._is_tool_approved(tool_block):
                            user_approval = "y"
                        else:
                            if not self.interactive:
                                print(
                                    "Error: Non-interactive environment requires auto_run=True to run tools"
                                )
                                exit(1)

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
                    break

                if not tool_result_content:
                    break

                self.messages.append(
                    {
                        "content": tool_result_content,
                        "role": "user" if provider == "anthropic" else "tool",
                    }
                )

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
                    print("\nEditor is not supported for non-Anthropic models yet.\n")
                    pass
                if "gui" in self.tools:
                    print("\nGUI is not supported for non-Anthropic models yet.\n")
                    pass

                if self.model.startswith("ollama/"):
                    # Fix ollama
                    stream = False
                    actual_model = self.model.replace("ollama/", "openai/")
                    if self.api_base == None:
                        api_base = "http://localhost:11434/v1/"
                    else:
                        api_base = self.api_base
                else:
                    stream = True
                    api_base = self.api_base
                    actual_model = self.model

                params = {
                    "model": actual_model,
                    "messages": [{"role": "system", "content": system_message}]
                    + self.messages,
                    "stream": stream,
                    "api_base": api_base,
                    "temperature": self.temperature,
                    "tools": tools,
                }

                raw_response = litellm.completion(**params)

                if not stream:
                    raw_response.choices[0].delta = raw_response.choices[0].message
                    raw_response = [raw_response]

                message = None
                first_token = True

                for chunk in raw_response:
                    yield chunk

                    if first_token:
                        self._spinner.stop()
                        first_token = False

                    if message == None:
                        message = chunk.choices[0].delta

                    if chunk.choices[0].delta.content:
                        md.feed(chunk.choices[0].delta.content)
                        await asyncio.sleep(0)

                        if message.content == None:
                            message.content = chunk.choices[0].delta.content
                        elif chunk.choices[0].delta.content != None:
                            message.content += chunk.choices[0].delta.content

                    if chunk.choices[0].delta.tool_calls:
                        if chunk.choices[0].delta.tool_calls[0].id:
                            if message.tool_calls == None or chunk.choices[
                                0
                            ].delta.tool_calls[0].id not in [
                                t.id for t in message.tool_calls
                            ]:
                                edit.close()
                                edit = ToolRenderer()
                                if message.tool_calls == None:
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
                            if edit.name == None:
                                edit.name = tool_name
                            if current_tool_call.function.name == None:
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

                self.messages.append(message)

                print()

                if not message.tool_calls:
                    break

                if self.auto_run:
                    user_approval = "y"
                else:
                    user_approval = input("\nRun tool(s)? (y/n): ").lower().strip()

                for tool_call in message.tool_calls:
                    function_arguments = json.loads(tool_call.function.arguments)

                    if user_approval == "y":
                        result = await tool_collection.run(
                            name=tool_call.function.name,
                            tool_input=cast(dict[str, Any], function_arguments),
                        )
                    else:
                        result = ToolResult(output="Tool execution cancelled by user")

                    self.messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(dataclasses.asdict(result)),
                            "tool_call_id": tool_call.id,
                        }
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
            print(user_approval)
            return user_approval
        except KeyboardInterrupt:
            print()
            return "n"

    def _handle_command(self, cmd: str, parts: list[str]) -> bool:
        return self._command_handler.handle_command(cmd, parts)

    def chat(self):
        """
        Interactive mode
        """
        try:
            placeholder_color = "ansigray"

            message_count = 0
            while True:
                # Determine placeholder text based on message count
                if message_count in [0, 1]:
                    placeholder_text = 'Use """ for multi-line prompts'
                elif message_count in []:  # Disabled
                    placeholder_text = "Type /help for advanced commands"
                else:
                    placeholder_text = ""

                # Get first line of input with placeholder
                placeholder = HTML(
                    f"<{placeholder_color}>{placeholder_text}</{placeholder_color}>"
                )
                if self._prompt_session is None:
                    self._prompt_session = PromptSession()
                user_input = self._prompt_session.prompt(
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
                        line = self._prompt_session.prompt(
                            "", placeholder=placeholder
                        ).strip()
                        if line == '"""':
                            break
                        user_input += line + "\n"
                    print()

                message_count += 1  # Increment counter after each message

                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=2)
                    cmd = parts[0].lower()
                    if self._handle_command(cmd, parts):
                        continue

                if user_input == "":
                    if message_count in range(4, 7):
                        print("Error: Cat is asleep on Enter key\n")
                    else:
                        print("Error: No input provided\n")
                    continue

                self.messages.append({"role": "user", "content": user_input})

                for _ in self.respond():
                    pass

                print()
        except KeyboardInterrupt:
            self._spinner.stop()
            print()
            pass
        except Exception as e:
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
