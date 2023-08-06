import json

def merge_deltas(original, delta):
    for key, value in delta.items():
        if isinstance(value, dict):
            if key not in original:
                original[key] = value
            else:
                merge_deltas(original[key], value)
        else:
            if key in original:
                original[key] += value
            else:
                original[key] = value

def escape_newlines_in_json_string_values(s):
    result = []
    in_string = False
    for ch in s:
        if ch == '"' and (len(result) == 0 or result[-1] != '\\'):
            in_string = not in_string
        if in_string and ch == '\n':
            result.append('\\n')
        else:
            result.append(ch)
    return ''.join(result)

def parse_partial_json(s):
    """
    Tries to parse a string as JSON and if it fails, attempts to 'close' any open JSON structures.

    Parameters:
    s (str): The string to parse as JSON.

    Returns:
    json: The parsed JSON if successful, or None if it fails even after attempting to close open structures.
    """

    # First, try to parse the string as-is. If it's valid JSON, we'll return it directly.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass  # The string is not valid JSON. We'll try to handle this case below.

    # First, make sure newlines inside double quotes are escaped properly (a common error in GPT function calls)
    s = escape_newlines_in_json_string_values(s)

    # Initialize a stack to keep track of open braces and brackets.
    stack = []

    # Initialize a flag to keep track of whether we're currently inside a string.
    is_inside_string = False

    # Process each character in the string one at a time.
    for char in s:

        # Handle quotes, which denote the start or end of a string in JSON.
        if char == '"':
          
            if stack and stack[-1] == '\\': # <- This is a single backslash, even though it looks like two!
              
                # This quote is escaped, so it doesn't affect whether we're inside a string.
                stack.pop()
            else:
                # This quote is not escaped, so it toggles whether we're inside a string.
                is_inside_string = not is_inside_string

        # If we're not inside a string, we need to handle braces and brackets.
        elif not is_inside_string:
            if char == '{' or char == '[':
                # This character opens a new structure, so add it to the stack.
                stack.append(char)
            elif char == '}' or char == ']':
                # This character closes a structure, so remove the most recently opened structure from the stack.
                if stack:
                    stack.pop()

    # If we're still inside a string at the end of processing, we need to close the string.
    if is_inside_string:
        s += '"'

    # Close any remaining open structures in the reverse order that they were opened.
    while stack:
        open_char = stack.pop()
        s += '}' if open_char == '{' else ']'

    # Attempt to parse the string as JSON again now that we've closed all open structures.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # If we still can't parse the string as JSON, return None to indicate failure.
        return None