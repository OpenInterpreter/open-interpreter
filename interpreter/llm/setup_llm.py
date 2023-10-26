

from .setup_text_llm import setup_text_llm
from .convert_to_coding_llm import convert_to_coding_llm
from .setup_openai_coding_llm import setup_openai_coding_llm
import os
import litellm
import sys
import platform
import subprocess



def setup_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a Coding LLM (a generator that streams deltas with `message` and `code`).
    """

    # Get some useful system information before starting the LLM
    if interpreter.debug_mode:
        
        # Get Python version
        python_version = sys.version
        print(f"\nPython Version: {python_version}")

        # Get pip version
        try:
            pip_version = subprocess.getoutput('pip --version')
            print(f"Pip Version: {pip_version}")
        except Exception as e:
            print(f"Error retrieving pip version: {e}")

        # Get platform (i.e., Windows, Linux, etc.s)
        platform_name = sys.platform
        print(f"Platform: {platform_name}")

        # More detailed OS info using the platform module
        os_name = platform.system()
        os_release = platform.release()
        os_version = platform.version()
        print(f"OS Name: {os_name}")
        print(f"OS Release: {os_release}")
        print(f"OS Version: {os_version}")

        # Print the architecture as well:
        architecture = platform.architecture()
        print(f"Architecture: {architecture[0]}")

    if (not interpreter.local
        and (interpreter.model in litellm.open_ai_chat_completion_models or interpreter.model.startswith("azure/"))):
        # Function calling LLM
        coding_llm = setup_openai_coding_llm(interpreter)
    else:
        text_llm = setup_text_llm(interpreter)
        coding_llm = convert_to_coding_llm(text_llm, debug_mode=interpreter.debug_mode)

    return coding_llm