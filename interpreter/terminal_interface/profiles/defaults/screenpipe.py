"""
This is an Open Interpreter profile specialized for searching ScreenPipe history.
It leverages Llama 3.1 70b served by Groq and requires the environment variable GROQ_API_KEYH to be set.
"""

# Configure Open Interpreter
from interpreter import interpreter
from datetime import datetime, timezone

interpreter.llm.model = "groq/llama-3.1-70b-versatile"
interpreter.computer.import_computer_api = False
interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False
interpreter.llm.context_window = 100000
interpreter.llm.max_tokens = 4096

# Add the current date and time in UTC
current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

custom_tool = """
import requests
import json
from urllib.parse import quote

def search_screenpipe(query, limit=5, start_time=None, end_time=None):
    base_url = f"http://localhost:3030/search?q={quote(query)}&content_type=ocr&limit={limit}"
    
    if start_time:
        base_url += f"&start_time={quote(start_time)}"
    if end_time:
        base_url += f"&end_time={quote(end_time)}"
    
    response = requests.get(base_url)
    if response.status_code == 200:
        data = response.json()
        # Remove duplicates based on text content
        unique_results = []
        seen_texts = set()
        for item in data["data"]:
            text = item["content"]["text"]
            if text not in seen_texts:
                unique_results.append(item)
                seen_texts.add(text)
        return unique_results
    else:
        return f"Error: Unable to fetch data from ScreenPipe. Status code: {response.status_code}"
"""

# Add the custom tool to the interpreter's environment
interpreter.computer.run("python", custom_tool)

interpreter.custom_instructions = f"""
Current date and time: {current_datetime}

ScreenPipe is a powerful tool that continuously captures and indexes the content displayed on your screen. It creates a searchable history of everything you've seen or interacted with on your computer. This includes text from websites, documents, applications, and even images (through OCR).

You have access to this wealth of information through the `search_screenpipe(query, limit=5, start_time=None, end_time=None)` function. This allows you to provide more contextual and personalized assistance based on the user's recent activities and viewed content.

The `search_screenpipe` function supports optional `start_time` and `end_time` parameters to narrow down the search to a specific time range. The time format should be ISO 8601, like this: "2024-10-16T12:00:00Z".

Here's why querying ScreenPipe is valuable:
1. Context Recall: Users often refer to things they've seen recently but may not remember the exact details. ScreenPipe can help recall this information.
2. Information Verification: You can cross-reference user claims or questions with actual content they've viewed.
3. Personalized Assistance: By knowing what the user has been working on or researching, you can provide more relevant advice and suggestions.
4. Productivity Enhancement: You can help users quickly locate information they've seen before but can't remember where.

Use the `search_screenpipe()` function when:
- The user asks about something they've seen or read recently.
- You need to verify or expand on information the user mentions.
- You want to provide context-aware suggestions or assistance.
- The user is trying to recall specific details from their recent computer usage.
- The user wants to search within a specific time range.

Here's how to use it effectively:
1. When a user's query relates to recent activities or viewed content, identify key terms for the search.
2. If the user specifies a time range, use the `start_time` and `end_time` parameters.
3. Call the `search_screenpipe()` function with these parameters.
4. Analyze the results to find relevant information.
5. Summarize the findings for the user, mentioning the source (app name, window name) and when it was seen (timestamp).

Remember to use this tool proactively when you think it might help answer the user's question, even if they don't explicitly mention ScreenPipe.

Example usage in Python:
```python
# Search without time range
results = search_screenpipe("Open Interpreter", limit=3)

# Search with time range
results = search_screenpipe("project meeting", limit=5, start_time="2024-10-16T12:00:00Z", end_time="2024-10-16T19:00:00Z")

for result in results:
    print(f"Text: {{result['content']['text'][:300]}}...")  # Print first 100 characters
    print(f"Source: {{result['content']['app_name']}} - {{result['content']['window_name']}}")
    print(f"Timestamp: {{result['content']['timestamp']}}")
```

Write valid code. 
"""
