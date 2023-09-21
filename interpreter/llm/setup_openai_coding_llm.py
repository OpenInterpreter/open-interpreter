"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import litellm
from ..utils.merge_deltas import merge_deltas
from ..utils.parse_partial_json import parse_partial_json
from ..utils.convert_to_openai_messages import convert_to_openai_messages
import tokentrim as tt

function_schema = {
  "name": "run_code",
  "description":
  "Executes code on the user's machine and returns the output",
  "parameters": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "description":
        "The programming language",
        "enum": ["python", "R", "shell", "applescript", "javascript", "html"]
      },
      "code": {
        "type": "string",
        "description": "The code to execute"
      }
    },
    "required": ["language", "code"]
  },
}

def setup_openai_coding_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a Coding LLM (a generator that streams deltas with `message`, `language`, and `code`).
    """

    def coding_llm(messages):
        
        # Convert and trim messages
        messages = convert_to_openai_messages(messages)
        messages = tt.trim(messages, model=interpreter.model)

        if interpreter.debug_mode:
            print("Sending this to the OpenAI LLM:", messages)

        # Create LiteLLM generator
        params = {
            'model': interpreter.model,
            'messages': messages,
            'temperature': interpreter.temperature,
            'functions': [function_schema],
            'stream': True,
        }

        # TODO: What needs to be optional? Can't everything be env vars?
        """
        # Optional inputs
        if interpreter.api_base:
            params["api_base"] = interpreter.api_base
        """

        response = litellm.completion(**params)

        accumulated_deltas = {}
        language = None
        code = ""

        for chunk in response:
            
            if interpreter.debug_mode:
                print(chunk)

            if ('choices' not in chunk or len(chunk['choices']) == 0):
                # This happens sometimes
                continue

            delta = chunk["choices"][0]["delta"]

            # Accumulate deltas
            accumulated_deltas = merge_deltas(accumulated_deltas, delta)

            if "content" in delta and delta["content"]:
                yield {"message": delta["content"]}

            if ("function_call" in accumulated_deltas 
                and "arguments" in accumulated_deltas["function_call"]):

                arguments = accumulated_deltas["function_call"]["arguments"]
                arguments = parse_partial_json(arguments)

                if arguments:

                    if (language is None
                        and "language" in arguments
                        and arguments["language"]):
                        language = arguments["language"]
                        yield {"language": language}
                    
                    if language is not None and "code" in arguments:
                        # Calculate the delta (new characters only)
                        code_delta = arguments["code"][len(code):]
                        # Update the code
                        code = arguments["code"]
                        # Yield the delta
                        if code_delta:
                          yield {"code": code_delta}
            
    return coding_llm