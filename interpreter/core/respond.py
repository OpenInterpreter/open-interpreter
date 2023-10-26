import json

from ..code_interpreters.base_code_interpreter import BreakLoop
from ..utils.merge_deltas import merge_deltas
from ..utils.display_markdown_message import display_markdown_message
import traceback
import litellm

def respond(interpreter):
    """
    Yields tokens, but also adds them to interpreter.messages. TBH probably would be good to seperate those two responsibilities someday soon
    Responds until it decides not to run any more code or say anything else.
    """

    while True:

        system_message = interpreter.generate_system_message()

        # Create message object
        system_message = {"role": "system", "message": system_message}

        # Create the version of messages that we'll send to the LLM
        messages_for_llm = interpreter.messages.copy()
        messages_for_llm = [system_message] + messages_for_llm

        # It's best to explicitly tell these LLMs when they don't get an output
        for message in messages_for_llm:
            if "output" in message and message["output"] == "":
                message["output"] = "No output"

        ### RUN THE LLM ###

        # Add a new message from the assistant to interpreter's "messages" attribute
        # (This doesn't go to the LLM. We fill this up w/ the LLM's response)
        interpreter.messages.append({"role": "assistant"})

        # Start putting chunks into the new message
        # + yielding chunks to the user
        try:

            # Track the type of chunk that the coding LLM is emitting
            chunk_type = None

            for chunk in interpreter._llm(messages_for_llm):
                # Add chunk to the last message
                interpreter.messages[-1] = merge_deltas(interpreter.messages[-1], chunk)

                # This is a coding llm
                # It will yield dict with either a message, language, or code (or language AND code)

                # We also want to track which it's sending to we can send useful flags.
                # (otherwise pretty much everyone needs to implement this)
                if "message" in chunk and chunk_type != "message":
                    chunk_type = "message"
                    yield {"start_of_message": True}
                elif "language" in chunk and chunk_type != "code":
                    chunk_type = "code"
                    yield {"start_of_code": True}
                if "code" in chunk and chunk_type != "code":
                    # (This shouldn't happen though — ^ "language" should be emitted first)
                    chunk_type = "code"
                    yield {"start_of_code": True}
                elif "message" not in chunk and chunk_type == "message":
                    chunk_type = None
                    yield {"end_of_message": True}
                elif "code" not in chunk and "language" not in chunk and chunk_type == "code":
                    chunk_type = None
                    yield {"end_of_code": True}

                yield chunk
        except litellm.exceptions.BudgetExceededError:
            display_markdown_message(f"""> Max budget exceeded

                **Session spend:** ${litellm._current_cost}
                **Max budget:** ${interpreter.max_budget}

                Press CTRL-C then run `interpreter --max_budget [higher USD amount]` to proceed.
            """)
            break
        # Provide extra information on how to change API keys, if we encounter that error
        # (Many people writing GitHub issues were struggling with this)
        except Exception as e:
            if 'auth' in str(e).lower() or 'api key' in str(e).lower():
                output = traceback.format_exc()
                raise Exception(
                    f"{output}\n\nThere might be an issue with your API key(s).\n\nTo reset your API key (we'll use OPENAI_API_KEY for this example, but you may need to reset your ANTHROPIC_API_KEY, HUGGINGFACE_API_KEY, etc):\n        Mac/Linux: 'export OPENAI_API_KEY=your-key-here',\n        Windows: 'setx OPENAI_API_KEY your-key-here' then restart terminal.\n\n")
            else:
                raise

        executed = False
        try:
            for func in interpreter.functions:
                did_execute = False
                for result in func(interpreter):
                    did_execute = True
                    yield result

                if did_execute:
                    executed = True
                    break

            if not executed:
                break

        except BreakLoop:
            break

    return
