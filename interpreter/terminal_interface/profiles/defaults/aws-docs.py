"""
This is an Open Interpreter profile. It is specialized for searching AWS documentation and is configured to run Anthropic's `Claude 3.5 Sonnet`.
"""

# Configure Open Interpreter
from interpreter import interpreter

interpreter.llm.model = "claude-3-5-sonnet-20240620"
interpreter.computer.import_computer_api = True
interpreter.llm.supports_functions = True
interpreter.llm.supports_vision = True
interpreter.llm.context_window = 100000
interpreter.llm.max_tokens = 4096

AWS_DOCS_SEARCH_URL = "https://docs.aws.amazon.com/search/doc-search.html?searchPath=documentation&searchQuery=<query>"

custom_tool = """

import os
import requests

def search_aws_docs(query):

    url = "https://api.perplexity.ai/chat/completions"

    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "Be precise and concise."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "return_citations": True,
        "search_domain_filter": ["docs.aws.amazon.com"],
        "return_images": False,
        "return_related_questions": False,
        #"search_recency_filter": "month",
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1
    }
    headers = {
        "Authorization": f"Bearer {os.environ.get('PPLX_API_KEY')}",
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)

    print(response.text)

    return response.text

"""


interpreter.computer.run("python", custom_tool)

interpreter.custom_instructions = f"""
You have access to a special function imported inside your python environment, to be executed in python, called `search_aws_docs(query)` which lets you search the AWS docs. 
Use it frequently to ground your usage of AWS products. 
Use it often!

If the user wants you to open the docs, open their browser to the URL: {AWS_DOCS_SEARCH_URL}
"""
