import random
import time

from edit import CodeStreamView


def feed_json_in_chunks(
    json_str: str, streamer: CodeStreamView, min_chunk=1, max_chunk=40
):
    """Feed a JSON string to the streamer in random sized chunks"""

    i = 0
    while i < len(json_str):
        # Get random chunk size between min and max
        chunk_size = random.randint(min_chunk, max_chunk)
        # Get next chunk, ensuring we don't go past end of string
        chunk = json_str[i : i + chunk_size]
        # Feed the chunk
        streamer.feed(chunk)
        # Increment position
        i += chunk_size
        # Sleep for random delay between 0.01 and 0.3
        time.sleep(random.uniform(0.001, 0.003))

    streamer.close()


# Example JSON to stream
json_str = """{"command": "create", "path": "temp/test.py", "file_text": "def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world()def hello_world():\\n    print(\\"Hello world!\\")\\n\\ndef calculate_sum(a, b):\\n    return a + b\\n\\nif __name__ == \\"__main\\":\\n    hello_world()\\n    result = calculate_sum(5, 3)\\n    print(f\\"Sum: {result}\\")\\n"}"""

# Feed the JSON string in chunks
streamer = CodeStreamView()
streamer.name = "str_replace_editor"
feed_json_in_chunks(json_str, streamer)

# Ask user if they want to create the file
path = "/tmp/test_file.txt"

# response = input(f"\n\033[38;5;240mCreate \033[0m\033[1m{path}\033[0m?" + "\n\n(y/n): ").lower().strip()

print(
    "\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
)

# Example view JSON to stream
view_json = """{"command": "view", "path": "something/test.py"}"""

# Feed the view JSON string in chunks
streamer = CodeStreamView()
streamer.name = "str_replace_editor"
feed_json_in_chunks(view_json, streamer)


# Example insert JSON to stream
insert_json = """{"command": "insert", 
                 "path": "interpreter/computer_use/ui/test_edit.py", 
                 "insert_line": 1, 
                 "new_str": "import random\\nfrom datetime import datetime\\n\\ndef greet_user():\\n    current_time = datetime.now().strftime(\\"%H:%M:%S\\")\\n    print(f\\"Hello! The current time is {current_time}\\")\\n    \\ndef calculate_random_sum():\\n    num1 = random.randint(1, 100)\\n    num2 = random.randint(1, 100)\\n    return num1 + num2\\n\\ngreet_user()\\nresult = calculate_random_sum()\\nprint(f\\"Random sum: {result}\\")"
                }"""

# Feed the insert JSON string in chunks
streamer = CodeStreamView()
streamer.name = "str_replace_editor"
feed_json_in_chunks(insert_json, streamer)


# Example insert JSON to stream
insert_json = """{"command": "insert",
                 "path": "interpreter/computer_use/loop.py",
                 "old_str": "user_approval = None\\n        tool_result_content: list[BetaToolResultBlockParam] = []\\n        for content_block in cast(list[BetaContentBlock], response.content):\\n            output_callback(content_block)\\n",
                 "new_str": "user_approval = None\\n        tool_result_content: list[BetaToolResultBlockParam] = []\\n        for content_block in cast(list[BetasContentBlock], response.content):\\n            output_callback(content_block)\\n"
                }"""

# Validate that the JSON is properly formatted
import json

try:
    json.loads(insert_json)
except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")
    exit(1)


# Feed the insert JSON string in chunks
streamer = CodeStreamView()
streamer.name = "str_replace_editor"
feed_json_in_chunks(insert_json, streamer)
