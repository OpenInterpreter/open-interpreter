import os
import appdirs

# Using appdirs to determine user-specific config path
config_dir = appdirs.user_config_dir("Open Interpreter")

def get_local_models_paths():
    models_dir = os.path.join(config_dir, "models")
    files = [os.path.join(models_dir, f) for f in os.listdir(models_dir)]
    return files