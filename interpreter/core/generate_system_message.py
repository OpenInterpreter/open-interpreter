import traceback

from .rag.get_relevant_procedures_string import get_relevant_procedures_string
from .utils.get_user_info_string import get_user_info_string


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

    #### Add dynamic components, like the user's OS, username, relevant procedures, etc

    system_message += "\n" + get_user_info_string()

    # DISABLED
    # because wait, they'll have terminal open, no text will be selected. if we find a way to call `--os` mode from anywhere, this will be cool though.
    # if interpreter.os:
    #     # Add the user's selection to to the system message in OS mode
    #     try:
    #         selected_text = interpreter.computer.clipboard.get_selected_text()
    #         if len(selected_text) > 20:
    #             system_message += "\nThis is a preview of the user's selected text: " + selected_text[:20] + "..." + selected_text[-20:]
    #     except:
    #         pass

    if not interpreter.local and not interpreter.disable_procedures:
        try:
            system_message += "\n" + get_relevant_procedures_string(interpreter)
        except:
            if interpreter.debug_mode:
                print(traceback.format_exc())
            # It's okay if they can't. This just fixes some common mistakes it makes.

    for language in interpreter.computer.terminal.languages:
        if hasattr(language, "system_message"):
            system_message += "\n\n" + language.system_message

    return system_message.strip()
