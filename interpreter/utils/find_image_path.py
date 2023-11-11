import os
import re


def find_image_path(text):
    pattern = r"([A-Za-z]:\\[^:\n]*?\.(png|jpg|jpeg|PNG|JPG|JPEG))|(/[^:\n]*?\.(png|jpg|jpeg|PNG|JPG|JPEG))"
    matches = [match.group() for match in re.finditer(pattern, text) if match.group()]
    matches += [match.replace("\\", "") for match in matches if match]
    existing_paths = [match for match in matches if os.path.exists(match)]
    return max(existing_paths, key=len) if existing_paths else None
