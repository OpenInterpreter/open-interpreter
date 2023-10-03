# Standard library imports
import atexit
import hashlib
import json
import os
import re
import select
import shutil
import struct
import subprocess
import threading
import time


# Third-party imports
import docker
from docker import DockerClient
from docker.errors import DockerException
from docker.utils import kwargs_from_env
from docker.tls import TLSConfig
from rich import print as Print


def get_files_hash(*file_paths):
    """Return the SHA256 hash of multiple files."""
    hasher = hashlib.sha256()
    for file_path in file_paths:
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
    return hasher.hexdigest()


def build_docker_images(
    dockerfile_dir = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "dockerfiles")
,
):
    """
    Builds a Docker image for the Open Interpreter runtime container if needed.

    Args:
        dockerfile_dir (str): The directory containing the Dockerfile and requirements.txt files.

    Returns:
        None
    """
    try:
        client = DockerClient.from_env()
    except DockerException:
        Print("[bold red]ERROR[/bold red]: Could not connect to Docker daemon. Is Docker Engine installed and running?")
        Print(
            "\nFor information on Docker installation, visit: https://docs.docker.com/engine/install/ and follow the instructions for your system."
        )
        return

    image_name = "openinterpreter-runtime-container"
    hash_file_path = os.path.join(dockerfile_dir, "hash.json")

    dockerfile_name = "Dockerfile"
    requirements_name = "requirements.txt"
    dockerfile_path = os.path.join(dockerfile_dir, dockerfile_name)
    requirements_path = os.path.join(dockerfile_dir, requirements_name)

    if not os.path.exists(dockerfile_path) or not os.path.exists(requirements_path):
        Print("ERROR: Dockerfile or requirements.txt not found. Did you delete or rename them?")
        raise RuntimeError(
            "No container Dockerfiles or requirements.txt found. Make sure they are in the dockerfiles/ subdir of the module."
        )

    current_hash = get_files_hash(dockerfile_path, requirements_path)

    stored_hashes = {}
    if os.path.exists(hash_file_path):
        with open(hash_file_path, "rb") as f:
            stored_hashes = json.load(f)

    original_hash = stored_hashes.get("original_hash")
    previous_hash = stored_hashes.get("last_hash")

    if current_hash == original_hash:
        images = client.images.list(name=image_name, all=True)
        if not images:
            Print("Downloading default image from Docker Hub, please wait...")
            subprocess.run(["docker", "pull", "unaidedelf/openinterpreter-runtime-container:latest"])
            subprocess.run(["docker", "tag", "unaidedelf/openinterpreter-runtime-container:latest", image_name ],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif current_hash != previous_hash:
        Print("Dockerfile or requirements.txt has changed. Building container...")

        try:
            # Run the subprocess without capturing stdout and stderr
            # This will allow Docker's output to be printed to the console in real-time
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-t",
                    f"{image_name}:latest",
                    dockerfile_dir,
                ],
                check=True,  # This will raise a CalledProcessError if the command returns a non-zero exit code
                text=True,
            )

            # Update the stored current hash
            stored_hashes["last_hash"] = current_hash
            with open(hash_file_path, "w") as f:
                json.dump(stored_hashes, f)

        except subprocess.CalledProcessError:
            # Suppress Docker's error messages and display your own error message
            Print("Docker Build Error: Building Docker image failed. Please review the error message above and resolve the issue.")

        except FileNotFoundError:
            Print("ERROR: The 'docker' command was not found on your system.")
            Print(
                "Please ensure Docker Engine is installed and the 'docker' command is available in your PATH."
            )
            Print(
                "For information on Docker installation, visit: https://docs.docker.com/engine/install/"
            )
            Print("If Docker is installed, try starting a new terminal session.")


