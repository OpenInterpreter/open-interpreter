from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as setup_embed
import os
import numpy as np

# Set up the embedding function
os.environ["TOKENIZERS_PARALLELISM"] = "false" # Otherwise setup_embed displays a warning message
try:
    chroma_embedding_function = setup_embed()
except:
    # This does set up a model that we don't strictly need.
    # If it fails, it's not worth breaking everything.
    pass

def embed_function(query):
    return np.squeeze(chroma_embedding_function([query])).tolist()