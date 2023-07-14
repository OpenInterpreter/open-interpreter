import json
import re

def close_and_parse_json(s):
    # First, check if the string is valid JSON as-is.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass  # We will handle this case below.

    # If the string is not valid JSON, we will try to close any open structures.

    # count the number of escaped and unescaped quotes
    num_escaped_quotes = len(re.findall(r'\\\"', s))
    num_unescaped_quotes = len(re.findall(r'(?<!\\)\"', s))

    # The number of open quotes is the total number of unescaped quotes
    # minus twice the number of escaped quotes (since each pair of quotes forms a complete string).
    num_open_quotes = num_unescaped_quotes - 2 * num_escaped_quotes

    # append closing characters to the string
    if num_open_quotes % 2 != 0:
        s += '"'

    # Keep a stack of the open braces and brackets, and add closing characters
    # in the reverse order of the opening characters.
    stack = []
    for char in s:
        if char == '{' or char == '[':
            stack.append(char)
        elif char == '}' or char == ']':
            if stack:
                stack.pop()

    while stack:
        open_char = stack.pop()
        if open_char == '{':
            s += '}'
        elif open_char == '[':
            s += ']'

    # attempt to parse the string as JSON again
    try:
        return json.loads(s)
    except json.JSONDecodeError:
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