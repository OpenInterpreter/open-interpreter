"""
This file handles conversations.
"""

import appdirs
import inquirer
import subprocess
import platform
import os
import json
from .render_past_conversation import render_past_conversation
from ..utils.display_markdown_message import display_markdown_message

def conversation_navigator(interpreter):

    data_dir = appdirs.user_data_dir("Open Interpreter")
    conversations_dir = os.path.join(data_dir, "conversations")

    display_markdown_message(f"""> Conversations are stored in "`{conversations_dir}`".
    
    Select a conversation to resume.
    """)

    # Check if conversations directory exists
    if not os.path.exists(conversations_dir):
        print(f"No conversations found in {conversations_dir}")
        return None

    # Get list of all JSON files in the directory
    json_files = [f for f in os.listdir(conversations_dir) if f.endswith('.json')]
    json_files.append("> Open folder")  # Add the option to open the folder

    # Use inquirer to let the user select a file
    questions = [
        inquirer.List('file',
                      message="",
                      choices=json_files,
                      ),
    ]
    answers = inquirer.prompt(questions)

    # If the user selected to open the folder, do so and return
    if answers['file'] == "> Open folder":
        open_folder(conversations_dir)
        return

    # Open the selected file and load the JSON data
    with open(os.path.join(conversations_dir, answers['file']), 'r') as f:
        messages = json.load(f)

    # Pass the data into render_past_conversation
    render_past_conversation(messages)

    # Set the interpreter's settings to the loaded messages
    interpreter.messages = messages
    interpreter.conversation_name = answers['file'].replace(".json", "")

    # Start the chat
    interpreter.chat()

def open_folder(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", path])
    else:
        # Assuming it's Linux
        subprocess.run(["xdg-open", path])