import traceback

from .rag.get_relevant_procedures_string import get_relevant_procedures_string
from .utils.OLD_get_user_info_string import get_user_info_string


def extend_system_message(interpreter):
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

    if not interpreter.offline and not interpreter.os:
        try:
            system_message += "\n" + get_relevant_procedures_string(interpreter)
        except:
            if interpreter.verbose:
                print(traceback.format_exc())
            # It's okay if they can't. This just fixes some common mistakes it makes.

    for language in interpreter.computer.terminal.languages:
        if hasattr(language, "system_message"):
            system_message += "\n\n" + language.system_message

    if interpreter.custom_instructions:
        system_message += "\n\n" + interpreter.custom_instructions

    if interpreter.os:
        try:
            import pywinctl

            active_window = pywinctl.getActiveWindow()

            if active_window:
                app_info = ""

                if "_appName" in active_window.__dict__:
                    app_info += (
                        "Active Application: " + active_window.__dict__["_appName"]
                    )

                if hasattr(active_window, "title"):
                    app_info += "\n" + "Active Window Title: " + active_window.title
                elif "_winTitle" in active_window.__dict__:
                    app_info += (
                        "\n"
                        + "Active Window Title:"
                        + active_window.__dict__["_winTitle"]
                    )

                if app_info != "":
                    system_message += (
                        "\n\n# Important Information:\n"
                        + app_info
                        + "\n(If you need to be in another active application to help the user, you need to switch to it.)"
                    )

        except:
            # Non blocking
            pass

    return system_message.strip()
