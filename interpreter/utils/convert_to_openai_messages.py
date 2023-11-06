import json


def convert_to_openai_messages(messages, function_calling=True):
    new_messages = []

    for message in messages:
        new_message = {"role": message["role"], "content": ""}

        if "message" in message:
            new_message["content"] = message["message"]

        if "code" in message:
            if function_calling:
                new_message["function_call"] = {
                    "name": "execute",
                    "arguments": json.dumps(
                        {"language": message["language"], "code": message["code"]}
                    ),
                    # parsed_arguments isn't actually an OpenAI thing, it's an OI thing.
                    # but it's soo useful! we use it to render messages to text_llms
                    "parsed_arguments": {
                        "language": message["language"],
                        "code": message["code"],
                    },
                }
            else:
                new_message[
                    "content"
                ] += f"""\n\n```{message["language"]}\n{message["code"]}\n```"""
                new_message["content"] = new_message["content"].strip()

        new_messages.append(new_message)

        if "output" in message:
            if function_calling:
                new_messages.append(
                    {
                        "role": "function",
                        "name": "execute",
                        "content": message["output"],
                    }
                )
            else:
                if message["output"] == "No output":
                    content = "The code above was executed on my machine. It produced no output. Was that expected?"
                else:
                    content = (
                        "Code output: "
                        + message["output"]
                        + "\n\nWhat does this output mean / what's next (if anything)?"
                    )

                new_messages.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )

    if not function_calling:
        new_messages = [
            msg
            for msg in new_messages
            if "content" in msg and msg["content"].strip() != ""
        ]

    return new_messages
