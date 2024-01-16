import os
import shutil

import yaml

from .local_storage_path import get_storage_path

profile_filename = "profiles.yaml"
user_profile_path = os.path.join(get_storage_path(), profile_filename)

def get_profile_path(path=user_profile_path):
    # check to see if we were given a path that exists
    if not os.path.exists(path):
        # check to see if we were given a filename that exists in the profile directory
        if os.path.exists(os.path.join(get_storage_path(), path)):
            path = os.path.join(get_storage_path(), path)
        else:
            # check to see if we were given a filename that exists in the current directory
            if os.path.exists(os.path.join(os.getcwd(), path)):
                path = os.path.join(os.path.curdir, path)
            # if we weren't given a path that exists, we'll create a new file
            else:
                # if the user gave us a path that isn't our default profile directory
                # but doesn't already exist, let's create it
                if os.path.dirname(path) and not os.path.exists(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                else:
                    # Ensure the user-specific directory exists
                    os.makedirs(get_storage_path(), exist_ok=True)

                    # otherwise, we'll create the file in our default profile directory
                    path = os.path.join(get_storage_path(), path)

                # If user's profile doesn't exist, copy the default profile from the package
                here = os.path.abspath(os.path.dirname(__file__))
                parent_dir = os.path.dirname(here)
                default_profile_path = os.path.join(parent_dir, profile_filename)

                # Copying the file using shutil.copy
                new_file = shutil.copy(default_profile_path, path)

    return path

def get_profile(path=user_profile_path):
    path = get_profile_path(path)

    profile = None

    try:
        with open(path, "r", encoding='utf-8') as file:
            profile = yaml.safe_load(file)
            if profile is not None:
                return profile
    except UnicodeDecodeError:
        print("")
        print(
            "WARNING: Profile file can't be read due to a Unicode decoding error. Ensure it is saved in UTF-8 format. Run `interpreter --reset_profile` to reset it."
        )
        print("")
        return {}
    except Exception as e:
        print("")
        print(
            f"WARNING: An error occurred while reading the profile file: {e}."
        )
        print("")
        return {}

    if profile is None:
        # Deleting empty file because get_profile_path copies the default if file is missing
        os.remove(path)
        path = user_profile_path(path)
        with open(path, "r", encoding="utf-8") as file:
            profile = yaml.safe_load(file)
            return profile

def apply_profile(self, profile_path=None):
    if profile_path == None:
        profile_path = get_profile_path

    if self.verbose:
        print(f"Extending profileuration from `{profile_path}`")

    profile = get_profile(profile_path)
    