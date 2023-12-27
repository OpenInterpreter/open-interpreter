import time

import yaml

from .display_markdown_message import display_markdown_message
from .get_config import get_config, user_config_path


def apply_config(self, config_path=None):
    if config_path == None:
        config_path = user_config_path

    if self.debug_mode:
        print(f"Extending configuration from `{config_path}`")

    config = get_config(config_path)

    if "version" not in config or config["version"] != "0.2.0":
        print("")
        print(
            "We have update our configuration file format. Would you like to migrate your configuration file to the new format? No data will be lost."
        )
        print("")
        message = input("(y/n): ")
        print("")
        if message.lower() == "y":
            print("Migrating...")

            # Mapping old attribute names to new ones
            attribute_mapping = {
                "model": "llm.model",
                "temperature": "llm.temperature",
                "llm_supports_vision": "llm.supports_vision",
                "function_calling_llm": "llm.supports_functions",
                "context_window": "llm.context_window",
                "max_tokens": "llm.max_tokens",
                "api_base": "llm.api_base",
                "api_key": "llm.api_key",
                "api_version": "llm.api_version",
                "max_budget": "llm.max_budget",
                "local": "offline",
            }

            # Update attribute names in the config
            for old_attribute, new_attribute in attribute_mapping.items():
                if old_attribute in config:
                    config[new_attribute] = config[old_attribute]
                    del config[old_attribute]

            old_system_messages = [""]
            if (
                "system_message" in config
                and config["system_message"] in old_system_messages
            ):
                # Deleting this will use the default message
                del config["system_message"]

            # Save config file
            with open(config_path, "w") as file:
                yaml.dump(config, file)

            # Wrap it in comments and the version at the bottom
            comment_wrapper = """
### OPEN INTERPRETER CONFIGURATION FILE

{old_config}

# Be sure to remove the "#" before the following settings to use them.

# custom_instructions: ""  # This will be appended to the system message
# auto_run: False  # If True, code will run without asking for confirmation
# safe_mode: "off"  # The safety mode for the LLM — one of "off", "ask", "auto"
# offline: False  # If True, will disable some online features like checking for updates
# debug_mode: False  # If True, will print detailed logs

# llm.api_key: ...  # Your API key, if the API requires it
# llm.api_base: ...  # The URL where an OpenAI-compatible server is running to handle LLM API requests
# llm.api_version: ...  # The version of the API (this is primarily for Azure)
# llm.max_output: 2500  # The maximum characters of code output visible to the LLM

# All options: https://docs.openinterpreter.com/usage/terminal/config

version: 0.2.0 # Configuration file version (do not modify)
                """.strip()

            # Read the current config file
            with open(config_path, "r") as file:
                old_config = file.read()

            # Replace {old_config} in comment_wrapper with the current config
            comment_wrapper = comment_wrapper.format(old_config=old_config)

            # Write the commented config to the file
            with open(config_path, "w") as file:
                file.write(comment_wrapper)

            print("Migration complete.")
            print("")
        else:
            print("Skipping loading config...")
            print("")
            return self

    if "system_message" in config:
        display_markdown_message(
            "\n\n> FYI: A `system_message` was found in your configuration file.\n\nBecause we frequently improve our default system message, we highly reccommend removing this parameter (which manually overrides our default system message).\n\nInstead, run `interpreter --config` to edit your configuration file, then un-comment out the optional 'custom_instructions: "
            "' parameter (by removing the `#` that preceeds it) and use it to append unique instructions to the base system message.\n\n"
        )
        time.sleep(4)

    if "computer.languages" in config:
        # this is handled specially
        self.computer.languages = [
            i
            for i in self.computer.languages
            if i.name.lower() in [l.lower() for l in config["computer.languages"]]
        ]
        del config["computer.languages"]

    for key, value in config.items():
        if key.startswith("llm."):
            setattr(self.llm, key[4:], value)
        elif key.startswith("computer."):
            setattr(self.computer, key[9:], value)
        else:
            setattr(self, key, value)

    return self
