import traceback

import litellm

from ..terminal_interface.utils.display_markdown_message import display_markdown_message


def respond(interpreter):
    """
    Yields chunks.
    Responds until it decides not to run any more code or say anything else.
    """

    last_unsupported_code = ""

    while True:
        system_message = interpreter.generate_system_message()

        # Create message object
        system_message = {
            "role": "system",
            "type": "message",
            "content": system_message,
        }

        # Create the version of messages that we'll send to the LLM
        messages_for_llm = interpreter.messages.copy()
        messages_for_llm = [system_message] + messages_for_llm

        # Trim image messages if they're there
        if interpreter.vision:
            image_messages = [msg for msg in messages_for_llm if msg["type"] == "image"]

            if interpreter.os:
                # Keep only the last image if the interpreter is running in OS mode
                if len(image_messages) > 1:
                    for img_msg in image_messages[:-1]:
                        messages_for_llm.remove(img_msg)
                        if interpreter.debug_mode:
                            print("Removing image message!")
            else:
                # Delete all the middle ones (leave only the first and last 2 images) from messages_for_llm
                if len(image_messages) > 3:
                    for img_msg in image_messages[1:-2]:
                        messages_for_llm.remove(img_msg)
                        if interpreter.debug_mode:
                            print("Removing image message!")
                # Idea: we could set detail: low for the middle messages, instead of deleting them

        ### RUN THE LLM ###

        try:
            for chunk in interpreter._llm(messages_for_llm):
                yield {"role": "assistant", **chunk}

        except litellm.exceptions.BudgetExceededError:
            display_markdown_message(
                f"""> Max budget exceeded

                **Session spend:** ${litellm._current_cost}
                **Max budget:** ${interpreter.max_budget}

                Press CTRL-C then run `interpreter --max_budget [higher USD amount]` to proceed.
            """
            )
            break
        # Provide extra information on how to change API keys, if we encounter that error
        # (Many people writing GitHub issues were struggling with this)
        except Exception as e:
            if (
                interpreter.local == False
                and "auth" in str(e).lower()
                or "api key" in str(e).lower()
            ):
                output = traceback.format_exc()
                raise Exception(
                    f"{output}\n\nThere might be an issue with your API key(s).\n\nTo reset your API key (we'll use OPENAI_API_KEY for this example, but you may need to reset your ANTHROPIC_API_KEY, HUGGINGFACE_API_KEY, etc):\n        Mac/Linux: 'export OPENAI_API_KEY=your-key-here',\n        Windows: 'setx OPENAI_API_KEY your-key-here' then restart terminal.\n\n"
                )
            elif interpreter.local == False and "not have access" in str(e).lower():
                response = input(
                    f"  You do not have access to {interpreter.model}. You will need to add a payment method and purchase credits for the OpenAI API billing page (different from ChatGPT) to use `GPT-4`.\n\nhttps://platform.openai.com/account/billing/overview\n\nWould you like to try GPT-3.5-TURBO instead? (y/n)\n\n  "
                )
                print("")  # <- Aesthetic choice

                if response.strip().lower() == "y":
                    interpreter.model = "gpt-3.5-turbo-1106"
                    interpreter.context_window = 16000
                    interpreter.max_tokens = 4096
                    interpreter.function_calling_llm = True
                    display_markdown_message(f"> Model set to `{interpreter.model}`")
                else:
                    raise Exception(
                        "\n\nYou will need to add a payment method and purchase credits for the OpenAI API billing page (different from ChatGPT) to use GPT-4.\n\nhttps://platform.openai.com/account/billing/overview"
                    )
            elif interpreter.local:
                raise Exception(
                    "Error occurred. "
                    + str(e)
                    + """

Please make sure LM Studio's local server is running by following the steps above, if you're using LM Studio (recommended).

If LM Studio's local server is running, please try a language model with a different architecture.

                    """
                )
            else:
                raise

        ### RUN CODE (if it's there) ###

        if interpreter.messages[-1]["type"] == "code":
            if interpreter.debug_mode:
                print("Running code:", interpreter.messages[-1])

            try:
                # What language/code do you want to run?
                language = interpreter.messages[-1]["format"].lower().strip()
                code = interpreter.messages[-1]["content"]

                # Is this language enabled/supported?
                if language not in interpreter.languages:
                    output = f"`{language}` disabled or not supported."

                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": output,
                    }

                    # Let the response continue so it can deal with the unsupported code in another way. Also prevent looping on the same piece of code.
                    if code != last_unsupported_code:
                        last_unsupported_code = code
                        continue
                    else:
                        break

                # Yield a message, such that the user can stop code execution if they want to
                try:
                    yield {
                        "role": "computer",
                        "type": "confirmation",
                        "format": "execution",
                        "content": {
                            "type": "code",
                            "format": language,
                            "content": code,
                        },
                    }
                except GeneratorExit:
                    # The user might exit here.
                    # We need to tell python what we (the generator) should do if they exit
                    break

                # don't let it import computer on os mode — we handle that!
                if interpreter.os and language == "python":
                    code = code.replace("import computer", "")

                # yield each line
                for line in interpreter.computer.run(language, code):
                    yield {"role": "computer", **line}

                # yield final "active_line" message, as if to say, no more code is running. unlightlight active lines
                # (is this a good idea? is this our responsibility? i think so — we're saying what line of code is running! ...?)
                yield {
                    "role": "computer",
                    "type": "console",
                    "format": "active_line",
                    "content": None,
                }

            except:
                yield {
                    "role": "computer",
                    "type": "console",
                    "format": "output",
                    "content": traceback.format_exc(),
                }

        else:
            # Doesn't want to run code. We're done!
            break

    return
