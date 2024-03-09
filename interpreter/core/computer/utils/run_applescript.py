import subprocess

def run_applescript(script):
    """
    Runs the given AppleScript using osascript and returns the result.
    """
    args = ['osascript', '-e', script]
    return subprocess.check_output(args, universal_newlines=True)


def run_applescript_capture(script):
    """
    Runs the given AppleScript using osascript, captures the output and error, and returns them.
    """
    args = ['osascript', '-e', script]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    stdout, stderr = result.stdout, result.stderr
    return stdout, stderr
