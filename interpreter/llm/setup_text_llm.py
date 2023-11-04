import os
import traceback

import litellm
import tokentrim as tt

from ..utils.display_markdown_message import display_markdown_message
from .setup_local_text_llm import setup_local_text_llm


def setup_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    # Pass remaining parameters to LiteLLM
    def base_llm(messages):
        """
        Returns a generator
        """

        system_message = messages[0]["content"]

        # Tell it how to run code.
        # THIS MESSAGE IS DUPLICATED IN `setup_local_text_llm.py`
        # (We should deduplicate it somehow soon)
        system_message += "\nTo execute code on the user's machine, write a markdown code block *with the language*, i.e:\n\n```python\nprint('Hi!')\n```\n\nYou will receive the output ('Hi!'). Use any language."

        # TODO swap tt.trim for litellm util
        messages = messages[1:]
        if interpreter.context_window and interpreter.max_tokens:
            trim_to_be_this_many_tokens = (
                interpreter.context_window - interpreter.max_tokens - 25
            )  # arbitrary buffer
            messages = tt.trim(
                messages,
                system_message=system_message,
                max_tokens=trim_to_be_this_many_tokens,
            )
        else:
            try:
                messages = tt.trim(
                    messages, system_message=system_message, model=interpreter.model
                )
            except:
                display_markdown_message(
                    """
                **We were unable to determine the context window of this model.** Defaulting to 3000.
                If your model can handle more, run `interpreter --context_window {token limit}` or `interpreter.context_window = {token limit}`.
                Also, please set max_tokens: `interpreter --max_tokens {max tokens per response}` or `interpreter.max_tokens = {max tokens per response}`
                """
                )
                messages = tt.trim(
                    messages, system_message=system_message, max_tokens=3000
                )

        if interpreter.debug_mode:
            print("Passing messages into LLM:", messages)

        # Create LiteLLM generator
        params = {
            "model": interpreter.model,
            "messages": messages,
            "stream": True,
        }

        # Optional inputs
        if interpreter.api_base:
            params["api_base"] = interpreter.api_base
        if interpreter.api_key:
            params["api_key"] = interpreter.api_key
        if interpreter.max_tokens:
            params["max_tokens"] = interpreter.max_tokens
        if interpreter.temperature is not None:
            params["temperature"] = interpreter.temperature
        else:
            params["temperature"] = 0.0

        # These are set directly on LiteLLM
        if interpreter.max_budget:
            litellm.max_budget = interpreter.max_budget
        if interpreter.debug_mode:
            litellm.set_verbose = True

        # Report what we're sending to LiteLLM
        if interpreter.debug_mode:
            print("Sending this to LiteLLM:", params)

        return litellm.completion(**params)

    return base_llm
