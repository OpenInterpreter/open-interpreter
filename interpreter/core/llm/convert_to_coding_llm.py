from ..utils.convert_to_openai_messages import convert_to_openai_messages
from .setup_text_llm import setup_text_llm


def convert_to_coding_llm(text_llm, debug_mode=False, vision=False):
    """
    Takes a text_llm
    returns an OI Coding LLM.
    """

    def coding_llm(messages):
        # First, tell it how to run code.

        # System message method:
        assert messages[0]["role"] == "system"
        messages[0][
            "content"
        ] += "\nTo execute code on the user's machine, write a markdown code block. Specify the language after the ```. You will receive the output. Use any programming language."

        # Gaslight method (DISABLED):
        '''
        gaslight = None
        if messages[-1]["role"] == "user":
            # Last message came from the user.
            if messages[-1]["message"].lower() not in [
                "hello",
                "hi",
                "hey",
                "helo",
                "hii",
                "hi!",
            ]:  # :)
                gaslight = """Let's explore this. I can run code on your machine by writing the code in a markdown code block. This works if I put a newline after ```shell, ```python, ```applescript, etc. then write code. I'm going to try to do this for your task **after I make a plan**. I'll put the *correct* language after the "```"."""
        else:
            # Last message came from the assistant.

            # (The below should actually always be True in OI if last message came from the assistant)
            # I think we don't need this actually.
            """
            if "output" in messages[-1]:
                if messages[-1]["output"] != "No output":
                    gaslight = "(Thought: I see that the code I just ran produced an output. The next message I send will go to the user.)"
                elif messages[-1]["output"] == "No output":
                    gaslight = "(Thought: I see that the code I just ran produced no output. The next message I send will go to the user.)"
            """

        if gaslight:
            messages.append({"role": "assistant", "message": gaslight})
        '''

        messages = convert_to_openai_messages(
            messages, function_calling=False, vision=vision
        )

        inside_code_block = False
        accumulated_block = ""
        language = None

        for chunk in text_llm(messages):
            if debug_mode:
                print("Chunk in coding_llm", chunk)

            if "choices" not in chunk or len(chunk["choices"]) == 0:
                # This happens sometimes
                continue

            content = chunk["choices"][0]["delta"].get("content", "")

            accumulated_block += content

            if accumulated_block.endswith("`"):
                # We might be writing "```" one token at a time.
                continue

            # Did we just enter a code block?
            if "```" in accumulated_block and not inside_code_block:
                inside_code_block = True
                accumulated_block = accumulated_block.split("```")[1]

            # Did we just exit a code block?
            if inside_code_block and "```" in accumulated_block:
                return

            # If we're in a code block,
            if inside_code_block:
                # If we don't have a `language`, find it
                if language is None and "\n" in accumulated_block:
                    language = accumulated_block.split("\n")[0]

                    # Default to python if not specified
                    if language == "":
                        language = "python"
                    else:
                        # Removes hallucinations containing spaces or non letters.
                        language = "".join(char for char in language if char.isalpha())

                # If we do have a `language`, send it out
                if language:
                    yield {"type": "code", "format": language, "content": content}

            # If we're not in a code block, send the output as a message
            if not inside_code_block:
                yield {"type": "message", "content": content}

    return coding_llm
