import os
import yaml
import json
import shutil
import sys

# Agregamos la ruta al directorio que contiene local_storage_path
sys.path.append(r'C:\Users\Ricardo Ruiz\open-interpreter\interpreter\utils')


# Asumiendo que 'local_storage_path' es un módulo en el mismo directorio
from local_storage_path import get_storage_path

config_filename = "config.yaml"
data_filename = "mis_datos.json"

user_config_path = os.path.join(get_storage_path(), config_filename)
user_data_path = os.path.join(get_storage_path(), data_filename)

def get_config_path(path=user_config_path):
    if not os.path.exists(path):
        if os.path.exists(os.path.join(get_storage_path(), path)):
            path = os.path.join(get_storage_path(), path)
        else:
            if os.path.exists(os.path.join(os.getcwd(), path)):
                path = os.path.join(os.path.curdir, path)
            else:
                here = os.path.abspath(os.path.dirname(__file__))
                parent_dir = os.path.dirname(here)
                default_config_path = os.path.join(parent_dir, 'config.yaml')

                new_file = shutil.copy(default_config_path, path)

    return path

def get_data_path(path=user_data_path):
    if not os.path.exists(path):
        if os.path.exists(os.path.join(get_storage_path(), path)):
            path = os.path.join(get_storage_path(), path)
        else:
            if os.path.exists(os.path.join(os.getcwd(), path)):
                path = os.path.join(os.path.curdir, path)
            else:
                here = os.path.abspath(os.path.dirname(__file__))
                parent_dir = os.path.dirname(here)
                default_data_path = os.path.join(parent_dir, 'mis_datos.json')

                new_data_file = shutil.copy(default_data_path, path)

    return path

def get_config(path=user_config_path):
    path = get_config_path(path)

    with open(path, 'r') as file:
        return yaml.safe_load(file)

def get_data(path=user_data_path):
    path = get_data_path(path)

    with open(path, 'r') as file:
        return json.load(file)

# Resto del código
