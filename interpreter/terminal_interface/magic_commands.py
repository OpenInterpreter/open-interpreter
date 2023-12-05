import json
import os
import subprocess

from ..core.utils.system_debug_info import system_info
from .utils.count_tokens import count_messages_tokens
from .utils.display_markdown_message import display_markdown_message


def handle_undo(self, arguments):
    # Removes all messages after the most recent user entry (and the entry itself).
    # Therefore user can jump back to the latest point of conversation.
    # Also gives a visual representation of the messages removed.

    if len(self.messages) == 0:
        return
    # Find the index of the last 'role': 'user' entry
    last_user_index = None
    for i, message in enumerate(self.messages):
        if message.get("role") == "user":
            last_user_index = i

    removed_messages = []

    # Remove all messages after the last 'role': 'user'
    if last_user_index is not None:
        removed_messages = self.messages[last_user_index:]
        self.messages = self.messages[:last_user_index]

    print("")  # Aesthetics.

    # Print out a preview of what messages were removed.
    for message in removed_messages:
        if "content" in message and message["content"] != None:
            display_markdown_message(
                f"**Removed message:** `\"{message['content'][:30]}...\"`"
            )
        elif "function_call" in message:
            display_markdown_message(
                f"**Removed codeblock**"
            )  # TODO: Could add preview of code removed here.

    print("")  # Aesthetics.


def handle_help(self, arguments):
    commands_description = {
        "%% [commands]": "Run commands in system shell",
        "%debug [true/false]": "Toggle debug mode. Without arguments or with 'true', it enters debug mode. With 'false', it exits debug mode.",
        "%reset": "Resets the current session.",
        "%undo": "Remove previous messages and its response from the message history.",
        "%save_message [path]": "Saves messages to a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%load_message [path]": "Loads messages from a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%tokens [prompt]": "EXPERIMENTAL: Calculate the tokens used by the next request based on the current conversation's messages and estimate the cost of that request; optionally provide a prompt to also calulate the tokens used by that prompt and the total amount of tokens that will be sent with the next request",
        "%help": "Show this help message.",
        "%info": "Show system and interpreter information",
    }

    base_message = ["> **Available Commands:**\n\n"]

    # Add each command and its description to the message
    for cmd, desc in commands_description.items():
        base_message.append(f"- `{cmd}`: {desc}\n")

    additional_info = [
        "\n\nFor further assistance, please join our community Discord or consider contributing to the project's development."
    ]

    # Combine the base message with the additional info
    full_message = base_message + additional_info

    display_markdown_message("".join(full_message))


def handle_debug(self, arguments=None):
    if arguments == "" or arguments == "true":
        display_markdown_message("> Entered debug mode")
        print("\n\nCurrent messages:\n")
        for message in self.messages:
            print(f"\n{message}\n")
        print("\n")
        self.debug_mode = True
    elif arguments == "false":
        display_markdown_message("> Exited debug mode")
        self.debug_mode = False
    else:
        display_markdown_message("> Unknown argument to debug command.")


def handle_info(self, arguments):
    system_info(self)


def handle_reset(self, arguments):
    self.reset()
    display_markdown_message("> Reset Done")


def default_handle(self, arguments):
    display_markdown_message("> Unknown command")
    handle_help(self, arguments)


def handle_save_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "w") as f:
        json.dump(self.messages, f, indent=2)

    display_markdown_message(f"> messages json export to {os.path.abspath(json_path)}")


def handle_load_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "r") as f:
        self.messages = json.load(f)

    display_markdown_message(
        f"> messages json loaded from {os.path.abspath(json_path)}"
    )


def handle_count_tokens(self, prompt):
    messages = [{"role": "system", "message": self.system_message}] + self.messages

    outputs = []

    if len(self.messages) == 0:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.model
        )
    else:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.model
        )

    outputs.append(
        (
            f"> Tokens sent with next request as context: {conversation_tokens} (Estimated Cost: ${conversation_cost})"
        )
    )

    if prompt:
        (prompt_tokens, prompt_cost) = count_messages_tokens(
            messages=[prompt], model=self.model
        )
        outputs.append(
            f"> Tokens used by this prompt: {prompt_tokens} (Estimated Cost: ${prompt_cost})"
        )

        total_tokens = conversation_tokens + prompt_tokens
        total_cost = conversation_cost + prompt_cost

        outputs.append(
            f"> Total tokens for next request with this prompt: {total_tokens} (Estimated Cost: ${total_cost})"
        )

    outputs.append(
        f"**Note**: This functionality is currently experimental and may not be accurate. Please report any issues you find to the [Open Interpreter GitHub repository](https://github.com/KillianLucas/open-interpreter)."
    )

    display_markdown_message("\n".join(outputs))


def handle_magic_command(self, user_input):
    # Handle shell
    if user_input.startswith("%%"):
        code = user_input[2:].strip()
        for chunk in self.computer.run("shell", code):
            if "output" in chunk:
                print(chunk["output"], flush=True, end="")
        print("")
        return

    # split the command into the command and the arguments, by the first whitespace
    switch = {
        "help": handle_help,
        "debug": handle_debug,
        "reset": handle_reset,
        "save_message": handle_save_message,
        "load_message": handle_load_message,
        "undo": handle_undo,
        "tokens": handle_count_tokens,
        "info": handle_info,
    }

    user_input = user_input[1:].strip()  # Capture the part after the `%`
    command = user_input.split(" ")[0]
    arguments = user_input[len(command) :].strip()
    action = switch.get(
        command, default_handle
    )  # Get the function from the dictionary, or default_handle if not found
    action(self, arguments)  # Execute the function
