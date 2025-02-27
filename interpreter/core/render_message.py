import concurrent.futures
import re
import threading

# Thread-local cache for rendered messages
_cache_lock = threading.RLock()
_render_cache = {}
_cache_size_limit = 50  # Maximum cache entries to prevent memory bloat


def render_message(interpreter, message):
    """
    Renders a dynamic message into a string.
    Efficiently handles template variables enclosed in {{ and }} by evaluating them as Python code.
    """
    # Check cache first for performance (using message hash as key)
    cache_key = hash((message, interpreter.computer.save_skills))
    with _cache_lock:
        if cache_key in _render_cache:
            return _render_cache[cache_key]

    # Save original setting for computer skills
    previous_save_skills_setting = interpreter.computer.save_skills
    interpreter.computer.save_skills = False

    try:
        # If the message doesn't contain template markers, return it directly
        if "{{" not in message and "}}" not in message:
            return message.strip()

        # Split the message into parts by {{ and }}, including multi-line strings
        parts = re.split(r"({{.*?}})", message, flags=re.DOTALL)

        # Process each part - regular text or template to evaluate
        rendered_parts = []
        for part in parts:
            # If the part is enclosed in {{ and }}
            if part.startswith("{{") and part.endswith("}}"):
                # Run the code inside the brackets and get output
                code_to_run = part[2:-2].strip()
                try:
                    # Execute the Python code and capture the output
                    output = interpreter.computer.run(
                        "python", code_to_run, display=interpreter.verbose
                    )

                    # Extract the output content
                    code_output = []
                    for line in output:
                        if line.get(
                            "format"
                        ) == "output" and "IGNORE_ALL_ABOVE_THIS_LINE" not in line.get(
                            "content", ""
                        ):
                            code_output.append(line["content"])

                    # Join the output lines
                    rendered_parts.append("\n".join(code_output))
                except Exception as e:
                    # Handle errors gracefully by including the error message
                    rendered_parts.append(f"[Error rendering template: {str(e)}]")
            else:
                # Regular text part, just include it as is
                rendered_parts.append(part)

        # Join the parts back into the rendered message
        rendered_message = "".join(rendered_parts).strip()

        # Cache the result for future use
        with _cache_lock:
            if len(_render_cache) >= _cache_size_limit:
                # Simple LRU-like behavior: clear half the cache when full
                keys_to_remove = list(_render_cache.keys())[: _cache_size_limit // 2]
                for key in keys_to_remove:
                    _render_cache.pop(key, None)
            _render_cache[cache_key] = rendered_message

        return rendered_message

    except Exception as e:
        # If anything goes wrong, return the original message with an error note
        return f"{message}\n\n[Error during template rendering: {str(e)}]"

    finally:
        # Always restore original settings
        interpreter.computer.save_skills = previous_save_skills_setting


def parallel_render_variables(interpreter, message):
    """
    More efficient rendering for complex templates with many variables.
    This is a future optimization that could be used for very large system messages.
    Currently experimental.
    """
    # Extract all template variables
    template_matches = re.finditer(r"{{(.*?)}}", message, re.DOTALL)
    template_vars = [
        (match.group(0), match.group(1).strip()) for match in template_matches
    ]

    if not template_vars:
        return message.strip()

    # Create a mapping for replacements
    replacements = {}

    # Execute template variables in parallel
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(len(template_vars), 4)
    ) as executor:

        def execute_template(template, code):
            try:
                output = interpreter.computer.run("python", code, display=False)
                code_output = []
                for line in output:
                    if line.get(
                        "format"
                    ) == "output" and "IGNORE_ALL_ABOVE_THIS_LINE" not in line.get(
                        "content", ""
                    ):
                        code_output.append(line["content"])
                return "\n".join(code_output)
            except Exception as e:
                return f"[Error: {str(e)}]"

        # Submit all template variables for execution
        future_to_template = {
            executor.submit(execute_template, template, code): template
            for template, code in template_vars
        }

        # Collect results
        for future in concurrent.futures.as_completed(future_to_template):
            template = future_to_template[future]
            try:
                result = future.result()
                replacements[template] = result
            except Exception as e:
                replacements[template] = f"[Error: {str(e)}]"

    # Apply all replacements
    rendered_message = message
    for template, replacement in replacements.items():
        rendered_message = rendered_message.replace(template, replacement)

    return rendered_message.strip()


def clear_render_cache():
    """Clear the template rendering cache"""
    global _render_cache
    with _cache_lock:
        _render_cache.clear()
