

from .setup_text_llm import setup_text_llm
from .convert_to_coding_llm import convert_to_coding_llm
from .setup_openai_coding_llm import setup_openai_coding_llm
from ..utils.display_markdown_message import display_markdown_message
import os
import litellm

def setup_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a Coding LLM (a generator that streams deltas with `message` and `code`).
    """

    if (not interpreter.local
        and (interpreter.model in litellm.open_ai_chat_completion_models or interpreter.model.startswith("azure/"))):
        # Function calling LLM
        coding_llm = setup_openai_coding_llm(interpreter)
    else:
        text_llm = setup_text_llm(interpreter)
        coding_llm = convert_to_coding_llm(text_llm, debug_mode=interpreter.debug_mode)
    
    if interpreter.integrations:
        for service in interpreter.integrations:
            if service == "helicone":
                if not os.environ.get("HELICONE_API_KEY"):
                    display_markdown_message("> **Warning:** `HELICONE_API_KEY` is not set. Helicone will not be able to log your LLM requests.")
                else: 
                    display_markdown_message("> **Note:** Helicone will log your LLM requests.")
                    litellm.api_base = "https://oai.hconeai.com/v1"
                    litellm.headers = {"Helicone-Auth": f"Bearer {os.getenv('HELICONE_API_KEY')}"}

    return coding_llm