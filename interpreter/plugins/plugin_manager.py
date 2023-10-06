from importlib.metadata import entry_points


# adapted from: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata
def register_plugins(interpreter):
    """
    Discover plugins that use the interpreter.plugins entry point and load them
    if the user has defined them in their config.
    """

    interpreter.plugin_list = []

    discovered_plugins = entry_points(group="interpreter.plugins")

    plugins = {}

    if interpreter.plugins:
        for plugin in interpreter.plugins:
            interpreter.plugin_list.append(plugin)

            if discovered_plugins[plugin]:
                if interpreter.debug_mode:
                    print(f"Loading Open Interpreter Plugin {plugin}...")

                plugins[plugin] = discovered_plugins[plugin].load()
            else:
                if interpreter.debug_mode:
                    print(f"Error: Open Interpreter Plugin `{plugin}` not found.")

    interpreter.plugins = plugins
