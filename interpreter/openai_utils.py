"""
Module to generate an OpenAI streaming response.

Based on: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

Automatically manages token count based on model's maximum token limit. If the total 
tokens in a conversation exceed the model's limit, the `openai_streaming_response` function will remove messages from 
the beginning of the conversation until the total token count is under the limit. The system message is always 
preserved.

If a user message in conjunction with the system message still exceeds the token limit, the user message will be 
trimmed from the middle character by character, with a '...' indicating the trimmed part. This way, the conversation 
always fits within the model's token limit while preserving the context as much as possible.
"""

import tiktoken
import openai
import json
from typing import List, Dict, Any

# Dictionary to store the maximum tokens for each model
MODEL_MAX_TOKENS: Dict[str, int] = {
    'gpt-4': 8192,
    'gpt-4-0613': 8192,
    'gpt-4-32k': 32768,
    'gpt-4-32k-0613': 32768,
    'gpt-3.5-turbo': 4096,
    'gpt-3.5-turbo-16k': 16384,
    'gpt-3.5-turbo-0613': 4096,
    'gpt-3.5-turbo-16k-0613': 16384,
}


def num_tokens_from_messages(messages: List[Dict[str, Any]], model: str) -> int:
    """
    Function to return the number of tokens used by a list of messages.
    """
    # Attempt to get the encoding for the specified model
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Token handling specifics for different model types
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4
        tokens_per_name = -1
    elif "gpt-3.5-turbo" in model:
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    
    # Calculate the number of tokens
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            try:
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
            except Exception:
                value = json.dumps(value)
                num_tokens += len(encoding.encode(value))

    num_tokens += 3
    return num_tokens


def shorten_message_to_fit_limit(message: str, tokens_needed: int, encoding) -> str:
    """
    Shorten a message to fit within a token limit by removing characters from the middle.
    """
    while len(encoding.encode(message)) > tokens_needed:
        middle = len(message) // 2
        message = message[:middle-1] + "..." + message[middle+2:]
    return message


def openai_streaming_response(messages: List[Dict[str, Any]], functions: List[Any], system_message: str, model: str, temperature: float, api_key: str) -> Any:
    """
    Function to generate an OpenAI streaming response.

    If the total tokens in a conversation exceed the model's maximum limit, 
    this function removes messages from the beginning of the conversation 
    until the total token count is under the limit. Preserves the
    system message at the top of the conversation no matter what.

    If a user message in conjunction with the system message still exceeds the token limit,
    the user message is trimmed from the middle character by character, with a '...' indicating the trimmed part.
    """
    # Setting the OpenAI API key
    openai.api_key = api_key

    # Preparing the system message event
    system_message_event = {"role": "system", "content": system_message}

    # Attempt to get the encoding for the specified model
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    # Determining the maximum tokens available after accounting for the system message
    max_tokens = MODEL_MAX_TOKENS[model] - num_tokens_from_messages([system_message_event], model)

    # Prepare the final_messages list and the token_count
    final_messages = []
    token_count = 0

    # Process the messages in reverse to fit as many as possible within the token limit
    for message in reversed(messages):
        tokens = num_tokens_from_messages([message], model)
        if token_count + tokens > max_tokens:
            if token_count + num_tokens_from_messages([system_message_event], model) > max_tokens:
                # If one message with system message puts it over the limit, it will cut down the user message character by character from the middle.
                message["content"] = shorten_message_to_fit_limit(message["content"], max_tokens - token_count, encoding)
            else:
                break
        final_messages.append(message)
        token_count += tokens

    # Reverse the final_messages to maintain original order
    final_messages.reverse()

    # Include the system message as the first message
    final_messages.insert(0, system_message_event)

    # Generate and yield the response from the OpenAI ChatCompletion API
    yield from openai.ChatCompletion.create(
        model=model,
        messages=final_messages,
        functions=functions,
        stream=True,
        temperature=temperature,
    )