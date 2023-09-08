# Code-Llama on Windows

When running Open Interpreter on Windows with Code-Llama (either because you did
not enter an OpenAI API key or you ran `interpreter --local`) you may encounter
an error similar to the following.

```
OSError: [WinError 10106] The requested service provider could not be loaded or
initialized
Error during installation with OpenBLAS: Command '['C:\\Users\\Jane\\AppData\\
Local\\Microsoft\\WindowsApps\\python.exe', '-m', 'pip', 'install',
'llama-cpp-python']' returned non-zero exit status 1.
```

The resolve this issue, perform the following steps.

1.  Download and install the latest version of [Visual Studio 2022
    Community](https://visualstudio.microsoft.com/downloads/).
    
    **NOTE:** Visual Studio _Code_ is different from Visual Studio 2022
    Community. You need Visual Studio 2022 Community, but you don't have to
    uninstall Visual Studio Code if you already have it since they can coexist.

2.  During install, choose the following workload.

    - Desktop development for C++ workload

    On the right hand side, ensure that the following optional component is
    checked.

    - C++ CMake tools for Windows

3.  Once installed, open the Start menu, search for **Developer Command Prompt
    for VS 2022**, and open it.

4.  Run the following command.

    ```
    pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir
    ```

    Alternatively, if you want to include GPU suppport, follow the steps in [Local Language Models with GPU Support](./GPU.md)
