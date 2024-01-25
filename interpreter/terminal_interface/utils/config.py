import json
import os

import requests
import yaml

from .get_oi_dir import get_oi_dir

config_dir = os.path.join(get_oi_dir() + "configs")


def get_config(filename_or_url):
    # i.com/ is a shortcut for openinterpreter.com/profiles/
    shortcuts = ["i.com/", "www.i.com/", "https://i.com/", "http://i.com/"]
    for shortcut in shortcuts:
        if filename_or_url.startswith(shortcut):
            filename_or_url = filename_or_url.replace(
                shortcut, "openinterpreter.com/profiles/"
            )
            break

    config_path = os.path.join(config_dir, filename_or_url)
    if os.path.exists(config_path):
        with open(config_path, "r") as file:
            try:
                return yaml.safe_load(file)
            except:
                return json.load(file)
    else:
        response = requests.get(filename_or_url)
        response.raise_for_status()
        try:
            return yaml.safe_load(response.text)
        except:
            return json.loads(response.text)
