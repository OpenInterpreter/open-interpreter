import json


import json

def create_message(role, content="", function_call=None):
    message = {"role": role, "content": content}
    if function_call:
        message["function_call"] = function_call
    return message

def convert_to_openai_messages(messages, function_calling=True):
    new_messages = []

    for message in messages:
        role = message.get("role", "user")
        content = message.get("message", "")
        code_block = message.get("code")
        output = message.get("output")

        if code_block:
            if function_calling:
                function_call = {
                    "name": "execute",
                    "arguments": json.dumps({"language": message["language"], "code": code_block}),
                    "parsed_arguments": {"language": message["language"], "code": code_block},
                }
                new_messages.append(create_message(role, output, function_call))
            else:
                formatted_code = f"\n\n```{message['language']}\n{code_block}\n```"
                new_messages.append(create_message(role, content + formatted_code))

        elif output:
            if function_calling:
                new_messages.append(create_message("function", output))
            else:
                output_message = "CODE EXECUTED ON USERS MACHINE. OUTPUT (invisible to the user): " + output
                new_messages.append(create_message(role, output_message))

        else:
            new_messages.append(create_message(role, content))

    return new_messages
