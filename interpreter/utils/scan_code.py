import os
import subprocess
from yaspin import yaspin
from yaspin.spinners import Spinners

from .temporary_file import create_temporary_file, cleanup_temporary_file
from ..code_interpreters.language_map import language_map


def get_language_file_extension(language_name):
    """
    Get the file extension for a given language
    """
    language = language_map[language_name.lower()]

    if language.file_extension:
        return language.file_extension
    else:
        return language


def get_language_proper_name(language_name):
    """
    Get the proper name for a given language
    """
    language = language_map[language_name.lower()]

    if language.proper_name:
        return language.proper_name
    else:
        return language


def scan_code(code, language, interpreter):
    """
    Scan code with semgrep
    """

    temp_file = create_temporary_file(
        code, get_language_file_extension(language), verbose=interpreter.debug_mode
    )

    temp_path = os.path.dirname(temp_file)
    file_name = os.path.basename(temp_file)

    if interpreter.debug_mode:
        print(f"Scanning {language} code in {file_name}")
        print("---")

    # Run semgrep
    try:
        # HACK: we need to give the subprocess shell access so that the semgrep from our pyproject.toml is available
        # the global namespace might have semgrep from guarddog installed, but guarddog is currenlty
        # pinned to an old semgrep version that has issues with reading the semgrep registry
        # while scanning a single file like the temporary one we generate
        # if guarddog solves [#249](https://github.com/DataDog/guarddog/issues/249) we can change this approach a bit
        with yaspin(text="  Scanning code...").green.right.binary as loading:
            scan = subprocess.run(
                f"cd {temp_path} && semgrep scan --config auto --quiet --error {file_name}",
                shell=True,
            )

        if scan.returncode == 0:
            language_name = get_language_proper_name(language)
            print(
                f"  {'Code Scaner: ' if interpreter.safe_mode == 'auto' else ''}No issues were found in this {language_name} code."
            )
            print("")

        # TODO: it would be great if we could capture any vulnerabilities identified by semgrep
        # and add them to the conversation history

    except Exception as e:
        print(f"Could not scan {language} code.")
        print(e)
        print("")  # <- Aesthetic choice

    cleanup_temporary_file(temp_file, verbose=interpreter.debug_mode)
