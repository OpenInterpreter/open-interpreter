import os
from ..utils.display_markdown_message import display_markdown_message
import time
import inquirer

def validate_llm_settings(interpreter):
    """
    Interactivley prompt the user for required LLM settings
    """

    while True:

        if interpreter.local:
            # Ensure model is downloaded and ready to be set up

            if interpreter.model == "":
                display_welcome_message_once()

                # Interactive prompt to download the best local model we know of

                display_markdown_message("""
                **Open Interpreter** will use `Code Llama` for local execution. Use your arrow keys to set up the model.
                """)

                models = {
                    '7B': 'TheBloke/CodeLlama-7B-Instruct-GGUF',
                    '13B': 'TheBloke/CodeLlama-13B-Instruct-GGUF',
                    '34B': 'TheBloke/CodeLlama-34B-Instruct-GGUF'
                }

                parameter_choices = list(models.keys())
                questions = [inquirer.List('param', message="Parameter count (smaller is faster, larger is more capable)", choices=parameter_choices)]
                answers = inquirer.prompt(questions)
                chosen_param = answers['param']

                interpreter.model = "huggingface/" + models[chosen_param]
                break
        
        else:
            # Ensure API keys are set as environment variables

            # OpenAI
            if "gpt" in interpreter.model:
                if not os.environ.get("OPENAI_API_KEY"):
                    
                    display_welcome_message_once()

                    display_markdown_message("""---
                    > OpenAI API key not found

                    To use `GPT-4` (recommended) please provide an OpenAI API key.

                    To use `Code-Llama` (free but less capable) press `enter`.
                    
                    ---
                    """)

                    response = input("OpenAI API key: ")

                    if response == "":
                        # User pressed `enter`, requesting Code-Llama
                        display_markdown_message("""> Switching to `Code-Llama`...
                        
                        **Tip:** Run `interpreter --local` to automatically use `Code-Llama`.
                        
                        ---""")
                        time.sleep(1.5)
                        interpreter.local = True
                        interpreter.model = ""
                        continue
                    
                    display_markdown_message("""

                    **Tip:** To save this key for later, run `export OPENAI_API_KEY=your_api_key` on Mac/Linux or `setx OPENAI_API_KEY your_api_key` on Windows.
                    
                    ---""")
                    
                    time.sleep(2)
                    break

    display_markdown_message(f"> Model set to `{interpreter.model}`")


def display_welcome_message_once():
    """
    Displays a welcome message only on its first call.
    
    Uses an internal attribute `_displayed` to track its state.
    """
    if not hasattr(display_welcome_message_once, "_displayed"):

        display_markdown_message("""
        ●

        Welcome to **Open Interpreter**.
        """)
        time.sleep(1.5)

        display_welcome_message_once._displayed = True