import os
import json
import hashlib
import subprocess
from docker import DockerClient
from docker.errors import DockerException
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
