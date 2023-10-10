from .language_map import language_map

def create_code_interpreter(language, sandbox=False, e2b_api_key=None):
    # Case in-sensitive
    language = language.lower()

    try:
        CodeInterpreter = language_map[language]
        return CodeInterpreter(sandbox=sandbox, e2b_api_key=e2b_api_key)
    except KeyError:
        raise ValueError(f"Unknown or unsupported language: {language}")
