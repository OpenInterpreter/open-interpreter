import os
import interpreter

currentPath = os.path.dirname(os.path.abspath(__file__))
config_path=os.path.join(currentPath, './config.yaml')

interpreter.extend_config(config_path=config_path)

message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)