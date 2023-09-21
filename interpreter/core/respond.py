from interpreter.code_interpreters.create_code_interpreter import create_code_interpreter
from interpreter.utils import get_user_info_string
from ..utils.merge_deltas import merge_deltas
from ..utils.get_user_info_string import get_user_info_string
from ..rag.get_relevant_procedures import get_relevant_procedures
import tokentrim as tt

def respond(interpreter):
    """
    Yields tokens, but also adds them to interpreter.messages
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


        ### RUN THE LLM ###

        # Add a new message from the assistant to interpreter's "messages" attribute
        # (This doesn't go to the LLM. We fill this up w/ the LLM's response)
        interpreter.messages.append({"role": "assistant"})

        # Start putting chunks into the new message
        # + yielding chunks to the user
        for chunk in interpreter._llm(messages_for_llm):

            # Add chunk to the last message
            interpreter.messages[-1] = merge_deltas(interpreter.messages[-1], chunk)

            # This is a coding llm
            # It will yield dict with either a message, language, or code (or language AND code)
            yield chunk

        
        ### OPTIONALLY RUN CODE ###

        if "code" in interpreter.messages[-1]:
            if interpreter.debug_mode:
                print("Running code:", interpreter.messages[-1])

            # What code do you want to run?
            code = interpreter.messages[-1]["code"]

            # Get a code interpreter to run it
            language = interpreter.messages[-1]["language"]
            if language not in interpreter._code_interpreters:
                interpreter._code_interpreters[language] = create_code_interpreter(language)
            code_interpreter = interpreter._code_interpreters[language]

            # Yield each line, also append it to last messages' output
            interpreter.messages[-1]["output"] = ""
            for line in code_interpreter.run(code):
                yield line
                if "output" in line:
                    output = interpreter.messages[-1]["output"]
                    output += "\n" + line["output"]
                    interpreter.messages[-1]["output"] = output.strip()

        else:
            # Doesn't want to run code. We're done
            break

    return