
import os
import importlib.util

class PluginManager:
    def __init__(self, plugin_dir='plugins'):
        self.plugin_dir = plugin_dir
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)

    def load_plugin(self, plugin_name):
        plugin_path = os.path.join(self.plugin_dir, f'{plugin_name}.py')
        if not os.path.exists(plugin_path):
            raise FileNotFoundError(f'Plugin {plugin_name} not found in {self.plugin_dir}')

        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)

        return plugin

    def execute_plugin(self, plugin_name, *args, **kwargs):
        plugin = self.load_plugin(plugin_name)
        if hasattr(plugin, 'main'):
            return plugin.main(*args, **kwargs)
        else:
            raise AttributeError(f'Plugin {plugin_name} does not have a main function')

# Example usage:
# plugin_manager = PluginManager()
# result = plugin_manager.execute_plugin('example_plugin', arg1, arg2)
