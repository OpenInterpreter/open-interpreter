from interpreter.code_interpreters.create_code_interpreter import create_code_interpreter
from ..utils.merge_deltas import merge_deltas

def respond(interpreter):
    """
    Yields tokens, but also adds them to interpreter.messages
    Responds until it decides not to run any more code.
    """

    while True:

        # Store messages we'll send to the LLM before we add new message
        messages_for_llm = interpreter.messages.copy()

        # Add a new message from the assistant. We'll fill this up
        interpreter.messages.append({"role": "assistant"})

        # Start putting chunks into the new message
        # + yielding chunks to the user
        for chunk in interpreter._llm(messages_for_llm):

            # Add chunk to the last message
            interpreter.messages[-1] = merge_deltas(interpreter.messages[-1], chunk)

            # This is a coding llm
            # It will yield dict with either a message, language, or code (or language AND code)
            yield chunk

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