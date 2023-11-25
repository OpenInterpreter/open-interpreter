import os

from .local_storage_path import get_storage_path


def get_conversations():
    conversations_dir = get_storage_path("conversations")
    json_files = [f for f in os.listdir(conversations_dir) if f.endswith(".json")]
    return json_files
