import os
from concurrent.futures import ThreadPoolExecutor

import openai
import tiktoken
from prompt_toolkit import prompt


def split_into_chunks(text, tokens, model, overlap):
    encoding = tiktoken.encoding_for_model(model)
    tokenized_text = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokenized_text), tokens - overlap):
        chunk = encoding.decode(tokenized_text[i : i + tokens])
        chunks.append(chunk)
    return chunks


def chunk_responses(responses, tokens, model, overlap):
    encoding = tiktoken.encoding_for_model(model)
    chunked_responses = []
    current_chunk = ""
    current_tokens = 0

    for response in responses:
        tokenized_response = encoding.encode(response)
        new_tokens = current_tokens + len(tokenized_response)

        # If the new token count exceeds the limit, handle the current chunk
        if new_tokens > tokens:
            # If current chunk is empty or response alone exceeds limit, add response as standalone
            if current_tokens == 0 or len(tokenized_response) > tokens:
                chunked_responses.append(response)
            else:
                chunked_responses.append(current_chunk)
                current_chunk = response
                current_tokens = len(tokenized_response)
            continue

        # Add response to the current chunk
        current_chunk += "\n\n" + response if current_chunk else response
        current_tokens = new_tokens

    # Add remaining chunk if not empty
    if current_chunk:
        chunked_responses.append(current_chunk)

    return chunked_responses


def query_map_chunk(transcription, model, query):
    """Query a chunk of text using a given language model."""
    response = openai.ChatCompletion.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": query},
            {"role": "user", "content": transcription},
        ],
    )
    return response["choices"][0]["message"]["content"]


def query_reduce_chunk(transcription, model, query):
    """Reduce previously queried text."""
    response = openai.ChatCompletion.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": query},
            {"role": "user", "content": transcription},
        ],
    )
    return response["choices"][0]["message"]["content"]


def query_map_chunks(chunks, model, query):
    """Query the chunks of text using query_chunk_map."""
    with ThreadPoolExecutor() as executor:
        responses = list(
            executor.map(lambda chunk: query_map_chunk(chunk, model, query), chunks)
        )
    return responses


def query_reduce_chunks(responses, model, chunk_size, overlap):
    """Reduce query responses in a while loop."""
    while len(responses) > 1:
        # Use the previously defined chunk_summaries function to chunk the summaries
        chunks = chunk_responses(responses, chunk_size, model, overlap)

        # Use multithreading to summarize each chunk simultaneously
        with ThreadPoolExecutor() as executor:
            summaries = list(
                executor.map(lambda chunk: query_map_chunks(chunk, model), chunks)
            )

    return summaries[0]


class Files:
    def __init__(self, computer):
        self.computer = computer

    def query(self, text, query, custom_reduce_query=None):
        # Retrieve OpenAI API key
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key is None:
            openai_api_key = prompt(
                "Please enter your OpenAI API key: ", is_password=True
            )

        openai.api_key = openai_api_key

        model = "gpt-3.5-turbo"
        chunk_size = 2000
        overlap = 50

        # Split the text into chunks
        chunks = split_into_chunks(text, chunk_size, model, overlap)

        # (Map) Query each chunk
        responses = query_map_chunks(chunks, model)

        # (Reduce) Compress the responses
        response = query_reduce_chunks(responses, model, chunk_size, overlap)

        return response

    def summarize(self, text, model="gpt-3.5-turbo", chunk_size=2000, overlap=50):
        query = "You are a highly skilled AI trained in language comprehension and summarization. I would like you to read the following text and summarize it into a concise abstract paragraph. Aim to retain the most important points, providing a coherent and readable summary that could help a person understand the main points of the discussion without needing to read the entire text. Please avoid unnecessary details or tangential points."
        custom_reduce_query = "You are tasked with taking multiple summarized texts and merging them into one unified and concise summary. Maintain the core essence of the content and provide a clear and comprehensive summary that encapsulates all the main points from the individual summaries."
        return self.query(text, query, custom_reduce_query)
