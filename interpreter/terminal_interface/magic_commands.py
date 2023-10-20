import json
import os
import appdirs
import docker

from ..utils.display_markdown_message import display_markdown_message
from ..utils.count_tokens import count_messages_tokens
from ..utils.display_markdown_message import display_markdown_message
from ..code_interpreters.container_utils.download_file import download_file_from_container
from ..code_interpreters.container_utils.upload_file import copy_file_to_container

from rich import print as Print


def handle_undo(self, arguments):
    # Removes all messages after the most recent user entry (and the entry itself).
    # Therefore user can jump back to the latest point of conversation.
    # Also gives a visual representation of the messages removed.

    if len(self.messages) == 0:
        return
    # Find the index of the last 'role': 'user' entry
    last_user_index = None
    for i, message in enumerate(self.messages):
        if message.get('role') == 'user':
            last_user_index = i

    removed_messages = []

    # Remove all messages after the last 'role': 'user'
    if last_user_index is not None:
        removed_messages = self.messages[last_user_index:]
        self.messages = self.messages[:last_user_index]

    print("")  # Aesthetics.

    # Print out a preview of what messages were removed.
    for message in removed_messages:
        if 'content' in message and message['content'] != None:
            display_markdown_message(
                f"**Removed message:** `\"{message['content'][:30]}...\"`")
        elif 'function_call' in message:
            # TODO: Could add preview of code removed here.
            display_markdown_message(f"**Removed codeblock**")

    print("")  # Aesthetics.


def handle_help(self, arguments):
    commands_description = {
        "%debug [true/false]": "Toggle debug mode. Without arguments or with 'true', it enters debug mode. With 'false', it exits debug mode.",
        "%reset": "Resets the current session.",
        "%undo": "Remove previous messages and its response from the message history.",
        "%save_message [path]": "Saves messages to a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%load_message [path]": "Loads messages from a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
        "%tokens [prompt]": "Calculate the tokens used by the current conversation's messages and estimate their cost and optionally calculate the tokens and estimated cost of a `prompt` if one is provided.",
        "%help": "Show this help message.",
        "%upload": "open a File Dialog, and select a file to upload to the container. only used when using containerized code execution",
        "%upload folder": "same as upload command, except you can upload a folder instead of just a file.",
        "%upload file": "same as upload command, except you can upload a file.",
        "%download" : "Download a file or directory given the file or folder name in the container."
    }

    base_message = [
        "> **Available Commands:**\n\n"
    ]

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
        print(self.messages)
        self.debug_mode = True
    elif arguments == "false":
        display_markdown_message("> Exited debug mode")
        self.debug_mode = False
    else:
        display_markdown_message("> Unknown argument to debug command.")


def handle_reset(self, arguments):
    self.reset()
    display_markdown_message("> Reset Done")


def default_handle(self, arguments):
    display_markdown_message("> Unknown command")
    handle_help(self,arguments)

def handle_save_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, 'w') as f:
        json.dump(self.messages, f, indent=2)

    display_markdown_message(
        f"> messages json export to {os.path.abspath(json_path)}")


def handle_load_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, 'r') as f:
        self.messages = json.load(f)

    display_markdown_message(
        f"> messages json loaded from {os.path.abspath(json_path)}")

