from ..utils.get_user_info_string import get_user_info_string
import traceback

def generate_system_message(interpreter):
    """
    Dynamically generate a system message.

    Takes an interpreter instance,
    returns a string.

    This is easy to replace!
    Just swap out `interpreter.generate_system_message` with another function.
    """

    #### Start with the static system message

    system_message = interpreter.system_message
    

    #### Add dynamic components, like the user's OS, username, etc

    system_message += "\n" + get_user_info_string()
    try:
        system_message += "\n" + interpreter.get_relevant_procedures_string()
    except:
        if interpreter.debug_mode:
            print(traceback.format_exc())
        # In case some folks can't install the embedding model (I'm not sure if this ever happens)
        pass

    return system_message