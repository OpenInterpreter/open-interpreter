import os
import shutil
from importlib import resources

import yaml

from .local_storage_path import get_storage_path

config_filename = "config.yaml"

user_config_path = os.path.join(get_storage_path(), config_filename)


def get_config_path(path=user_config_path):
    # check to see if we were given a path that exists
    if not os.path.exists(path):
        # check to see if we were given a filename that exists in the config directory
        if os.path.exists(os.path.join(get_storage_path(), path)):
            path = os.path.join(get_storage_path(), path)
        else:
            # check to see if we were given a filename that exists in the current directory
            if os.path.exists(os.path.join(os.getcwd(), path)):
                path = os.path.join(os.path.curdir, path)
            # if we weren't given a path that exists, we'll create a new file
            else:
                # if the user gave us a path that isn't our default config directory
                # but doesn't already exist, let's create it
                if os.path.dirname(path) and not os.path.exists(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                else:
                    # Ensure the user-specific directory exists
                    os.makedirs(get_storage_path(), exist_ok=True)

                    # otherwise, we'll create the file in our default config directory
                    path = os.path.join(get_storage_path(), path)

                # If user's config doesn't exist, copy the default config from the package
                here = os.path.abspath(os.path.dirname(__file__))
                parent_dir = os.path.dirname(here)
                default_config_path = os.path.join(parent_dir, "config.yaml")

                # Copying the file using shutil.copy
                new_file = shutil.copy(default_config_path, path)

                print("Copied the default config file to the user's directory because the user's config file was not found.")

    return path


def get_config(path=user_config_path):
    path = get_config_path(path)
    
    config = None

    with open(path, "r") as file:
        config = yaml.safe_load(file)
        if config is not None:
            return config

    if config is None:
        # Deleting empty file because get_config_path copies the default if file is missing
        os.remove(path)
        path = get_config_path(path)
        with open(path, "r") as file:
            config = yaml.safe_load(file)
            return config