class DockerStreamWrapper:
    def __init__(self, exec_id, sock):
        self.exec_id = exec_id
        self._sock = sock
        self._stdout_r, self._stdout_w = os.pipe()
        self._stderr_r, self._stderr_w = os.pipe()
        self.stdout = self.Stream(self, self._stdout_r)
        self.stderr = self.Stream(self, self._stderr_r)

        ## stdin pipe and fd. dosent need a pipe, but its easier and thread safe and less mem intensive than a queue.Queue()
        self._stdin_r, self._stdin_w = os.pipe()  # Pipe for stdin
        self.stdin = os.fdopen(self._stdin_w, 'w')
        self._stdin_buffer = b""  # Buffer for stdin data. more complex = better fr

        ## start recieving thread to watch socket, and send data from stdin pipe.
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
    
    class Stream:
        def __init__(self, parent, read_fd):
            self.parent = parent
            self._read_fd = read_fd
            self._buffer = ""

        def readline(self):
            while '\n' not in self._buffer:
                ready_to_read, _, _ = select.select([self._read_fd], [], [], None)
                if not ready_to_read:
                    return ''
                chunk = os.read(self._read_fd, 1024).decode('utf-8')
                self._buffer += chunk

            newline_pos = self._buffer.find('\n')
            line = self._buffer[:newline_pos]
            self._buffer = self._buffer[newline_pos + 1:]
            return line

    def _listen(self):
        while not self._stop_event.is_set():
            ready_to_read, _, _ = select.select([self._sock, self._stdin_r], [], [], None)
            
            for s in ready_to_read:
                if s == self._sock:
                    raw_data = self._sock.recv(2048)
                    stdout, stderr = self.demux_docker_stream(raw_data)
                    os.write(self._stdout_w, stdout.encode())
                    os.write(self._stderr_w, stderr.encode())
                elif s == self._stdin_r:
                    # Read from the read end of the stdin pipe and add to the buffer
                    data_to_write = os.read(self._stdin_r, 2048).decode('utf-8')
                    
                    # Remove escape characters for quotes but leave other backslashes untouched
                    data_to_write =  re.sub(r'\\([\'"])', r'\1', data_to_write)

                    data_to_write = data_to_write.replace('\\n', '\n')

                    self._stdin_buffer += data_to_write.encode()

                    # Check for newline and send line by line
                    while b'\n' in self._stdin_buffer:
                        newline_pos = self._stdin_buffer.find(b'\n')
                        line = self._stdin_buffer[:newline_pos + 1]  # Include the newline
                        self._stdin_buffer = self._stdin_buffer[newline_pos + 1:]


                        # Send the line to the Docker container
                        self._sock.sendall(line)


    def demux_docker_stream(self, data):
        stdout = ""
        stderr = ""
        offset = 0
        while offset + 8 <= len(data):
            header = data[offset:offset + 8]
            stream_type, length = struct.unpack('>BxxxL', header)
            offset += 8
            chunk = data[offset:offset + length].decode('utf-8')
            offset += length
            if stream_type == 1:
                stdout += chunk
            elif stream_type == 2:
                stderr += chunk

        return stdout, stderr

    def flush(self):
        pass

    def terminate(self):
        self._stop_event.set()
        self._thread.join()
        os.close(self._stdout_r)
        os.close(self._stdout_w)
        os.close(self._stderr_r)
        os.close(self._stderr_w)



class DockerProcWrapper:
    def __init__(self, command, session_path):
        client_kwargs = kwargs_from_env()
        if client_kwargs.get('tls'):
            client_kwargs['tls'] = TLSConfig(**client_kwargs['tls'])
        self.client = docker.APIClient(**client_kwargs)
        self.image_name = "openinterpreter-runtime-container:latest"
        self.session_path = session_path
        self.exec_id = None
        self.exec_socket = None
        atexit.register(atexit_destroy, self)

        os.makedirs(self.session_path, exist_ok=True)


        # Initialize container
        self.init_container()

        self.init_exec_instance(command)
        

        self.wrapper = DockerStreamWrapper(self.exec_id, self.exec_socket)
        self.stdout = self.wrapper.stdout
        self.stderr = self.wrapper.stderr
        self.stdin = self.wrapper.stdin

        self.stdin.write(command + "\n")

    def init_container(self):
        self.container = None
        try:
            containers = self.client.containers(
                filters={"label": f"session_id={os.path.basename(self.session_path)}"}, all=True)
            if containers:
                self.container = containers[0]
                container_id = self.container.get('Id')
                container_info = self.client.inspect_container(container_id)
                if container_info.get('State', {}).get('Running') is False:
                    self.client.start(container=container_id)
                    self.wait_for_container_start(container_id)
            else:
                host_config = self.client.create_host_config(
                    binds={self.session_path: {'bind': '/mnt/data', 'mode': 'rw'}}
                )
                
                self.container = self.client.create_container(
                    image=self.image_name,
                    detach=True,
                    labels={'session_id': os.path.basename(self.session_path)},
                    host_config=host_config,
                    user="docker",
                    stdin_open=True,
                    tty=False
                )

                self.client.start(container=self.container.get('Id'))
                self.wait_for_container_start(self.container.get('Id'))


        except Exception as e:
            print(f"An error occurred: {e}")

    def init_exec_instance(self, command):
        if self.container:
            container_info = self.client.inspect_container(self.container.get('Id'))

            if container_info.get("State").get('Running') is False: # Not sure of the cause of this, but this works for now.
                self.client.start(self.container.get("Id"))

            self.exec_id = self.client.exec_create(
                self.container.get("Id"),
                cmd="/bin/bash",
                stdin=True,
                stdout=True,
                stderr=True,
                workdir="/mnt/data",
                user="docker",
                tty=False

            )['Id']
            # when socket=True, this returns a socketIO socket, so we just kinda hijack the underlying socket
            # since docker sets up the socketio wierd and tries to make it hard to mess with and write to.
            # We make the socket "Cooperative"
            self.exec_socket = self.client.exec_start(
                self.exec_id, socket=True, tty=False, demux=False)._sock 


    def wait_for_container_start(self, container_id, timeout=30):
        start_time = time.time()
        while True:
            container_info = self.client.inspect_container(container_id)
            if container_info.get('State', {}).get('Running') is True:
                return True
            elif time.time() - start_time > timeout:
                raise TimeoutError(
                    "Container did not start within the specified timeout.")
            time.sleep(1)


def atexit_destroy(self):
    shutil.rmtree(self.session_path)
    self.client.stop(self.container.get("Id"))
    self.client.remove_container(self.container.get("Id"))
