import getpass
import os
import platform


def get_user_info_string():
    username = getpass.getuser()
    current_working_directory = os.getcwd()
    operating_system = platform.system()
    default_shell = os.environ.get("SHELL")

    return f"[User Info]\nName: {username}\nCWD: {current_working_directory}\nSHELL: {default_shell}\nOS: {operating_system}"
