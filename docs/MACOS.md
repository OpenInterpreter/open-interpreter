# Code-Llama on MacOS (Apple Silicon)

When running Open Interpreter on macOS with Code-Llama (either because you did
not enter an OpenAI API key or you ran `interpreter --local`) you may want to
make sure it works correctly by following the instructions below.

Tested on **MacOS Ventura 13.5** with **M2 Pro Chip**.

I use conda as a virtual environment but you can choose whatever you want

```
conda create -n openinterpreter python=3.11.4
```

**Activate your environment:**

```
conda activate
```

**Install open-interpreter:**

```
pip install open-interpreter
```

**Uninstall any previously installed llama-cpp-python packages:**

```
pip uninstall llama-cpp-python -y
```

**Install llama-cpp-python with Apple Silicon support:**

Part 1

```
CMAKE_ARGS="-DLLAMA_METAL=on" FORCE_CMAKE=1 pip install -U llama-cpp-python --no-cache-dir
```

Part 2

```
pip install 'llama-cpp-python[server]'
```
