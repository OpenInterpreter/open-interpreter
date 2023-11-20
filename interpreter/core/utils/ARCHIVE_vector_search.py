"""
This is not used. See "ARCHIVE_local_get_relevant_procedures_string.py" for more info.
"""

import numpy as np
from chromadb.utils.distance_functions import cosine


def search(query, db, embed_function, num_results=2):
    """
    Finds the most similar value from the embeddings dictionary to the query.

    query is a string
    db is of type [{text: embedding}, {text: embedding}, ...]

    Args:
        query (str): The query to which you want to find a similar value.

    Returns:
        str: The most similar value from the embeddings dictionary.
    """

    # Convert the query to an embedding
    query_embedding = embed_function(query)

    # Calculate the cosine distance between the query embedding and each embedding in the database
    distances = {
        value: cosine(query_embedding, embedding) for value, embedding in db.items()
    }

    # Sort the values by their distance to the query, and select the top num_results
    most_similar_values = sorted(distances, key=distances.get)[:num_results]

    # Return the most similar values
    return most_similar_values
