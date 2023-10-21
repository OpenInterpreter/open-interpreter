import os
import uuid
from functools import partial

import appdirs
from .language_map import language_map


def create_code_interpreter(interpreter, language, use_containers=False):
    """
    Creates and returns a CodeInterpreter instance for the specified language.

    Parameters:
    - interpreter (Interpreter): The calling Interpreter object.
    - language (str): The programming language for which the CodeInterpreter is to be created.
    - use_containers (bool): A flag indicating whether to use containers. If True, a session ID is
      generated and associated with the calling Interpreter object.

    Returns:
    - CodeInterpreter: An instance of the CodeInterpreter class for the specified language,
      configured with the session ID if use_containers is True.

    Raises:
    - ValueError: If the specified language is unknown or unsupported.
    """

    # Case in-sensitive
    language = language.lower()

    if language not in language_map:
        raise ValueError(f"Unknown or unsupported language: {language}")

    CodeInterpreter = language_map[language]

    if not use_containers:
        return CodeInterpreter()

    if interpreter.session_id:
        session_id = interpreter.session_id
    else:
        session_id = f"ses-{str(uuid.uuid4())}"
        interpreter.session_id = session_id
    
    timeout = os.getenv("OI_CONTAINER_TIMEOUT", None)

    if timeout is not None:
        timeout = int(timeout)

    return CodeInterpreter(session_id=session_id, use_containers=use_containers, close_callback=partial(interpreter.container_callback, language=language), auto_remove_timeout=timeout)
