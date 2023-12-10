import base64
import json


def convert_to_openai_messages(messages, function_calling=True, vision=False):
    """
    Converts LMC messages into OpenAI messages
    """
    new_messages = []

    for message in messages:
        if "recipient" in message:
            if message["recipient"] != "assistant":
                continue

        new_message = {}

        if message["type"] == "message":
            new_message["role"] = message[
                "role"
            ]  # This should never be `computer`, right?
            new_message["content"] = message["content"]

        elif message["type"] == "code":
            new_message["role"] = "assistant"
            if function_calling:
                new_message["function_call"] = {
                    "name": "execute",
                    "arguments": json.dumps(
                        {"language": message["format"], "code": message["content"]}
                    ),
                    # parsed_arguments isn't actually an OpenAI thing, it's an OI thing.
                    # but it's soo useful!
                    "parsed_arguments": {
                        "language": message["format"],
                        "code": message["content"],
                    },
                }
            else:
                new_message[
                    "content"
                ] = f"""```{message["format"]}\n{message["content"]}\n```"""

        elif message["type"] == "console" and message["format"] == "output":
            if function_calling:
                new_message["role"] = "function"
                new_message["name"] = "execute"
                if message["content"].strip() == "":
                    new_message[
                        "content"
                    ] = "No output"  # I think it's best to be explicit, but we should test this.
                else:
                    new_message["content"] = message["content"]

            else:
                if message["content"].strip() == "":
                    content = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
                else:
                    content = (
                        "Code output: "
                        + message["content"]
                        + "\n\nWhat does this output mean / what's next (if anything, or are we done)?"
                    )

                new_message["role"] = "user"
                new_message["content"] = content

        elif message["type"] == "image":
            if vision == False:
                continue

            if "base64" in message["format"]:
                # Extract the extension from the format, default to 'png' if not specified
                if "." in message["format"]:
                    extension = message["format"].split(".")[-1]
                else:
                    extension = "png"

                # Construct the content string
                content = f"data:image/{extension};base64,{message['content']}"

            elif message["format"] == "path":
                # Convert to base64
                image_path = message["content"]
                file_extension = image_path.split(".")[-1]

                with open(image_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

                content = f"data:image/{file_extension};base64,{encoded_string}"
            else:
                # Probably would be better to move this to a validation pass
                # Near core, through the whole messages object
                if "format" not in message:
                    raise Exception("Format of the image is not specified.")
                else:
                    raise Exception(f"Unrecognized image format: {message['format']}")

            # Calculate the size of the original binary data in bytes
            content_size_bytes = len(content) * 3 / 4

            # Convert the size to MB
            content_size_mb = content_size_bytes / (1024 * 1024)

            # Print the size of the content in MB
            # print(f"File size: {content_size_mb} MB")

            # Assert that the content size is under 20 MB
            assert content_size_mb < 20, "Content size exceeds 20 MB"

            new_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": content, "detail": "low"},
                    }
                ],
            }

        elif message["type"] == "file":
            new_message = {"role": "user", "content": message["content"]}

        else:
            raise Exception(f"Unable to convert this message type: {message}")

        new_messages.append(new_message)

    """
    # Combine adjacent user messages
    combined_messages = []
    i = 0
    while i < len(new_messages):
        message = new_messages[i]
        if message["role"] == "user":
            combined_content = []
            while i < len(new_messages) and new_messages[i]["role"] == "user":
                if isinstance(new_messages[i]["content"], str):
                    combined_content.append({
                        "type": "text",
                        "text": new_messages[i]["content"]
                    })
                elif isinstance(new_messages[i]["content"], list):
                    combined_content.extend(new_messages[i]["content"])
                i += 1
            message["content"] = combined_content
        combined_messages.append(message)
        i += 1
    new_messages = combined_messages

    if not function_calling:
        # Combine adjacent assistant messages, as "function calls" will just be normal messages with content: markdown code blocks
        combined_messages = []
        i = 0
        while i < len(new_messages):
            message = new_messages[i]
            if message["role"] == "assistant":
                combined_content = ""
                while i < len(new_messages) and new_messages[i]["role"] == "assistant":
                    combined_content += new_messages[i]["content"] + "\n\n"
                    i += 1
                message["content"] = combined_content.strip()
            combined_messages.append(message)
            i += 1
        new_messages = combined_messages
    """

    return new_messages
