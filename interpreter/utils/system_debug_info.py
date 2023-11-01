import platform
import psutil
import subprocess

def get_python_version():
    return platform.python_version()

def get_pip_version():
    try:
        pip_version = subprocess.check_output(['pip', '--version']).decode().split()[1]
    except Exception as e:
        pip_version = str(e)
    return pip_version

def get_os_version():
    return platform.platform()

def get_cpu_info():
    return platform.processor()

def get_ram_info():
    vm = psutil.virtual_memory()
    used_ram = vm.used
    free_ram = vm.free
    used_ram_gb = used_ram / (1024 ** 3)
    free_ram_gb = free_ram / (1024 ** 3)
    total_ram_gb = vm.total / (1024 ** 3)
    return f"{total_ram_gb:.2f} GB used: {used_ram_gb:.2f}, free: {free_ram_gb:.2f}"

def system_info():
    print(f"Python Version: {get_python_version()}\nPip Version: {get_pip_version()}\nOS Version and Architecture: {get_os_version()}\nCPU Info: {get_cpu_info()}\nRAM Info: {get_ram_info()}\n")

if __name__ == '__main__':
    system_info()