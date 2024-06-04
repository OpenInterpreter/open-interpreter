"""
I do not like this and I want to get rid of it lol. Like, what is it doing..?
I guess it's setting up the model. So maybe this should be like, interpreter.llm.load() soon
"""

import os
import subprocess
import time

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm
from prompt_toolkit import prompt

from interpreter.terminal_interface.contributing_conversations import (
    contribute_conversation_launch_logic,
)

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
            if interpreter.llm.model in [
                "gpt-4",
                "gpt-3.5-turbo",
                "gpt-40",
                "gpt-4-turbo",
            ]:
                if (
                    not os.environ.get("OPENAI_API_KEY")
                    and not interpreter.llm.api_key
                    and not interpreter.llm.api_base
                ):
                    display_welcome_message_once()

                    display_markdown_message(
                        """---
                    > OpenAI API key not found

                    To use `gpt-4o` (recommended) please provide an OpenAI API key.

                    To use another language model, run `interpreter --local` or consult the documentation at [docs.openinterpreter.com](https://docs.openinterpreter.com/language-model-setup/).
                    
                    ---
                    """
                    )

                    response = prompt("OpenAI API key: ", is_password=True)

                    if response == "interpreter --local":
                        print(
                            "\nType `interpreter --local` again to use a local language model.\n"
                        )
                        exit()

                    display_markdown_message(
                        """

                    **Tip:** To save this key for later, run one of the following and then restart your terminal. 
                    MacOS: `echo '\\nexport OPENAI_API_KEY=your_api_key' >> ~/.zshrc`
                    Linux: `echo '\\nexport OPENAI_API_KEY=your_api_key' >> ~/.bashrc`
                    Windows: `setx OPENAI_API_KEY your_api_key`
                    
                    ---"""
                    )

                    interpreter.llm.api_key = response
                    time.sleep(2)
                    break

            elif interpreter.llm.model.startswith("ollama/"):
                model_name = interpreter.llm.model.replace("ollama/", "")
                try:
                    # List out all downloaded ollama models. Will fail if ollama isn't installed
                    result = subprocess.run(
                        ["ollama", "list"], capture_output=True, text=True, check=True
                    )
                except Exception as e:
                    print(str(e))
                    interpreter.display_message(
                        f"> Ollama not found\n\nPlease download Ollama from [ollama.com](https://ollama.com/) to use `{model_name}`.\n"
                    )
                    exit()

                lines = result.stdout.split("\n")
                names = [
                    line.split()[0].replace(":latest", "")
                    for line in lines[1:]
                    if line.strip()
                ]  # Extract names, trim out ":latest", skip header

                if model_name not in names:
                    interpreter.display_message(f"\nDownloading {model_name}...\n")
                    subprocess.run(["ollama", "pull", model_name], check=True)

                # Send a ping, which will actually load the model
                interpreter.display_message("\n*Loading model...*\n")

                old_max_tokens = interpreter.llm.max_tokens
                interpreter.llm.max_tokens = 1
                interpreter.computer.ai.chat("ping")
                interpreter.llm.max_tokens = old_max_tokens

                # interpreter.display_message(f"> Model set to `{model_name}`")

            # This is a model we don't have checks for yet.
            break

    # If we're here, we passed all the checks.

    # Auto-run is for fast, light usage -- no messages.
    # If offline, it's usually a bogus model name for LiteLLM since LM Studio doesn't require one.
    if not interpreter.auto_run and not interpreter.offline:
        display_markdown_message(f"> Model set to `{interpreter.llm.model}`")

    if interpreter.llm.model == "i":
        interpreter.display_message(
            "***Note:*** *Conversations with this model will be used to train our open-source model.*\n"
        )
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
        time.sleep(1)

        display_welcome_message_once._displayed = True
