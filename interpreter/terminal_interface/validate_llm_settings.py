import getpass
import os
import time

import litellm

from .utils.display_markdown_message import display_markdown_message


def validate_llm_settings(interpreter):
    """
    Interactively prompt the user for required LLM settings
    """

    # This runs in a while loop so `continue` lets us start from the top
    # after changing settings (like switching to/from local)
    while True:
        if interpreter.offline:
            # We have already displayed a message.
            # (This strange behavior makes me think validate_llm_settings needs to be rethought / refactored)
            break

        else:
            # Ensure API keys are set as environment variables

            # OpenAI
            if interpreter.llm.model in litellm.open_ai_chat_completion_models:
                if not os.environ.get("OPENAI_API_KEY") and not interpreter.llm.api_key:
                    display_welcome_message_once()

                    display_markdown_message(
                        """---
                    > OpenAI API key not found

                    To use `GPT-4` (highly recommended) please provide an OpenAI API key.

                    To use another language model, consult the documentation at [docs.openinterpreter.com](https://docs.openinterpreter.com/language-model-setup/).
                    
                    ---
                    """
                    )

                    response = getpass.getpass("OpenAI API key: ")
                    print(f"OpenAI API key: {response[:4]}...{response[-4:]}")

                    display_markdown_message(
                        """

                    **Tip:** To save this key for later, run `export OPENAI_API_KEY=your_api_key` on Mac/Linux or `setx OPENAI_API_KEY your_api_key` on Windows.
                    
                    ---"""
                    )

                    interpreter.llm.api_key = response
                    time.sleep(2)
                    break

            # This is a model we don't have checks for yet.
            break

    # If we're here, we passed all the checks.

    # Auto-run is for fast, light useage -- no messages.
    # If offline, it's usually a bogus model name for LiteLLM since LM Studio doesn't require one.
    if not interpreter.auto_run and not interpreter.offline:
        display_markdown_message(f"> Model set to `{interpreter.llm.model}`")
    return


def display_welcome_message_once():
    """
    Displays a welcome message only on its first call.

    (Uses an internal attribute `_displayed` to track its state.)
    """
    if not hasattr(display_welcome_message_once, "_displayed"):
        display_markdown_message(
            """
        ●

        Welcome to **Open Interpreter**.
        """
        )
        time.sleep(1.5)

        display_welcome_message_once._displayed = True
