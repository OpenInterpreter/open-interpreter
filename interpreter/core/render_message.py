import re
import time


def render_message(interpreter, message):
    """
    Renders a dynamic message into a string.
    """

    previous_save_skills_setting = interpreter.computer.save_skills
    interpreter.computer.save_skills = False

    # Split the message into parts by {{ and }}, including multi-line strings
    parts = re.split(r"({{.*?}})", message, flags=re.DOTALL)

    for i in range(len(parts)):
        part = parts[i]
        # If the part is enclosed in {{ and }}
        if part.startswith("{{") and part.endswith("}}"):
            # Run the code inside the brackets
            output = interpreter.computer.run(
                "python", part[2:-2].strip(), display=interpreter.verbose
            )

            # Turn it into just a simple string
            outputs = []
            for line in output:
                if interpreter.debug:
                    print(line)
                if line.get("format") == "output":
                    if "IGNORE_ALL_ABOVE_THIS_LINE" in line["content"]:
                        outputs.append(
                            line["content"].split("IGNORE_ALL_ABOVE_THIS_LINE")[1]
                        )
                    else:
                        outputs.append(line["content"])
            output = "\n".join(outputs)

            # Replace the part with the output
            parts[i] = output

    # Join the parts back into the message
    rendered_message = "".join(parts).strip()

    if interpreter.debug:
        print("\n\n\nSYSTEM MESSAGE\n\n\n")
        print(rendered_message)
        print("\n\n\n")

    interpreter.computer.save_skills = previous_save_skills_setting

    return rendered_message
