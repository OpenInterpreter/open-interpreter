"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import litellm

def setup_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    if interpreter.local:

        # Download HF models
        if interpreter.model.startswith("huggingface/"):
            model = interpreter.model.split("huggingface/")[1]
            return get_HF_model(model)
        
        # If we're here, it means the user wants to use
        # an OpenAI compatible endpoint running on localhost

        if interpreter.api_base is None:
            raise Exception("""To use Open Interpreter locally, provide a huggingface model via `interpreter --model huggingface/{huggingface repo name}`
                            or a localhost URL that exposes an OpenAI compatible endpoint via `interpreter --local --api_base {localhost url}`""")
        
        # Tell LiteLLM to treat the endpoint as an OpenAI proxy
        model = "openai-proxy/" + interpreter.model

    else:
        # For non-local use, pass in the model directly
        model = interpreter.model


    # Pass remaining parameters to LiteLLM
    def base_llm(messages):
        """
        Returns a generator
        """
    
        return litellm.completion(
            model=model,
            messages=messages,
            temperature=interpreter.temperature,
            max_tokens=interpreter.max_tokens,
            stream=True,
        )

    return base_llm