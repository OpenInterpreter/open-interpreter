import appdirs


def get_oi_dir():
    return appdirs.user_config_dir("Open Interpreter Terminal")
