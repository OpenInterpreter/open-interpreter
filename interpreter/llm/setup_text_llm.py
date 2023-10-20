

import litellm

from ..utils.display_markdown_message import display_markdown_message
from .setup_local_text_llm import setup_local_text_llm
import os
import tokentrim as tt
import traceback

def setup_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    if interpreter.local:

        # Soon, we should have more options for local setup. For now we only have HuggingFace.
        # So we just do that.

        """

        # Download HF models
        if interpreter.model.startswith("huggingface/"):
            # in the future i think we should just have a model_file attribute.
            # this gets set up in the terminal interface / validate LLM settings.
            # then that's passed into this:
            return setup_local_text_llm(interpreter)
        
        # If we're here, it means the user wants to use
        # an OpenAI compatible endpoint running on localhost

        if interpreter.api_base is None:
            raise Exception('''To use Open Interpreter locally, either provide a huggingface model via `interpreter --model huggingface/{huggingface repo name}`
                            or a localhost URL that exposes an OpenAI compatible endpoint by setting `interpreter --api_base {localhost URL}`.''')
        
        # Tell LiteLLM to treat the endpoint as an OpenAI proxy
        model = "custom_openai/" + interpreter.model

        """

        try:
            # Download and use HF model
            return setup_local_text_llm(interpreter)
        except:
            traceback.print_exc()
            # If it didn't work, apologize and switch to GPT-4

            display_markdown_message(f"""
            > Failed to install `{interpreter.model}`.
            \n\n**We have likely not built the proper `{interpreter.model}` support for your system.**
            \n\n(*Running language models locally is a difficult task!* If you have insight into the best way to implement this across platforms/architectures, please join the `Open Interpreter` community Discord, or the `Oobabooga` community Discord, and consider contributing the development of these projects.)
            """)
            
            raise Exception("Architecture not yet supported for local LLM inference via `Oobabooga`. Please run `interpreter` to connect to a cloud model.")

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
            trim_to_be_this_many_tokens = interpreter.context_window - interpreter.max_tokens - 25 # arbitrary buffer
            messages = tt.trim(messages, system_message=system_message, max_tokens=trim_to_be_this_many_tokens)
        else:
            try:
                messages = tt.trim(messages, system_message=system_message, model=interpreter.model)
            except:
                display_markdown_message("""
                **We were unable to determine the context window of this model.** Defaulting to 3000.
                If your model can handle more, run `interpreter --context_window {token limit}` or `interpreter.context_window = {token limit}`.
                Also, please set max_tokens: `interpreter --max_tokens {max tokens per response}` or `interpreter.max_tokens = {max tokens per response}`
                """)
                messages = tt.trim(messages, system_message=system_message, max_tokens=3000)

        if interpreter.debug_mode:
            print("Passing messages into LLM:", messages)
    
        # Create LiteLLM generator
        params = {
            'model': interpreter.model,
            'messages': messages,
            'stream': True,
        }

        # Optional inputs
        if interpreter.api_base:
            params["api_base"] = interpreter.api_base
        if interpreter.api_key:
            params["api_key"] = interpreter.api_key
        if interpreter.max_tokens:
            params["max_tokens"] = interpreter.max_tokens
        if interpreter.temperature:
            params["temperature"] = interpreter.temperature

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