def handle_container_upload(self,type=None, *args):
    def is_gui_available():
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication([])
            del app
            return True
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return False
        
    args = list(args)
    if self.use_containers:
        try:
            client = docker.APIClient()
        except:
            error_message = (
                "We were not able to connect to the Docker Container daemon. "
                "Please ensure Docker is installed and running. If you have not run any code yet, "
                "you will need to in order to start a container."
            )
            display_markdown_message(f"{error_message}")
            return
        if len(args) == 0:
            if is_gui_available():
                try:
                    from .components.file_dialog import FileDialog

                    fd = FileDialog()
                    if type is not None:
                        path = fd.get_path(type=type)
                    else:
                        path = fd.get_path(type=None)
                    if path is not None: # if none, they exited
                        
                        args.append(path)
                    else: # We shall now exit on them out of spite
                        return
                except ImportError as e:
                    Print(f"Internal import error {e}")
                    return 
            else:
                Print(f"No GUI available for your system.\n please provide a filepath manually. use the command %upload <filetype (file or folder)> <path>")
                return
                 
        for filepath in args:
            if os.path.exists(filepath):
                session_id = self.session_id
                if session_id is None:
                    Print("[BOLD] [RED] No session found. Please run any code to start one. [/RED] [/BOLD]")
                    return
                containers = client.containers(filters={"label": f"session_id={session_id}"})
                if containers:
                    container_id = containers[0]['Id']
                    # /mnt/data is default workdir for container
                    copy_file_to_container(
                        container_id=container_id, local_path=filepath, path_in_container=f"/mnt/data/{os.path.basename(filepath)}"
                    )
                    success_message = f"[{filepath}](#) successfully uploaded to container in dir `/mnt/data`."
                    display_markdown_message(success_message)
                else:
                    no_container_message = (
                        "No container found to upload to. Please run any code to start one. "
                        "This will be fixed in a later update."
                    )
                    display_markdown_message(f"**'{no_container_message}'**")
            else:
                file_not_found_message = f"File `{filepath}` does not exist."
                display_markdown_message(file_not_found_message)
    else:
        ignore_command_message = "File uploads are only used when using containerized code execution. Ignoring command."
        display_markdown_message(f"**{ignore_command_message}**")
        
def handle_container_download(self, *args):
    if self.use_containers:
        try:
            client = docker.APIClient()
        except Exception as e:
            print("[BOLD][RED]Unable to connect to the Docker Container daemon. Please ensure Docker is installed and running. ignoring command[/RED][/BOLD]")
            return
        
        session_id = self.session_id
        if session_id is None:
            print("No session found. Please run any code to start one.")
            return

        containers = client.containers(filters={"label": f"session_id={session_id}"})
        if not containers:
            print("No container found to download from. Please run any code to start one.")
            return
        
        container_id = containers[0]['Id']

        # Define the local directory where the files will be downloaded.
        # Using 'Open Interpreter' as the appname and no author.
        local_dir = appdirs.user_data_dir(appname="Open Interpreter")

        for file_path_in_container in args:

            if not file_path_in_container.startswith("/mnt/data"):
                file_path_in_container = os.path.join("/mnt/data", file_path_in_container)

            # Construct the local file path
            local_file_path = os.path.join(local_dir, os.path.basename(file_path_in_container))
            
            # Attempt to download the file and handle exceptions
            try:
                download_file_from_container(container_id, file_path_in_container, local_file_path)
                print(f"File downloaded to {local_file_path}")
            except docker.errors.NotFound:
                print(f"File {file_path_in_container} not found in the container.")
    else:
        print("File downloads are only used when using containerized code execution. Ignoring command.")


def handle_count_tokens(self, prompt):
    messages = [{"role": "system", "message": self.system_message}] + self.messages

    outputs = []

    if len(self.messages) == 0:
      (tokens, cost) = count_messages_tokens(messages=messages, model=self.model)
      outputs.append((f"> System Prompt Tokens: {tokens} (${cost})"))
    else:
      (tokens, cost) = count_messages_tokens(messages=messages, model=self.model)
      outputs.append(f"> Conversation Tokens: {tokens} (${cost})")

    if prompt and prompt != '':
      (tokens, cost) = count_messages_tokens(messages=[prompt], model=self.model)
      outputs.append(f"> Prompt Tokens: {tokens} (${cost})") 

    display_markdown_message("\n".join(outputs))


def handle_magic_command(self, user_input):
    # split the command into the command and the arguments, by the first whitespace
    switch = {
        "help": handle_help,
        "debug": handle_debug,
        "reset": handle_reset,
        "save_message": handle_save_message,
        "load_message": handle_load_message,
        "tokens": handle_count_tokens,
        "undo": handle_undo,
        "upload": handle_container_upload,
        "download": handle_container_download,
    }

    user_input = user_input[1:].strip()  # Capture the part after the `%`
    command = user_input.split(" ")[0]
    arguments = user_input[len(command):].strip()
    action = switch.get(command, default_handle)  # Get the function from the dictionary, or default_handle if not found
    action(self, arguments) # Execute the function.
