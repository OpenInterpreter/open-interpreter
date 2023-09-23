import litellm
from ..utils.merge_deltas import merge_deltas
from ..utils.parse_partial_json import parse_partial_json
from ..utils.convert_to_openai_messages import convert_to_openai_messages
import tokentrim as tt


function_schema = {
  "name": "execute",
  "description":
  "Executes code on the user's machine, **in the users local environment**, and returns the output",
  "parameters": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "description":
        "The programming language (required parameter to the `execute` function)",
        "enum": ["python", "R", "shell", "applescript", "javascript", "html"]
      },
      "code": {
        "type": "string",
        "description": "The code to execute (required)"
      }
    },
    "required": ["language", "code"]
  },
}

def setup_openai_coding_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a OI Coding LLM (a generator that takes OI messages and streams deltas with `message`, `language`, and `code`).
    """

    def coding_llm(messages):
        
        # Convert messages
        messages = convert_to_openai_messages(messages)

        # Add OpenAI's reccomended function message
        messages[0]["content"] += "\n\nOnly use the function you have been provided with."

        # Seperate out the system_message from messages
        # (We expect the first message to always be a system_message)
        system_message = messages[0]["content"]
        messages = messages[1:]

        # Trim messages, preserving the system_message
        messages = tt.trim(messages=messages, system_message=system_message, model=interpreter.model)

        if interpreter.debug_mode:
            print("Sending this to the OpenAI LLM:", messages)

        # Create LiteLLM generator
        params = {
            'model': interpreter.model,
            'messages': messages,
            'stream': True,
            'functions': [function_schema]
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

            if "content" in delta and delta["content"]:
                yield {"message": delta["content"]}

            if ("function_call" in accumulated_deltas 
                and "arguments" in accumulated_deltas["function_call"]):

                arguments = accumulated_deltas["function_call"]["arguments"]
                arguments = parse_partial_json(arguments)

                if arguments:

                    if (language is None
                        and "language" in arguments
                        and "code" in arguments # <- This ensures we're *finished* typing language, as opposed to partially done
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