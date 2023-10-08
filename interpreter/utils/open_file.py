import os
import platform
import subprocess

def open_file(file_path):
    if platform.system() == 'Windows':
        os.startfile(file_path)  # This will open the file with the default application, e.g., Notepad
    else:
        try:
            # Try using xdg-open on non-Windows platforms
            subprocess.call(['xdg-open', file_path])
        except FileNotFoundError:
            # Fallback to using 'open' on macOS if 'xdg-open' is not available
            subprocess.call(['open', file_path])