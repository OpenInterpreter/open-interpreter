from interpreter.code_interpreters.create_code_interpreter import create_code_interpreter
from interpreter.utils import display_markdown_message, get_user_info_string
from ..utils.merge_deltas import merge_deltas
from ..utils.get_user_info_string import get_user_info_string
from ..rag.get_relevant_procedures import get_relevant_procedures
from ..utils.truncate_output import truncate_output
import traceback

def respond(interpreter):
    """
    Yields tokens, but also adds them to interpreter.messages. TBH probably would be good to seperate those two responsibilities someday soon
    Responds until it decides not to run any more code or say anything else.
    """

    while True:

        ### PREPARE MESSAGES ###

        system_message = interpreter.system_message
        
        # Open Procedures is an open-source database of tiny, up-to-date coding tutorials.
        # We can query it semantically and append relevant tutorials/procedures to our system message
        if not interpreter.local:
            try:
                system_message += "\n\n" + get_relevant_procedures(interpreter.messages[-2:])
            except:
                # This can fail for odd SLL reasons. It's not necessary, so we can continue
                pass
        
        # Add user info to system_message, like OS, CWD, etc
        system_message += "\n\n" + get_user_info_string()

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

            for chunk in interpreter._llm(messages_for_llm):

                # Add chunk to the last message
                interpreter.messages[-1] = merge_deltas(interpreter.messages[-1], chunk)

                # This is a coding llm
                # It will yield dict with either a message, language, or code (or language AND code)
                yield chunk

        # Provide extra information on how to change API keys, if we encounter that error
        # (Many people writing GitHub issues were struggling with this)
        except Exception as e:
            if 'auth' in str(e).lower() or 'api key' in str(e).lower():
                output = traceback.format_exc()
                raise Exception(f"{output}\n\nThere might be an issue with your API key(s).\n\nTo reset your OPENAI_API_KEY (for example):\n        Mac/Linux: 'export OPENAI_API_KEY=your-key-here',\n        Windows: 'setx OPENAI_API_KEY=your-key-here' then restart terminal.\n\n")
            else:
                raise e
        
        
        ### RUN CODE (if it's there) ###

        if "code" in interpreter.messages[-1]:
            
            if interpreter.debug_mode:
                print("Running code:", interpreter.messages[-1])

            try:
                # What code do you want to run?
                code = interpreter.messages[-1]["code"]

                # Fix a common error where the LLM thinks it's in a Jupyter notebook
                if interpreter.messages[-1]["language"] == "python" and code.startswith("!"):
                    code = code[1:]
                    interpreter.messages[-1]["code"] = code
                    interpreter.messages[-1]["language"] = "shell"

                # Get a code interpreter to run it
                language = interpreter.messages[-1]["language"]
                if language not in interpreter._code_interpreters:
                    interpreter._code_interpreters[language] = create_code_interpreter(language)
                code_interpreter = interpreter._code_interpreters[language]

                # Yield a message, such that the user can stop code execution if they want to
                yield {"executing": {"code": code, "language": language}}

                # Track if you've sent_output.
                # If you never do, we'll send an empty string (to indicate that code has been run)
                sent_output = False

                # Yield each line, also append it to last messages' output
                interpreter.messages[-1]["output"] = ""
                for line in code_interpreter.run(code):
                    yield line
                    if "output" in line:
                        sent_output = True
                        output = interpreter.messages[-1]["output"]
                        output += "\n" + line["output"]

                        # Truncate output
                        output = truncate_output(output, interpreter.max_output)

                        interpreter.messages[-1]["output"] = output.strip()

                if sent_output == False:
                    # Indicate that the code has been run by sending an empty string
                    # I think we can remove this now that we send "executing".. right?
                    yield {"output": ""}

            except:
                output = traceback.format_exc()
                yield {"output": output.strip()}
                interpreter.messages[-1]["output"] = output.strip()

            yield {"end_of_execution": True}

        else:
            # Doesn't want to run code. We're done
            break

    return