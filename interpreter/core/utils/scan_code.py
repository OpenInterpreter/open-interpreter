import os
import subprocess

from .temporary_file import cleanup_temporary_file, create_temporary_file

try:
    from yaspin import yaspin
    from yaspin.spinners import Spinners
except ImportError:
    pass


def scan_code(code, language, interpreter):
    """
    Scan code with semgrep
    """
    language_class = interpreter.computer.terminal.get_language(language)

    temp_file = create_temporary_file(
        code, language_class.file_extension, verbose=interpreter.debug_mode
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
            language_name = language_class.name
            print(
                f"  {'Code Scanner: ' if interpreter.safe_mode == 'auto' else ''}No issues were found in this {language_name} code."
            )
            print("")

        # TODO: it would be great if we could capture any vulnerabilities identified by semgrep
        # and add them to the conversation history

    except Exception as e:
        print(f"Could not scan {language} code. Have you installed 'semgrep'?")
        print(e)
        print("")  # <- Aesthetic choice

    cleanup_temporary_file(temp_file, verbose=interpreter.debug_mode)
