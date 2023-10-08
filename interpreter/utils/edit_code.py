import os
from yaspin import yaspin

from .temporary_file import create_temporary_file, cleanup_temporary_file
from .open_file import open_file
from ..code_interpreters.languages.utils.language_tools import get_language_file_extension, get_language_proper_name


def edit_code(code, language, interpreter):
    """
    Edit the code and listen for changes with watchdog
    """

    temp_code = code

    temp_file = create_temporary_file(
        temp_code, get_language_file_extension(language), verbose=interpreter.debug_mode
    )

    language_name = get_language_proper_name(language)

    file_name = os.path.basename(temp_file)

    if interpreter.debug_mode:
        print(f"Editing {language_name} code in {file_name}")
        print("---")

    # Run semgrep
    try:
        print("  Press `ENTER` after you've saved your edits.")

        open_file(temp_file)

        with yaspin(text=f"  Editing {language_name} code...").green.right.dots as loading:
            # HACK: we're just listening for the user to come back and hit Enter
            # but we aren't actually doing anything with it and since we're inside
            # of a yaspin handler, the input prompt doesn't actually render
            done = input("  Press `ENTER` when you're ready to continue:")

            loading.stop()
            loading.hide()

        if done == "":
            print(f"  {language_name} code updated.")
            print("") # <- Aesthetic choice

            temp_code = open(temp_file).read()

            if interpreter.debug_mode:
                print(f"Getting updated {language_name} code from {file_name}")
                print("---")

            cleanup_temporary_file(temp_file, verbose=interpreter.debug_mode)

            if interpreter.debug_mode:
                print(f"Deleting {file_name}")
                print("---")

    except Exception as e:
        print(f"Could not edit {language} code.")
        print(e)
        print("")  # <- Aesthetic choice

    return temp_code
