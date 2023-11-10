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
                if "image" not in message:
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

        if "image" in message and message["role"] == "assistant":
            new_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "This is the result. Does that look right..? Could it be closer to the FULL vision of what we're aiming for (not just one part of it) or is it done? Be detailed in exactly how we could improve it first, then write code to improve it.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": message["image"], "detail": "high"},
                        },
                    ],
                }
            )
            if "output" in message:
                # This is hacky, but only display the message if it's the placeholder warning for now:
                if (
                    "placeholder" in message["output"].lower()
                    or "traceback" in message["output"].lower()
                ):
                    new_messages[-1]["content"][0]["text"] += (
                        "\n\nAlso, I recieved this output from the Open Interpreter code execution system we're using, which executes your markdown code blocks automatically: "
                        + message["output"]
                    )

    if not function_calling:
        new_messages = [
            msg for msg in new_messages if "content" in msg and len(msg["content"]) != 0
        ]

    return new_messages
