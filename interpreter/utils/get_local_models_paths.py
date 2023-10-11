import os

from ..utils.local_storage_path import get_storage_path

def get_local_models_paths():
    models_dir = get_storage_path("models")
    files = [os.path.join(models_dir, f) for f in os.listdir(models_dir)]
    return files