import logging
import os
import shutil

import yaml

from .local_storage_path import get_storage_path

# Constants for file paths
PROFILE_FILENAME = "profiles.yaml"
USER_PROFILE_PATH = os.path.join(get_storage_path(), PROFILE_FILENAME)


def get_profile_path(path=USER_PROFILE_PATH):
    """
    Retrieve the path to the profile. If the path does not exist, create a new profile.
    :param path: The path or filename for the profile.
    :return: The full path to the profile.
    """
    # Constructing full paths for various locations
    profile_dir = get_storage_path()
    current_dir = os.getcwd()

    # Check if path exists, or if it's in profile or current directory
    if not os.path.exists(path):
        if os.path.exists(os.path.join(profile_dir, path)):
            path = os.path.join(profile_dir, path)
        elif os.path.exists(os.path.join(current_dir, path)):
            path = os.path.join(current_dir, path)
        else:
            # Create directory if it doesn't exist
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            else:
                os.makedirs(profile_dir, exist_ok=True)
                path = os.path.join(profile_dir, path)

            # Copy default profile
            default_profile_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), PROFILE_FILENAME
            )
            shutil.copy(default_profile_path, path)

    return path


def get_profile(path=USER_PROFILE_PATH):
    """
    Load and return the user profile from the given path.
    :param path: The path to the profile file.
    :return: A dictionary containing the profile data.
    """
    path = get_profile_path(path)
    try:
        with open(path, "r", encoding="utf-8") as file:
            profile = yaml.safe_load(file)
            return profile if profile else {}
    except UnicodeDecodeError:
        logging.warning(
            "Profile file can't be read due to a Unicode decoding error. "
            "Ensure it is saved in UTF-8 format. Run `interpreter --reset_profile` to reset it."
        )
    except Exception as e:
        logging.warning(f"An error occurred while reading the profile file: {e}.")
    return {}


def apply_profile(self, profile_path=None):
    """
    Apply the user profile settings from the specified path.
    If profile_path is None, the default path is used.
    The method uses self.profile to access the current profile name.
    :param profile_path: The path to the profile file.
    """
    if profile_path is None:
        profile_path = get_profile_path()

    profile = get_profile(profile_path)

    # Retrieve the specific profile based on the current profile name
    selected_profile = profile.get(self.profile, {})

    # Apply settings from the selected profile
    for key, value in selected_profile.items():
        if key.startswith("llm."):
            setattr(self.llm, key[4:], value)  # For 'llm.' prefixed keys
        elif key.startswith("computer."):
            setattr(self.computer, key[9:], value)  # For 'computer.' prefixed keys
        else:
            setattr(self, key, value)  # For other keys

    return self
