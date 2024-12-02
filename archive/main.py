"""
Based on Anthropic's computer use example at https://github.com/anthropics/anthropic-quickstarts/blob/main/computer-use-demo/computer_use_demo/loop.py
"""

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

import pyautogui
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from .misc.desktop import desktop_prompt
from .ui.markdown import MarkdownRenderer

try:
    from enum import StrEnum
except ImportError:  # 3.10 compatibility
    from enum import Enum as StrEnum

from typing import Any, List, cast

from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex
from anthropic.types import ToolResultBlockParam
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

from .tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult
from .ui.tool import ToolRenderer

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

md = MarkdownRenderer()

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

from typing import List, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add these near the top with other global variables
approved_paths = set()  # Store approved file paths
approved_commands = set()  # Store approved bash commands

# Add this near the top of the file, with other imports and global variables # <- this is from anthropic but it sounds so cursor lmao
messages: List[BetaMessageParam] = []


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


# This system prompt is optimized for the Docker environment in this repository and
# specific tool combinations enabled.
# We encourage modifying this system prompt to ensure the model has context for the
# environment it is running in, and to provide any additional information that may be
# helpful for the task at hand.

SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are an AI assistant with access to a machine running on {"Mac OS" if platform.system() == "Darwin" else platform.system()} with internet access.
* When using your computer function calls, they take a while to run and send back to you. Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %d, %Y')}.
* The user's cwd is {os.getcwd()} and username is {os.getlogin()}.
</SYSTEM_CAPABILITY>"""

# Update the SYSTEM_PROMPT for Mac OS
if platform.system() == "Darwin":
    SYSTEM_PROMPT += """
