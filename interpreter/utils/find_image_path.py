import os
import re


# Function to find all paths ending with .png, .jpg, or .jpeg
def find_image_path(text):
    # Regex pattern to find all the specified paths with extensions .png, .jpg, or .jpeg
    pattern = r"([A-Za-z]:\\[^:\n]*?\.(png|jpg|jpeg|PNG|JPG|JPEG))|(/[^:\n]*?\.(png|jpg|jpeg|PNG|JPG|JPEG))"

    # Find all matches using the finditer method
    matches = [match.group(1) for match in re.finditer(pattern, text)]

    # Add to matches a version of matches where each has had "\" removed (present for some terminals)
    matches += [match.replace("\\", "") for match in matches]

    # Filter out the matches that actually exist on the filesystem
    existing_paths = [match for match in matches if os.path.exists(match)]

    # Return the longest one if any exist
    if existing_paths:
        return max(existing_paths, key=len)
    else:
        return None
