import litellm
from ..utils.merge_deltas import merge_deltas
from ..utils.parse_partial_json import parse_partial_json
from ..utils.convert_to_openai_messages import convert_to_openai_messages
from ..utils.display_markdown_message import display_markdown_message
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


# Define a helper function to validate arguments based on the schema
def validate_arguments(arguments, schema):
    required_args = schema["parameters"]["required"]
    if all(key in arguments and arguments[key] for key in required_args):
        return True
    return False


def setup_openai_coding_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a OI Coding LLM (a generator that takes OI messages and streams deltas with `message`, `language`, and `code`).
    """

    def coding_llm(messages):

        # Convert messages
        messages = convert_to_openai_messages(messages)

        # Add OpenAI's recommended function message
        messages[0]["content"] += "\n\nOnly use the functions you have been provided with."

        # Seperate out the system_message from messages
        # (We expect the first message to always be a system_message)
        system_message = messages[0]["content"]
        messages = messages[1:]

        # Trim messages, preserving the system_message
        try:
            messages = tt.trim(messages=messages, system_message=system_message, model=interpreter.model)
        except:
            if interpreter.context_window:
                messages = tt.trim(messages=messages, system_message=system_message, max_tokens=interpreter.context_window)
            else:
                display_markdown_message("""
                **We were unable to determine the context window of this model.** Defaulting to 3000.
                If your model can handle more, run `interpreter --context_window {token limit}` or `interpreter.context_window = {token limit}`.
                """)
                messages = tt.trim(messages=messages, system_message=system_message, max_tokens=3000)

        if interpreter.debug_mode:
            print("Sending this to the OpenAI LLM:", messages)

        # Create LiteLLM generator
        params = {
            'model': interpreter.model,
            'messages': messages,
            'stream': True,
            'functions': interpreter.functions_schemas
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

        response = litellm.completion(**params)

        accumulated_deltas = {}

        # Initialize empty arguments dictionary
        arguments = {}
        accumulated_deltas = {}
        for chunk in response:
            if 'choices' not in chunk or len(chunk['choices']) == 0:
                continue

            delta = chunk["choices"][0]["delta"]
            accumulated_deltas = merge_deltas(accumulated_deltas, delta)

            if "content" in delta and delta["content"]:
                yield {"message": delta["content"]}

            if "function_call" in accumulated_deltas and "arguments" in accumulated_deltas["function_call"]:
                partial_arguments = parse_partial_json(accumulated_deltas["function_call"]["arguments"])
                if partial_arguments:
                    arguments.update(partial_arguments)  # Update the arguments dictionary with new values

        # Fetch current function schema based on the function name
        current_schema = next(
            (c for c in interpreter.functions_schemas if c['name'] == accumulated_deltas.get('function_call', {}).get('name')),
            None
        )

        if current_schema is not None:
            # Check if all required keys are present
            if all(key in arguments for key in current_schema['parameters']['required']):

                # Yield each argument individually
                for key, value in arguments.items():
                    yield {key: value}

    return coding_llm