<IMPORTANT>
* Open applications using Spotlight by using the computer tool to simulate pressing Command+Space, typing the application name, and pressing Enter.
</IMPORTANT>"""


async def respond(
    *,
    model: str = "claude-3-5-sonnet-20241022",
    provider: APIProvider,
    messages: list[BetaMessageParam],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    auto_approve: bool = False,
    tools: list[str] = [],
):
    """
    Agentic sampling loop for the assistant/tool interaction of computer use.
    """

    tools = []
    if "interpreter" in tools:
        tools.append(BashTool())
    if "editor" in tools:
        tools.append(EditTool())
    if "gui" in tools:
        tools.append(ComputerTool())

    tool_collection = ToolCollection(*tools)
    system = BetaTextBlockParam(
        type="text",
        text=SYSTEM_PROMPT,
    )

    while True:
        spinner = yaspin(Spinners.simpleDots, text="")
        spinner.start()

        enable_prompt_caching = False
        betas = [COMPUTER_USE_BETA_FLAG]
        image_truncation_threshold = 10
        if provider == APIProvider.ANTHROPIC:
            if api_key:
                client = Anthropic(api_key=api_key)
            else:
                client = Anthropic()
            enable_prompt_caching = True
        elif provider == APIProvider.VERTEX:
            client = AnthropicVertex()
        elif provider == APIProvider.BEDROCK:
            client = AnthropicBedrock()
        else:
            client = Anthropic()

        if enable_prompt_caching:
            betas.append(PROMPT_CACHING_BETA_FLAG)
            # _inject_prompt_caching(messages)
            # Is it ever worth it to bust the cache with prompt caching?
            image_truncation_threshold = 50
            system["cache_control"] = {"type": "ephemeral"}

        if only_n_most_recent_images:
            _maybe_filter_to_n_most_recent_images(
                messages,
                only_n_most_recent_images,
                min_removal_threshold=image_truncation_threshold,
            )

        edit = ToolRenderer()

        # Call the API
        # we use raw_response to provide debug information to streamlit. Your
        # implementation may be able call the SDK directly with:
        # `response = client.messages.create(...)` instead.

        try:
            use_anthropic = (
                litellm.get_model_info(model)["litellm_provider"] == "anthropic"
            )
        except:
            use_anthropic = False

        if use_anthropic:
            # Use Anthropic API which supports betas
            raw_response = client.beta.messages.create(
                max_tokens=max_tokens,
                messages=messages,
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
                if first_token:
                    spinner.stop()
                    first_token = False

                if isinstance(chunk, BetaRawContentBlockStartEvent):
                    current_block = chunk.content_block
                elif isinstance(chunk, BetaRawContentBlockDeltaEvent):
                    if chunk.delta.type == "text_delta":
                        # print(f"{chunk.delta.text}", end="", flush=True)
                        md.feed(chunk.delta.text)
                        yield {"type": "chunk", "chunk": chunk.delta.text}
                        await asyncio.sleep(0)
                        if current_block and current_block.type == "text":
                            current_block.text += chunk.delta.text
                    elif chunk.delta.type == "input_json_delta":
                        # Initialize partial_json if needed
                        if not hasattr(current_block, "partial_json"):
                            current_block.partial_json = ""
                            current_block.parsed_json = {}
                            current_block.current_key = None
                            current_block.current_value = ""

                        # Add new JSON delta
                        current_block.partial_json += chunk.delta.partial_json

                        # print(chunk.delta.partial_json)

                        # If name attribute is present on current_block:
                        if hasattr(current_block, "name"):
                            if edit.name == None:
                                edit.name = current_block.name
                            edit.feed(chunk.delta.partial_json)

                elif isinstance(chunk, BetaRawContentBlockStopEvent):
                    edit.close()
                    edit = ToolRenderer()
                    if current_block:
                        if hasattr(current_block, "partial_json"):
                            # Finished a tool call
                            # print()
                            current_block.input = json.loads(current_block.partial_json)
                            # yield {"type": "chunk", "chunk": current_block.input}
                            delattr(current_block, "partial_json")
                        else:
                            # Finished a message
                            # print("\n")
                            md.feed("\n")
                            yield {"type": "chunk", "chunk": "\n"}
                            await asyncio.sleep(0)
                        # Clean up any remaining attributes from partial processing
                        if current_block:
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
                model=model,
                stop_reason=None,
                stop_sequence=None,
                type="message",
                usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                },  # Add a default usage dictionary
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": cast(list[BetaContentBlockParam], response.content),
                }
            )

            user_approval = None

            if auto_approve:
                user_approval = "y"
            else:
                # If not in terminal, break
                if not sys.stdin.isatty():
                    # Error out
                    print(
                        "Error: You appear to be running in a non-interactive environment, so cannot approve tools. Add the `-y` flag to automatically approve tools in non-interactive environments."
                    )
                    # Exit
                    exit(1)

                content_blocks = cast(list[BetaContentBlock], response.content)
                tool_use_blocks = [b for b in content_blocks if b.type == "tool_use"]
                if len(tool_use_blocks) > 1:
                    print(f"\n\033[38;5;240mRun all actions above\033[0m?")
                    user_approval = input("\n(y/n/a): ").lower().strip()
                elif len(tool_use_blocks) == 1:
                    auto_approved = False
                    if tool_use_blocks[0].name == "str_replace_editor":
                        path = tool_use_blocks[0].input.get("path")
                        if path.startswith(os.getcwd()):
                            path = path[len(os.getcwd()) + 1 :]
                            if path == "":
                                path = "/"

                        # Check if path is already approved
                        if path in approved_paths:
                            user_approval = "y"
                            auto_approved = True
                        else:
                            if tool_use_blocks[0].input.get("command") == "create":
                                print(
                                    f"\n\033[38;5;240mCreate \033[0m{path}\033[38;5;240m?\033[0m"
                                )
                            elif tool_use_blocks[0].input.get("command") == "view":
                                print(
                                    f"\n\033[38;5;240mView \033[0m{path}\033[38;5;240m?\033[0m"
                                )
                            elif tool_use_blocks[0].input.get("command") in [
                                "str_replace",
                                "insert",
                            ]:
                                print(
                                    f"\n\033[38;5;240mEdit \033[0m{path}\033[38;5;240m?\033[0m"
                                )
                    elif tool_use_blocks[0].name == "bash":
                        command = tool_use_blocks[0].input.get("command")
                        # Check if command is already approved
                        if command in approved_commands:
                            user_approval = "y"
                            auto_approved = True
                        else:
                            print(f"\n\033[38;5;240mRun code?\033[0m")
                    else:
                        print(f"\n\033[38;5;240mRun tool?\033[0m")

                    if not auto_approved:
                        user_approval = input("\n(y/n/a): ").lower().strip()

                        # Add to approved list if 'a' was pressed
                        if user_approval == "a":
                            if tool_use_blocks[0].name == "str_replace_editor":
                                approved_paths.add(path)
                                print(
                                    f"\033[38;5;240mAdded {path} to approved paths\033[0m"
                                )
                            elif tool_use_blocks[0].name == "bash":
                                approved_commands.add(command)
                                print(
                                    f"\033[38;5;240mAdded '{command}' to approved commands\033[0m"
                                )
                            user_approval = "y"

            tool_result_content: list[BetaToolResultBlockParam] = []
            for content_block in cast(list[BetaContentBlock], response.content):
                if content_block.type == "tool_use":
                    # Ask user if they want to create the file
                    # path = "/tmp/test_file.txt"
                    # print(f"\n\033[38;5;240m Create \033[0m\033[1m{path}\033[0m?")
                    # response = input(f"\n\033[38;5;240m Create \033[0m\033[1m{path}\033[0m?" + " (y/n): ").lower().strip()
                    # Ask user for confirmation before running tool
                    edit.close()

                    if user_approval == "y":
                        result = await tool_collection.run(
                            name=content_block.name,
                            tool_input=cast(dict[str, Any], content_block.input),
                        )
                    else:
                        result = ToolResult(output="Tool execution cancelled by user")
                    tool_result_content.append(
                        _make_api_tool_result(result, content_block.id)
                    )

            if user_approval == "n":
                messages.append({"content": tool_result_content, "role": "user"})
                yield {"type": "messages", "messages": messages}
                break

            if not tool_result_content:
                # Done!
                yield {"type": "messages", "messages": messages}
                break

            if use_anthropic:
                messages.append({"content": tool_result_content, "role": "user"})
            else:
                messages.append({"content": tool_result_content, "role": "tool"})

        else:
            # Use Litellm
            tools = [
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
                },
                {
                    "type": "function",
                    "function": {
                        "name": "str_replace_editor",
                        "description": """Custom editing tool for viewing, creating and editing files\n
                            * If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep\n
                            * The `create` command cannot be used if the specified `path` already exists as a file\n
                            * If a `command` generates a long output, it will be truncated and marked with `<response clipped>` \n
                            * The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!\n
                            * If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique\n
                            * The `new_str` parameter should contain the edited lines that should replace the `old_str`""",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.",
                                    "enum": [
                                        "view",
                                        "create",
                                        "str_replace",
                                        "insert",
                                        "undo_edit",
                                    ],
                                    "type": "string",
                                },
                                "file_text": {
                                    "description": "Required parameter of `create` command, with the content of the file to be created.",
                                    "type": "string",
                                },
                                "insert_line": {
                                    "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                                    "type": "integer",
                                },
                                "new_str": {
                                    "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                                    "type": "string",
                                },
                                "old_str": {
                                    "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                                    "type": "string",
                                },
                                "path": {
                                    "description": "Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.",
                                    "type": "string",
                                },
                                "view_range": {
                                    "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                            },
                            "required": ["command", "path"],
                        },
                    },
                },
            ]

            tools = tools[:1]

            if model.startswith("ollama/"):
                stream = False
                # Ollama doesn't support tool calling + streaming
                # Also litellm doesnt.. work?
                actual_model = model.replace("ollama/", "openai/")
                api_base = "http://localhost:11434/v1/"
            else:
                stream = True
                api_base = None
                actual_model = model

            params = {
                "model": actual_model,
                "messages": [{"role": "system", "content": system["text"]}] + messages,
                # "tools": tools,
                "stream": stream,
                # "max_tokens": max_tokens,
                "api_base": api_base,
                # "drop_params": True,
                "temperature": 0.0,
            }

            raw_response = litellm.completion(**params)
            print(raw_response)

            if not stream:
                # Simulate streaming
                raw_response.choices[0].delta = raw_response.choices[0].message
                raw_response = [raw_response]

            message = None
            first_token = True

            for chunk in raw_response:
                if first_token:
                    spinner.stop()
                    first_token = False

                if message == None:
                    message = chunk.choices[0].delta

                if chunk.choices[0].delta.content:
                    md.feed(chunk.choices[0].delta.content)
                    yield {"type": "chunk", "chunk": chunk.choices[0].delta.content}
                    await asyncio.sleep(0)

                    # If the delta == message, we're on the first block, so this content is already in there
                    if chunk.choices[0].delta != message:
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
                        tool_name = chunk.choices[0].delta.tool_calls[0].function.name
                        if edit.name == None:
                            edit.name = tool_name
                        if current_tool_call.function.name == None:
                            current_tool_call.function.name = tool_name
                    if chunk.choices[0].delta.tool_calls[0].function.arguments:
                        arguments_delta = (
                            chunk.choices[0].delta.tool_calls[0].function.arguments
                        )
                        edit.feed(arguments_delta)

                        # If the delta == message, we're on the first block, so this arguments_delta is already in there
                        if chunk.choices[0].delta != message:
                            current_tool_call.function.arguments += arguments_delta

                if chunk.choices[0].finish_reason:
                    edit.close()
                    edit = ToolRenderer()

            messages.append(message)

            print()

            if not message.tool_calls:
                yield {"type": "messages", "messages": messages}
                break

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

                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(dataclasses.asdict(result)),
                        "tool_call_id": tool_call.id,
                    }
                )


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int = 5,
):
    """
    With the assumption that images are screenshots that are of diminishing value as
    the conversation progresses, remove all but the final `images_to_keep` tool_result
    images in place, with a chunk of min_removal_threshold to reduce the amount we
    break the implicit prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[ToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    # for better cache behavior, we want to remove in chunks
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _response_to_params(
    response: BetaMessage,
) -> list[BetaTextBlockParam | BetaToolUseBlockParam]:
    res: list[BetaTextBlockParam | BetaToolUseBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            res.append({"type": "text", "text": block.text})
        else:
            res.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return res


def _inject_prompt_caching(
    messages: list[BetaMessageParam],
):
    """
    Set cache breakpoints for the 3 most recent turns
    one cache breakpoint is left for tools/system prompt, to be shared across sessions
    """

    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(
            content := message["content"], list
        ):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                content[-1]["cache_control"] = BetaCacheControlEphemeralParam(
                    {"type": "ephemeral"}
                )
            else:
                content[-1].pop("cache_control", None)
                # we'll only every have one extra turn per loop
                break


def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {
                    "type": "text",
                    "text": _maybe_prepend_system_tool_result(result, result.output),
                }
            )
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


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text


async def async_main(args):
    messages = []
    global exit_flag

    # Start the mouse position checking thread
    mouse_thread = threading.Thread(target=check_mouse_position)
    mouse_thread.daemon = True
    mouse_thread.start()

    while not exit_flag:
        # If is atty, get input from user
        placeholder_color = "ansiblack"
        placeholder_color = "ansigray"

        if args["input_message"]:
            user_input = args["input_message"]
            args["input_message"] = None
        elif sys.stdin.isatty():
            placeholder = HTML(
                f'<{placeholder_color}>Use """ for multi-line prompts</{placeholder_color}>'
            )
            # placeholder = HTML('<ansiblack>  Send a message (/? for help)</ansiblack>')
            session = PromptSession()
            # Initialize empty message for multi-line input
            user_input = ""
            if len(messages) < 3:
                first_line = await session.prompt_async("> ", placeholder=placeholder)
            else:
                first_line = input("> ")

            # Check if starting multi-line input
            if first_line.strip() == '"""':
                while True:
                    placeholder = HTML(
                        f'<{placeholder_color}>Use """ again to finish</{placeholder_color}>'
                    )
                    line = await session.prompt_async("", placeholder=placeholder)
                    if line.strip().endswith('"""'):
                        break
                    user_input += line + "\n"
            else:
                user_input = first_line
            print()
        else:
            # Read from stdin when not in terminal
            user_input = sys.stdin.read().strip()

        if user_input.lower() in ["exit", "quit", "q"]:
            break
        elif user_input.lower() in ["d"]:
            desktop_prompt()
            continue

        messages.append(
            {"role": "user", "content": [{"type": "text", "text": user_input}]}
        )

        try:
            async for chunk in respond(
                model=args["model"],
                provider=args.get("provider"),
                messages=messages,
                api_key=args["api_key"],
                auto_approve=args["auto_run"],
            ):
                if chunk["type"] == "messages":
                    messages = chunk["messages"]
        except asyncio.CancelledError:  # So weird but this happens on the first ctrl C
            continue
        except KeyboardInterrupt:  # Then this happens on all subsequent ctrl Cs?
            continue

        # If not in terminal, break
        if not sys.stdin.isatty():
            break

        print()

    # The thread will automatically terminate when the main program exits


def run(args):
    if "--server" in sys.argv:
        # Start uvicorn server directly without asyncio.run()
        app = asyncio.run(async_main(args))
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        try:
            asyncio.run(async_main(args))
        except KeyboardInterrupt:
            print()
            pass


# Replace the global variables and functions related to mouse tracking
exit_flag = False


def check_mouse_position():
    global exit_flag
    corner_threshold = 10
    screen_width, screen_height = pyautogui.size()

    while not exit_flag:
        x, y = pyautogui.position()
        if (
            (x <= corner_threshold and y <= corner_threshold)
            or (x <= corner_threshold and y >= screen_height - corner_threshold)
            or (x >= screen_width - corner_threshold and y <= corner_threshold)
            or (
                x >= screen_width - corner_threshold
                and y >= screen_height - corner_threshold
            )
        ):
            exit_flag = True
            print("\nMouse moved to corner. Exiting...")
            os._exit(0)
        threading.Event().wait(0.1)  # Check every 100ms


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    stream: Optional[bool] = False
