<<<<<<< HEAD
import inspect
import os
import uuid
import weakref

import appdirs
from .language_map import language_map


=======
from .language_map import language_map
>>>>>>> upstream/main

# Global dictionary to store the session IDs by the weak reference of the calling objects
SESSION_IDS_BY_OBJECT = weakref.WeakKeyDictionary()


def create_code_interpreter(language, use_containers=False):
    """
    Creates and returns a CodeInterpreter instance for the specified language.

    The function uses weak references to associate session IDs with calling Interpreter objects,
    ensuring that the objects can be garbage collected when they are no longer in use. The function
    also uses the inspect module to traverse the call stack and identify the calling Interpreter
    object. This allows the function to associate a unique session ID with each Interpreter object,
    even when the object is passed as a parameter through multiple function calls.

    Parameters:
    - language (str): The programming language for which the CodeInterpreter is to be created.
    - use_containers (bool): A flag indicating whether to use containers. If True, a session ID is
      generated and associated with the calling Interpreter object.

    Returns:
    - CodeInterpreter: An instance of the CodeInterpreter class for the specified language,
      configured with the session ID if use_containers is True.

    Raises:
    - RuntimeError: If unable to access the current frame.
    - ValueError: If the specified language is unknown or unsupported.
    """

    from ..core.core import Interpreter
    # Case in-sensitive
    language = language.lower()

<<<<<<< HEAD
    caller_object = None

    if use_containers:
        # Get the current frame
        current_frame = inspect.currentframe()

        if current_frame is None:
            raise RuntimeError("Failed to access the current frame")

        # Initialize frame count
        frame_count = 0

        # Keep going back through the stack frames with a limit of 5 frames back to
        # prevent seeing other instances other than the calling one.
        while current_frame.f_back and frame_count < 5:
            current_frame = current_frame.f_back
            frame_count += 1

            # Iterate over local variables in the current frame
            for var_value in current_frame.f_locals.values():
                if isinstance(var_value, Interpreter):
                    # Found an instance of Interpreter
                    caller_object = var_value
                    break

            if caller_object:
                break

        if caller_object and caller_object not in SESSION_IDS_BY_OBJECT.keys():
            session_id = f"ses-{str(uuid.uuid4())}"
            SESSION_IDS_BY_OBJECT[caller_object] = session_id

=======
>>>>>>> upstream/main
    try:
        # Retrieve the specific CodeInterpreter class based on the language
        CodeInterpreter = language_map[language]

        # Retrieve the session ID for the current calling object, if available
        session_id = SESSION_IDS_BY_OBJECT.get(caller_object, None) if caller_object else None

        if not use_containers or session_id is None:
            return CodeInterpreter()

        session_path = os.path.join(
            appdirs.user_data_dir("Open Interpreter"), "sessions", session_id
        )
        if not os.path.exists(session_path):
            os.makedirs(session_path)
        return CodeInterpreter(session_id=session_id, use_docker=use_containers)
    except KeyError as exc:
        raise ValueError(f"Unknown or unsupported language: {language}. \n ") from exc
    