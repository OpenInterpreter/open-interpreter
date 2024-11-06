import importlib.util
import os
import sys

import platformdirs

from .main import run_async_main
from .misc.help import help_message
from .misc.welcome import welcome_message


def main():
    oi_dir = platformdirs.user_config_dir("open-interpreter")
    profiles_dir = os.path.join(oi_dir, "profiles")

    # Get profile path from command line args
    profile = None
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
            break

    if profile:
        if not os.path.isfile(profile):
            profile = os.path.join(profiles_dir, profile)
            if not os.path.isfile(profile):
                profile += ".py"
                if not os.path.isfile(profile):
                    print(f"Invalid profile path: {profile}")
                    exit(1)

        # Load the profile module from the provided path
        spec = importlib.util.spec_from_file_location("profile", profile)
        profile_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(profile_module)

        # Get the interpreter from the profile
        interpreter = profile_module.interpreter

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        help_message()
    else:
        welcome_message()
        run_async_main()
