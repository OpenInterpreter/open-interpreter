from .language_map import language_map


def create_code_interpreter(config):
    # Case in-sensitive
    language = config["language"].lower()

    try:
        CodeInterpreter = language_map[language]
        return CodeInterpreter(config)
    except KeyError:
        raise ValueError(f"Unknown or unsupported language: {language}")
