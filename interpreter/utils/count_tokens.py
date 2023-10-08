import tiktoken

def count_tokens(text="", model="gpt-4"):
    """
    Count the number of tokens in a list of tokens
    """

    encoder = tiktoken.encoding_for_model(model)

    return len(encoder.encode(text))


def count_messages_tokens(messages=[], model=None):
    """
    Count the number of tokens in a list of messages
    """

    tokens_used = 0

    for message in messages:
        if isinstance(message, str):
            tokens_used += count_tokens(message, model=model)
        elif "message" in message:
            tokens_used += count_tokens(message["message"], model=model)

    return tokens_used