import os
import yaml
import shutil

from .local_storage_path import get_storage_path

config_filename = "config.yaml"

user_config_path = os.path.join(get_storage_path(), config_filename)

def get_config_path(path=user_config_path):
    # Verificar si se proporcionó una ruta que existe
    if not os.path.exists(path):
        # Verificar si se proporcionó un nombre de archivo que existe en el directorio de configuración
        if os.path.exists(os.path.join(get_storage_path(), path)):
            path = os.path.join(get_storage_path(), path)
        else:
            # Verificar si se proporcionó un nombre de archivo que existe en el directorio actual
            if os.path.exists(os.path.join(os.getcwd(), path)):
                path = os.path.join(os.path.curdir, path)
            # Si no se proporcionó una ruta que existe, crearemos un nuevo archivo
            else:
                # Si el usuario proporcionó una ruta que no es nuestro directorio de configuración predeterminado
                # pero aún no existe, la crearemos
                if os.path.dirname(path) and not os.path.exists(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                else:
                    # Asegurémonos de que exista el directorio específico del usuario
                    os.makedirs(get_storage_path(), exist_ok=True)

                    # En caso contrario, crearemos el archivo en nuestro directorio de configuración predeterminado
                    path = os.path.join(get_storage_path(), path)

                # Si la configuración del usuario no existe, copiaremos la configuración predeterminada desde el paquete
                here = os.path.abspath(os.path.dirname(__file__))
                parent_dir = os.path.dirname(here)
                default_config_path = os.path.join(parent_dir, 'config.yaml')

                # Copiamos el archivo utilizando shutil.copy
                new_file = shutil.copy(default_config_path, path)

    return path

def get_config(path=user_config_path):
    path = get_config_path(path)

    with open(path, 'r') as file:
        return yaml.safe_load(file)
