"""Short function to upload a file to a docker container via the docker module. yes its hacky, but its easy and I didnt want to over complicate."""
import io
import tarfile
import os
import docker
from tqdm import tqdm

def copy_file_to_container(container_id, local_path, path_in_container, pbar=True):
    # Validate input
    if not os.path.exists(local_path):
        raise ValueError(f"The specified local path {local_path} does not exist.")
    
    # Create a Docker client
    client = docker.APIClient()

    # Get the container
    container = client.containers()[0]

    container_id = container.get("Id")

    # Get the directory path and name in the container
    dir_path_in_container = os.path.dirname(path_in_container)
    name = os.path.basename(path_in_container)

    # Calculate the total size of the content to be uploaded
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(local_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)

    # Create a tarball in memory
    file_data = io.BytesIO()
    with tarfile.open(fileobj=file_data, mode='w') as tar:
        # Check if the local path is a directory or a file
        if os.path.isdir(local_path):
            # Add the entire directory to the tar archive with the specified name
            tar.add(local_path, arcname=name)
        else:
            # Add the local file to the tar archive with the specified file name
            tar.add(local_path, arcname=name)

    # Seek to the beginning of the in-memory tarball
    file_data.seek(0)

    # Create a tqdm progress bar
    with tqdm(total=total_size, unit='B', unit_scale=True, desc='Uploading') as pbar:
        # Define a generator to read the file data in chunks and update the progress bar
        def file_data_with_progress():
            chunk_size = 1024  # Define an appropriate chunk size
            while True:
                chunk = file_data.read(chunk_size)
                if not chunk:
                    break
                pbar.update(len(chunk))
                yield chunk
            file_data.close()

        # Use put_archive to copy the file or directory into the container
        client.put_archive(container=container_id, path=dir_path_in_container, data=file_data_with_progress())
    
    return path_in_container
