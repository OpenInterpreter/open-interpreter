import docker
import tarfile
import os
import tempfile
import appdirs
from tqdm import tqdm


def download_file_from_container(container_id, file_path_in_container, local_dir):
    # Check if the specified local directory exists
    if not os.path.isdir(local_dir):
        # If not, use a "Downloads" folder in the user's data directory as the default
        local_dir = os.path.join(appdirs.user_data_dir(), "Open Interpreter", "downloads")
        print(f"file is being downloaded to {local_dir}")
        # Create the Downloads directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)
    
    # Create a Docker client
    client = docker.from_env()

    # Get the container
    container = client.containers.get(container_id)

    # Use get_archive to get a file from the container
    stream, stat = container.get_archive(os.path.join("/mnt/data/", file_path_in_container))
    
    # Get the file name from the stat info
    file_name = os.path.basename(stat['name'])
    # Get the size of the file from the stat object for the progress bar
    total_size = stat['size']
    # Initialize the progress bar
    pbar = tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading")

    # Update the progress bar within the loop where chunks are being written
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        for chunk in stream:
            temp_file.write(chunk)
            pbar.update(len(chunk))
            temp_file.flush()
    pbar.close()
    
    # Open the temporary tar file for reading
    with tarfile.open(temp_file.name, 'r') as tar:
        # Extract the file to the local directory
        tar.extractall(path=local_dir)
    
    # Delete the temporary tar file
    os.remove(temp_file.name)

    # Return the path to the extracted file
    return os.path.join(local_dir, file_name)

