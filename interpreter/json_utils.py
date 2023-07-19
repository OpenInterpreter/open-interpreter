import json

def close_and_parse_json(s):
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

    # Initialize a stack to keep track of open braces and brackets.
    stack = []

    # Initialize a flag to keep track of whether we're currently inside a string.
    is_inside_string = False

    # Process each character in the string one at a time.
    for char in s:

        # Handle quotes, which denote the start or end of a string in JSON.
        if char == '"':
            if stack and stack[-1] == '\\':
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

class JsonDeltaCalculator:
    def __init__(self):
        self.previous_json = {}
        self.accumulated_str = ""

    def receive_chunk(self, char):
        self.accumulated_str += char

        parsed_json = close_and_parse_json(self.accumulated_str)
        if parsed_json is None:
            return None

        delta = self.calculate_delta(self.previous_json, parsed_json)
        self.previous_json = parsed_json

        if delta != None and delta != {}:
          return delta

    def calculate_delta(self, previous, current):
        delta = {}

        for key, value in current.items():
            if isinstance(value, dict):
                if key not in previous:
                    delta[key] = value
                else:
                    sub_delta = self.calculate_delta(previous[key], value)
                    if sub_delta:
                        delta[key] = sub_delta
            elif isinstance(value, list):
                raise ValueError("Lists are not supported")
            else:
                if key not in previous:
                    delta[key] = value
                else:
                    prev_value = previous[key]
                    if value[len(prev_value):]:
                        delta[key] = value[len(prev_value):]

        return delta