# Code-Llama on MacOS (Apple Silicon)

When running Open Interpreter on macOS with Code-Llama (either because you did
not enter an OpenAI API key or you ran `interpreter --local`) you may want to
make sure it works correctly by following the instructions below.

Tested on **MacOS Ventura 13.5** with **M2 Pro Chip** and **MacOS Ventura 13.5.1** with **M1 Max**.

I use conda as a virtual environment but you can choose whatever you want. If you go with conda you will find the Apple M1 version of miniconda here: [Link](https://docs.conda.io/projects/miniconda/en/latest/)

```bash
conda create -n openinterpreter python=3.11.4
```

**Activate your environment:**

```bash
conda activate openinterpreter
```

**Install open-interpreter:**

```bash
pip install open-interpreter
```

**Uninstall any previously installed llama-cpp-python packages:**

```bash
pip uninstall llama-cpp-python -y
```

## Install llama-cpp-python with Apple Silicon support

### Prerequisites: Xcode Command Line Tools

Before running the `CMAKE_ARGS` command to install `llama-cpp-python`, make sure you have Xcode Command Line Tools installed on your system. These tools include compilers and build systems essential for source code compilation.

Before proceeding, make sure you have the Xcode Command Line Tools installed. You can check whether they are installed by running:

```bash
xcode-select -p
```

If this command returns a path, then the Xcode Command Line Tools are already installed. If not, you'll get an error message, and you can install them by running:

```bash
xcode-select --install
```

Follow the on-screen instructions to complete the installation. Once installed, you can proceed with installing an Apple Silicon compatible `llama-cpp-python`.

---
### Step 1: Installing llama-cpp-python with ARM64 Architecture and Metal Support


```bash
CMAKE_ARGS="-DCMAKE_OSX_ARCHITECTURES=arm64 -DLLAMA_METAL=on" FORCE_CMAKE=1 pip install --upgrade --force-reinstall llama-cpp-python --no-cache-dir
--no-cache-dir
```

### Step 2: Verifying Installation of llama-cpp-python with ARM64 Support

After completing the installation, you can verify that `llama-cpp-python` was correctly installed with ARM64 architecture support by running the following command:

```bash
lipo -info /path/to/libllama.dylib
```

Replace `/path/to/` with the actual path to the `libllama.dylib` file. You should see output similar to:

```bash
Non-fat file: /Users/[user]/miniconda3/envs/openinterpreter/lib/python3.11/site-packages/llama_cpp/libllama.dylib is architecture: arm64
```

If the architecture is indicated as `arm64`, then you've successfully installed the ARM64 version of `llama-cpp-python`.

### Step 3: Installing Server Components for llama-cpp-python


```bash
pip install 'llama-cpp-python[server]'
```
