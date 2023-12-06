import litellm
import tokentrim as tt

from ...terminal_interface.utils.display_markdown_message import (
    display_markdown_message,
)
from ..utils.convert_to_openai_messages import convert_to_openai_messages
from ..utils.merge_deltas import merge_deltas
from ..utils.parse_partial_json import parse_partial_json

function_schema = {
    "name": "execute",
    "description": "Executes code on the user's machine, **in the users local environment**, and returns the output",
    "parameters": {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "The programming language (required parameter to the `execute` function)",
                "enum": [
                    # This will be filled dynamically with the languages OI has access to.
                ],
            },
            "code": {"type": "string", "description": "The code to execute (required)"},
        },
        "required": ["language", "code"],
    },
}


def setup_openai_coding_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a OI Coding LLM (a generator that takes OI messages and streams deltas with `message`, `language`, and `code`).
    """

    def coding_llm(messages):
        # Convert messages
        messages = convert_to_openai_messages(
            messages, function_calling=True, vision=interpreter.vision
        )

        # Add OpenAI's recommended function message
        messages[0][
            "content"
        ] += "\n\nOnly use the function you have been provided with."

        # Seperate out the system_message from messages
        # (We expect the first message to always be a system_message)
        system_message = messages[0]["content"]
        messages = messages[1:]

        # Trim messages, preserving the system_message
        try:
            messages = tt.trim(
                messages=messages,
                system_message=system_message,
                model=interpreter.model,
            )
        except:
            if interpreter.context_window:
                messages = tt.trim(
                    messages=messages,
                    system_message=system_message,
                    max_tokens=interpreter.context_window,
                )
            else:
                if len(messages) == 1:
                    display_markdown_message(
                        """
                    **We were unable to determine the context window of this model.** Defaulting to 3000.
                    If your model can handle more, run `interpreter --context_window {token limit}` or `interpreter.context_window = {token limit}`.
                    """
                    )
                messages = tt.trim(
                    messages=messages, system_message=system_message, max_tokens=3000
                )

        if interpreter.debug_mode:
            print("Sending this to the OpenAI LLM:", messages)

        # Add languages OI has access to
        function_schema["parameters"]["properties"]["language"][
            "enum"
        ] = interpreter.languages

        # Create LiteLLM generator
        params = {
            "model": interpreter.model,
            "messages": messages,
            "stream": True,
            "functions": [function_schema],
        }

        # Optional inputs
        if interpreter.api_base:
            params["api_base"] = interpreter.api_base
        if interpreter.api_key:
            params["api_key"] = interpreter.api_key
        if interpreter.api_version:
            params["api_version"] = interpreter.api_version
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

        response = litellm.completion(**params)

        # Parse response

        accumulated_deltas = {}
        language = None
        code = ""

        for chunk in response:
            if "choices" not in chunk or len(chunk["choices"]) == 0:
                # This happens sometimes
                continue

            delta = chunk["choices"][0]["delta"]

            # Accumulate deltas
            accumulated_deltas = merge_deltas(accumulated_deltas, delta)

            if "content" in delta and delta["content"]:
                yield {"type": "message", "content": delta["content"]}

            if (
                "function_call" in accumulated_deltas
                and "arguments" in accumulated_deltas["function_call"]
            ):
                if (
                    "name" in accumulated_deltas["function_call"]
                    and accumulated_deltas["function_call"]["name"] == "execute"
                ):
                    arguments = accumulated_deltas["function_call"]["arguments"]
                    arguments = parse_partial_json(arguments)

                    if arguments:
                        if (
                            language is None
                            and "language" in arguments
                            and "code"
                            in arguments  # <- This ensures we're *finished* typing language, as opposed to partially done
                            and arguments["language"]
                        ):
                            language = arguments["language"]

                        if language is not None and "code" in arguments:
                            # Calculate the delta (new characters only)
                            code_delta = arguments["code"][len(code) :]
                            # Update the code
                            code = arguments["code"]
                            # Yield the delta
                            if code_delta:
                                yield {
                                    "type": "code",
                                    "format": language,
                                    "content": code_delta,
                                }
                    else:
                        if interpreter.debug_mode:
                            print("Arguments not a dict.")

                # Common hallucinations
                elif "name" in accumulated_deltas["function_call"] and (
                    accumulated_deltas["function_call"]["name"] == "python"
                    or accumulated_deltas["function_call"]["name"] == "functions"
                ):
                    if interpreter.debug_mode:
                        print("Got direct python call")
                    if language is None:
                        language = "python"

                    if language is not None:
                        # Pull the code string straight out of the "arguments" string
                        code_delta = accumulated_deltas["function_call"]["arguments"][
                            len(code) :
                        ]
                        # Update the code
                        code = accumulated_deltas["function_call"]["arguments"]
                        # Yield the delta
                        if code_delta:
                            yield {
                                "type": "code",
                                "format": language,
                                "content": code_delta,
                            }

                else:
                    # If name exists and it's not "execute" or "python" or "functions", who knows what's going on.
                    if "name" in accumulated_deltas["function_call"]:
                        print(
                            "Encountered an unexpected function call: ",
                            accumulated_deltas["function_call"],
                            "\nPlease open an issue and provide the above info at: https://github.com/KillianLucas/open-interpreter",
                        )

    return coding_llm
