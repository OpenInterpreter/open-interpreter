
import os
import json
import yaml

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = {}

        if os.path.exists(self.config_file):
            self.load_config()

    def load_config(self):
        if self.config_file.endswith('.json'):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        elif self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            raise ValueError("Unsupported configuration file format")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def save_config(self):
        if self.config_file.endswith('.json'):
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        elif self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
            with open(self.config_file, 'w') as f:
                yaml.safe_dump(self.config, f)
        else:
            raise ValueError("Unsupported configuration file format")

# Example usage:
# config_manager = ConfigManager('config.json')
# config_manager.set('execution_mode', 'safe')
# print(config_manager.get('execution_mode'))
