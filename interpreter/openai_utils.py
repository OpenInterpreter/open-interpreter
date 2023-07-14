import tiktoken
import os
import openai
import json

model_max_tokens = {
    'gpt-4': 8192,
    'gpt-4-0613': 8192,
    'gpt-4-32k': 32768,
    'gpt-4-32k-0613': 32768,
    'gpt-3.5-turbo': 4096,
    'gpt-3.5-turbo-16k': 16384,
    'gpt-3.5-turbo-0613': 4096,
    'gpt-3.5-turbo-16k-0613': 16384,
}

def num_tokens_from_messages(messages, model):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
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
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        #print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        #print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():

            try:
              num_tokens += len(encoding.encode(value))
              if key == "name":
                num_tokens += tokens_per_name
            except:
              # This isn't great but functions doesn't work with this! So I do this:
              value = json.dumps(value)
              num_tokens += len(encoding.encode(value))

    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def openai_streaming_response(messages, functions, system_message, model, api_key):

    if api_key == None:
        if 'OPENAI_API_KEY' in os.environ:
            api_key = os.environ['OPENAI_API_KEY']
        else:
            raise Exception("Please provide an OpenAI API key via interpreter.openai_api_key or as an environment variable ('OPENAI_API_KEY').")
    else:
        openai.api_key = api_key

    system_message_event = {"role": "system", "content": system_message}

    max_tokens = model_max_tokens[model]
    max_tokens -= num_tokens_from_messages([system_message_event], model)

    # The list to store final messages
    final_messages = []

    # Token counter
    token_count = 0

    # Process messages in reverse order
    for message in reversed(messages):
        # Tokenize the message content
        tokens = num_tokens_from_messages([message], model)

        # Check if adding the current message would exceed the 8K token limit
        if token_count + tokens > max_tokens:
            break

        # Add the message to the list
        final_messages.append(message)

        # Update the token count
        token_count += tokens

    # Reverse the final_messages list to maintain the order
    final_messages.reverse()

    final_messages.insert(0, system_message_event)

    yield from openai.ChatCompletion.create(
        model=model,
        messages=final_messages,
        functions=functions,
        stream=True
    )