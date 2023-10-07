from ..llm.functions.schema import function_schema


def extend_functions(interpreter):
    """
    Extend the base Open Interpreter function schema with functions provided by
    external plugins the user has installed.
    """

    function_schemas = [function_schema]

    for plugin in interpreter.plugins:
        if interpreter.debug_mode:
            print(f"Loading functions from plugin: {plugin}")

        plugin_functions = interpreter.plugins[plugin].get_functions()

        for function in plugin_functions:
            if interpreter.debug_mode:
                print(f"Loading function: {function['name']}")

            function_schemas.append(function)
            interpreter.functions[function["name"]] = interpreter.plugins[plugin].execute_function

    return function_schemas
