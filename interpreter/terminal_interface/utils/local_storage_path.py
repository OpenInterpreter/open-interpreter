import os

import platformdirs

# Using platformdirs to determine user-specific config path
config_dir = platformdirs.user_config_dir("open-interpreter")


def get_storage_path(subdirectory=None):
    if subdirectory is None:
        return config_dir
    else:
        return os.path.join(config_dir, subdirectory)
