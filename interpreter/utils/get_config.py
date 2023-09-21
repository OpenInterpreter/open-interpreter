import os
import yaml
import appdirs
from importlib import resources
import shutil

config_filename = "config.yaml"

# Using appdirs to determine user-specific config path
config_dir = appdirs.user_config_dir("Open Interpreter")
user_config_path = os.path.join(config_dir, config_filename)

def get_config():
    if not os.path.exists(user_config_path):
        # If user's config doesn't exist, copy the default config from the package
        here = os.path.abspath(os.path.dirname(__file__))
        parent_dir = os.path.dirname(here)
        default_config_path = os.path.join(parent_dir, 'config.yaml')
        # Ensure the user-specific directory exists
        os.makedirs(config_dir, exist_ok=True)
        # Copying the file using shutil.copy
        shutil.copy(default_config_path, user_config_path)

    with open(user_config_path, 'r') as file:
        return yaml.safe_load(file)