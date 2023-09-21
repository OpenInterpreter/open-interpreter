"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

import litellm
from ..utils.merge_deltas import merge_deltas
from ..utils.parse_partial_json import parse_partial_json

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

        params = {
            'model': interpreter.model,
            'messages': messages,
            'temperature': interpreter.temperature,
            'functions': [function_schema],
            'stream': True,
        }

        # Optional inputs
        if interpreter.api_base:
            params["api_base"] = interpreter.api_base

        response = litellm.completion(**params)
        accumulated_deltas = {}
        language = None
        code = ""

        for chunk in response:

            if ('choices' not in chunk or len(chunk['choices']) == 0):
                # This happens sometimes
                continue

            delta = chunk["choices"][0]["delta"]

            # Accumulate deltas
            accumulated_deltas = merge_deltas(accumulated_deltas, delta)

            if (accumulated_deltas["function_call"] 
                and "arguments" in accumulated_deltas["function_call"]):

                arguments = accumulated_deltas["function_call"]["arguments"]
                arguments = parse_partial_json(arguments)

                if arguments:

                    if language is None and "language" in arguments:
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