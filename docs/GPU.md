# Local Language Models with GPU Support

Open Interpreter can be used with local language models, however these can be
rather taxing on your computer's resources. If you have an NVIDIA GPU, you may
benefit from offloading some of the work to your GPU.

## Windows

1.  Install the latest [NVIDIA CUDA
    Toolkit](https://developer.nvidia.com/cuda-downloads) for your version of
    Windows. The newest version that is known to work is CUDA Toolkit 12.2.2
    while the oldest version that is known to work is 11.7.1. Other versions may
    work, but not all have been tested.

    For Installer Type, choose **exe (network)**.

    During install, choose **Custom (Advanced)**.

    The only required components are:

    - CUDA
      - Runtime
      - Development
      - Integration with Visual Studio
    - Driver components
      - Display Driver

    You may choose to install additional components if you like.

2.  Once the CUDA Toolkit has finished installing, open **x64 Native Tools Command
    Prompt for VS 2022**, and run the following command. This ensures that the
    `CUDA_PATH` environment varilable is set.

    ```
    echo %CUDA_PATH%
    ```

    If you don't get back something like this:

    ```
    C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2
    ```

    Restart your computer, then repeat this step.

4.  Once you have verified that the `CUDA_PATH` environment variable is set, run
    the following commands. This will reinstall the `llama-cpp-python` package
    with NVIDIA GPU support.

    ```
    set FORCE_CMAKE=1 && set CMAKE_ARGS=-DLLAMA_CUBLAS=on
    pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir -vv
    ```

    The command should complete with no errors. If you receive an error, ask for
    help on [the Discord server](https://discord.gg/6p3fD6rBVm).

6.  Once `llama-cpp-python` has been reinstalled, you can quickly check whether
    GPU support has been installed and set up correctly by running the following
    command.

    ```
    python -c "from llama_cpp import GGML_USE_CUBLAS; print(GGML_USE_CUBLAS)"
    ```

    If you see something similar to this, then you are ready to use your GPU
    with Open Interpreter.

    ```
    ggml_init_cublas: found 1 CUDA devices:
      Device 0: NVIDIA GeForce RTX 3080, compute capability 8.6
    True
    ```

    If you instead see this, then ask for help on [the Discord server](https://discord.gg/6p3fD6rBVm).

    ```
    False
    ```

7.  Finally, run the following command to use Open Interpreter with a local
    language model with GPU support.

    ```
    interpreter --local
    ```

## Windows Subsystem for Linux 2 (WSL2)

1.  Ensure that you have the latest [NVIDIA Display
    Driver](https://www.nvidia.com/download/index.aspx) installed on your host
    **Windows** OS.
2.  Get the latest [NVIDIA CUDA Toolkit for
    WSL2](https://developer.nvidia.com/cuda-downloads) and run the provided
    steps in a WSL terminal.

    To get the correct steps, choose the following options.

    - Operating System: **Linux**
    - Architecture: **x86_64**
    - Distribution: **WSL-Ubuntu**
    - Version: **2.0**
    - Installer Type: **deb (network)**

3.  If installed correctly, the following command will display information about
    your NVIDIA GPU, including the driver version and CUDA version.

    ```
    nvidia-smi
    ```

4.  Next, verify the path where the CUDA Toolkit was installed by running the
    following command.

    ```
    ls /usr/local/cuda/bin/nvcc
    ```

    If it returns the following error, ask for help on [the Discord server](https://discord.gg/6p3fD6rBVm).

    ```
    ls: cannot access '/usr/local/cuda/bin/nvcc': No such file or directory
    ```

5.  Ensure that you have the required build dependencies by running the
    following commands.

    ```
    sudo apt update
    sudo apt install build-essential cmake python3 python3-pip python-is-python3
    ```

6.  Next, reinstall the `llama-cpp-python` package with NVIDIA GPU support by
    running the following command.

    ```
    CUDA_PATH=/usr/local/cuda FORCE_CMAKE=1 CMAKE_ARGS='-DLLAMA_CUBLAS=on' \
    pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir -vv
    ```

    The command should complete with no errors. If you receive an error, ask for
    help on [the Discord server](https://discord.gg/6p3fD6rBVm).

7.  Once `llama-cpp-python` has been reinstalled, you can quickly check whether
    GPU support has been installed and set up correctly by running the following
    command.

    ```
    python -c "from llama_cpp import GGML_USE_CUBLAS; print(GGML_USE_CUBLAS)"
    ```

    If you see something similar to this, then you are ready to use your GPU
    with Open Interpreter.

    ```
    ggml_init_cublas: found 1 CUDA devices:
      Device 0: NVIDIA GeForce RTX 3080, compute capability 8.6
    True
    ```

    If you instead see this, then ask for help on [the Discord server](https://discord.gg/6p3fD6rBVm).

    ```
    False
    ```

8.  Finally, run the following command to use Open Interpreter with a local
    language model with GPU support.

    ```
    interpreter --local
    ```
