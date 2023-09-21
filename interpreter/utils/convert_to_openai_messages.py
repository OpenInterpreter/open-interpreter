import json

def convert_to_openai_messages(messages):
    new_messages = []

    for message in messages:  
        new_message = {
            "role": message["role"],
            "content": ""
        }

        if "message" in message:
            new_message["content"] = message["message"]

        if "code" in message:
            new_message["function_call"] = {
                "name": "run_code",
                "arguments": json.dumps({
                    "code": message["code"],
                    "language": message["language"]
                })
            }

        new_messages.append(new_message)

        if "output" in message:
            new_messages.append({
                "role": "function",
                "name": "run_code",
                "content": message["output"]
            })

    return new_messages