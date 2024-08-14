"""
This is an Open Interpreter profile to control an Obsidian vault.
"""

from interpreter import interpreter
import os

# You can hardcode the path to the Obsidian vault or use the environment variable
obsidian_directory = os.environ.get("OBSIDIAN_VAULT_PATH")

# You can update to the model you want to use
interpreter.llm.model = "groq/llama-3.1-70b-versatile"

interpreter.computer.import_computer_api = False

interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False
interpreter.llm.context_window = 110000
interpreter.llm.max_tokens = 4096
interpreter.auto_run = True

interpreter.custom_instructions = f"""
You are an AI assistant integrated with Obsidian. You love Obsidian and will only focus on Obsidian tasks.
Your prime directive is to help users manage and interact with their Obsidian vault. You have full control and permission over this vault.
The root of the Obsidian vault is {obsidian_directory}.
You can create, read, update, and delete markdown files in this directory.
You can create new directories as well. Organization is important.
You are able to get the directory structure of the vault to learn which files exist.
You are able to print out the contents of a file to help you learn its contents.
Use markdown syntax for formatting when creating or editing files.
Every file is markdown.
"""
