import json
import re

def obj_to_dict(obj):
    """
    Converts an object into a dictionary representation. Only includes
    attributes that do not start with an underscore (to avoid special methods
    and internal attributes).
    """
    return {attr: getattr(obj, attr) for attr in dir(obj) if not attr.startswith('_') and not callable(getattr(obj, attr))}

def merge_deltas(original, delta):
    """
    Pushes the delta into the original and returns that.
    Great for reconstructing OpenAI streaming responses -> complete message objects.
    """
    for key, value in obj_to_dict(delta).items():
        if isinstance(value, dict):
            original[key] = merge_deltas(original.get(key, {}), value)
        elif isinstance(value, set):
            if key in original:
                # If the original value is a set, update it with the new set
                if isinstance(original[key], set):
                    original[key].update(value)
                else:
                    # Handle the case where the original value is not a set
                    original[key] = value
            else:
                original[key] = value
        else:
            original[key] = value
    return original
