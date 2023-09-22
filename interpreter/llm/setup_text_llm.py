

import litellm
from .setup_local_text_llm import setup_local_text_llm
import os
import tokentrim as tt

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

        # Download and use HF model
        return setup_local_text_llm(interpreter)

    else:
        # For non-local use, pass in the model directly
        model = interpreter.model

    # Pass remaining parameters to LiteLLM
    def base_llm(messages):
        """
        Returns a generator
        """

        system_message = messages[0]["content"]

        # TODO swap tt.trim for litellm util
        
        if interpreter.context_window and interpreter.max_tokens:
            trim_to_be_this_many_tokens = interpreter.context_window - interpreter.max_tokens - 25 # arbitrary buffer
            messages = tt.trim(messages, system_message=system_message, max_tokens=trim_to_be_this_many_tokens)
        else:
            try:
                messages = tt.trim(messages, system_message=system_message, model=interpreter.model)
            except:
                # If we don't know the model, just do 3000.
                messages = tt.trim(messages, system_message=system_message, max_tokens=3000)

        if interpreter.debug_mode:
            print("Passing messages into LLM:", messages)

        litellm.set_verbose = interpreter.debug_mode
    
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

        return litellm.completion(**params)

    return base_llm