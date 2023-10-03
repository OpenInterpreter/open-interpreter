import traceback

from interpreter.code_interpreters.base_code_interpreter import BreakLoop
from interpreter.code_interpreters.create_code_interpreter import create_code_interpreter
from interpreter.utils.truncate_output import truncate_output


def code_function(interpreter):
    ### RUN CODE (if it's there) ###

    if "code" not in interpreter.messages[-1]:
        return

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
        try:
            yield {"executing": {"code": code, "language": language}}
        except GeneratorExit:
            # The user might exit here.
            # We need to tell python what we (the generator) should do if they exit
            raise BreakLoop

        # Yield each line, also append it to last messages' output
        interpreter.messages[-1]["output"] = ""
        for line in code_interpreter.run(code):
            yield line
            if "output" in line:
                output = interpreter.messages[-1]["output"]
                output += "\n" + line["output"]

                # Truncate output
                output = truncate_output(output, interpreter.max_output)

                interpreter.messages[-1]["output"] = output.strip()

    except:
        output = traceback.format_exc()
        yield {"output": output.strip()}
        interpreter.messages[-1]["output"] = output.strip()

    yield {"end_of_execution": True}