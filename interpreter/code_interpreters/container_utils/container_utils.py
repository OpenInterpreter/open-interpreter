"""wrapper classes of the Docker python sdk which allows interaction like its a subprocess object."""
import os
import re
import select
import struct
import threading
import time


# Third-party imports       
import appdirs
import docker
from docker.utils import kwargs_from_env
from docker.tls import TLSConfig
from rich import print as Print

# Modules
from .auto_remove import access_aware

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


# The `@access_aware` decorator enables automatic container cleanup based on activity monitoring.
# It functions under the following conditions:
# 1. The container is subject to removal when it remains unaccessed beyond the duration specified by `auto_remove_timeout`.
# 2. This feature necessitates a non-None argument; absence of a valid argument renders this functionality inactive.
# 3. During interactive sessions, the auto-removal feature is disabled to prevent unintended interruptions.
# 4. The "INTERPRETER_CONTAINER_TIMEOUT" environment variable allows customization of the timeout period. 
#    It accepts an integer value representing the desired timeout in seconds.
# 5. In the event of an unexpected program termination, the container is still ensured to be removed,
#    courtesy of the integration with the `atexit` module, safeguarding system resources from being unnecessarily occupied.
@access_aware 
class DockerProcWrapper:
    def __init__(self, command, session_id, auto_remove_timeout=None, close_callback=None, mount=False): ## Mounting isnt implemented in main code, but i did it here prior so we just hide it behind a flag for now.
        
        # Docker stuff
        client_kwargs = kwargs_from_env()
        if client_kwargs.get('tls'):
            client_kwargs['tls'] = TLSConfig(**client_kwargs['tls'])
        self.client = docker.APIClient(**client_kwargs)
        self.image_name = "openinterpreter-runtime-container:latest"
        self.exec_id = None
        self.exec_socket = None

        # close callback
        self.close_callback = close_callback

        # session info
        self.session_id = session_id
        self.session_path = os.path.join(appdirs.user_data_dir("Open Interpreter"), "sessions", session_id)
        self.mount = mount


        # Initialize container
        self.init_container()

        self.init_exec_instance()
        

        self.wrapper = DockerStreamWrapper(self.exec_id, self.exec_socket)
        self.stdout = self.wrapper.stdout
        self.stderr = self.wrapper.stderr
        self.stdin = self.wrapper.stdin

        self.stdin.write(command + "\n")

    def init_container(self):
        self.container = None
        try:
            containers = self.client.containers(
                filters={"label": f"session_id={self.session_id}"}, all=True)
            if containers:
                self.container = containers[0]
                container_id = self.container.get('Id')
                container_info = self.client.inspect_container(container_id)
                if container_info.get('State', {}).get('Running') is False:
                    self.client.start(container=container_id)
                    self.wait_for_container_start(container_id)
            else:
                if self.mount:

                    os.makedirs(self.session_path, exist_ok=True)

                    host_config = self.client.create_host_config(
                        binds={self.session_path: {'bind': '/mnt/data', 'mode': 'rw'}}
                    )
                else:
                    host_config = None
                
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

    def init_exec_instance(self):
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
                self.exec_id, socket=True, tty=False, demux=False)._sock  # type: ignore


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
    
    def terminate(self):
        self.wrapper.terminate()
        self.client.stop(self.container.get("Id"))
        self.client.remove_container(self.container.get("Id"))

    def stop(self):
        self.wrapper.terminate()
        self.client.stop(self.container.get("Id"), 30)


    def __del__(self):
        self.terminate()





