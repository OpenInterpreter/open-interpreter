import re


def render_message(interpreter, message):
    """
    Renders a dynamic message into a string.
    """

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
                if line.get("format") == "output":
                    outputs.append(line["content"])
            output = "\n".join(outputs)

            # Replace the part with the output
            parts[i] = output

    # Join the parts back into the message
    rendered_message = "".join(parts)

    return rendered_message
