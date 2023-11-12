import platform
import subprocess

import pkg_resources
import psutil


def get_python_version():
    return platform.python_version()


def get_pip_version():
    try:
        pip_version = subprocess.check_output(["pip", "--version"]).decode().split()[1]
    except Exception as e:
        pip_version = str(e)
    return pip_version


def get_oi_version():
    try:
        oi_version_cmd = (
            subprocess.check_output(["interpreter", "--version"]).decode().split()[1]
        )
    except Exception as e:
        oi_version_cmd = str(e)
    oi_version_pkg = pkg_resources.get_distribution("open-interpreter").version
    oi_version = oi_version_cmd, oi_version_pkg
    return oi_version


def get_os_version():
    return platform.platform()


def get_cpu_info():
    return platform.processor()


def get_ram_info():
    vm = psutil.virtual_memory()
    used_ram_gb = vm.used / (1024**3)
    free_ram_gb = vm.free / (1024**3)
    total_ram_gb = vm.total / (1024**3)
    return f"{total_ram_gb:.2f} GB, used: {used_ram_gb:.2f}, free: {free_ram_gb:.2f}"


def interpreter_info(interpreter):
    try:
        if interpreter.local:
            try:
                curl = subprocess.check_output(f"curl {interpreter.api_base}")
            except Exception as e:
                curl = str(e)
        else:
            curl = "Not local"

        # System message:{interpreter.system_message}
        return f"""

        Interpreter Info
        Vision: {interpreter.vision}
        Model: {interpreter.model}
        Function calling: {interpreter.function_calling_llm}
        Context window: {interpreter.context_window}
        Max tokens: {interpreter.max_tokens}

        Auto run: {interpreter.auto_run}
        API base: {interpreter.api_base}
        Local: {interpreter.local}

        Curl output: {curl}
    """
    except:
        return "Error, couldn't get interpreter info"


def system_info(interpreter):
    oi_version = get_oi_version()
    print(
        f"""
        Python Version: {get_python_version()}
        Pip Version: {get_pip_version()}
        Open-interpreter Version: cmd:{oi_version[0]}, pkg: {oi_version[1]}
        OS Version and Architecture: {get_os_version()}
        CPU Info: {get_cpu_info()}
        RAM Info: {get_ram_info()}
        {interpreter_info(interpreter)}
    """
    )
