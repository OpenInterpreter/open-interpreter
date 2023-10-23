import os
import yaml
import shutil

def get_config_path(path="config.yaml"):
    if not os.path.exists(path):
        # If the user's config doesn't exist, copy the default config from the package
        here = os.path.abspath(os.path.dirname(__file__))
        parent_dir = os.path.dirname(here)
        default_config_path = os.path.join(parent_dir, 'config.yaml')

        # Copying the file using shutil.copy
        new_file = shutil.copy(default_config_path, path)

    return path

def get_memoria_path(path="memoria.json"):
    if not os.path.exists(path):
        # If the user's memoria data doesn't exist, create an empty JSON file
        with open(path, 'w') as file:
            file.write("{}")

    return path

def get_config_and_memoria(config_path=get_config_path(), memoria_path=get_memoria_path()):
    with open(config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)

    with open(memoria_path, 'r') as memoria_file:
        memoria_data = yaml.safe_load(memoria_file)

    return config, memoria_data
