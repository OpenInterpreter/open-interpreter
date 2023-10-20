import appdirs
import shutil
import atexit
import os
import re

import docker
from docker.tls import TLSConfig
from docker.utils import kwargs_from_env


def destroy(): # this fn is called when the entire program exits. registered with atexit in the __init__.py
    # Prepare the Docker client
    client_kwargs = kwargs_from_env()
    if client_kwargs.get('tls'):
        client_kwargs['tls'] = TLSConfig(**client_kwargs['tls'])
    client = docker.APIClient(**client_kwargs)

    # Get all containers
    all_containers = client.containers(all=True)

    # Filter containers based on the label
    for container in all_containers:
        labels = container['Labels']
        if labels:
            session_id = labels.get('session_id')
            if session_id and re.match(r'^ses-', session_id):
                # Stop the container if it's running
                if container['State'] == 'running':
                    client.stop(container=container['Id'])
                # Remove the container
                client.remove_container(container=container['Id'])
                session_path = os.path.join(appdirs.user_data_dir("Open Interpreter"), "sessions", session_id)
                if os.path.exists(session_path):
                    shutil.rmtree(session_path)

atexit.register(destroy)

