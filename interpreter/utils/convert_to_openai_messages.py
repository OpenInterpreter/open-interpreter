import json

def convert_to_openai_messages(messages, function_calling=True):
    new_messages = []

    for message in messages:  
        new_message = {
            "role": message["role"],
            "content": ""
        }

        if "message" in message:
            new_message["content"] = message["message"]

        if "code" in message:
            if function_calling:
                new_message["function_call"] = {
                    "name": "run_code",
                    "arguments": json.dumps({
                        "language": message["language"],
                        "code": message["code"]
                    }),
                    # parsed_arguments isn't actually an OpenAI thing, it's an OI thing.
                    # but it's soo useful! we use it to render messages to text_llms
                    "parsed_arguments": {
                        "language": message["language"],
                        "code": message["code"]
                    }
                }
            else:
                new_message["content"] += f"""\n\n```{message["language"]}\n{message["code"]}\n```"""
                new_message["content"] = new_message["content"].strip()

        new_messages.append(new_message)

        if "output" in message:
            if function_calling:
                new_messages.append({
                    "role": "function",
                    "name": "run_code",
                    "content": message["output"]
                })
            else:
                new_messages.append({
                    "role": "user",
                    "content": "CODE EXECUTED ON USERS MACHINE. OUTPUT (invisible to the user): " + message["output"]
                })

    return new_messages