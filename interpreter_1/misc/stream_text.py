import random
import time


def stream_text(text, min_chunk=1, max_chunk=5, min_delay=0.001, max_delay=0.003):
    i = 0
    while i < len(text):
        # Get random chunk size between min and max
        chunk_size = random.randint(min_chunk, max_chunk)
        # Get next chunk, ensuring we don't go past end of string
        chunk = text[i : i + chunk_size]
        # Yield the chunk
        yield chunk
        # Increment position
        i += chunk_size
        # Sleep for random delay
        time.sleep(random.uniform(min_delay, max_delay))
