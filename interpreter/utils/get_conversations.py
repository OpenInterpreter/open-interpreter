import os
import appdirs

# Using appdirs to determine user-specific config path
config_dir = appdirs.user_config_dir("Open Interpreter")

def get_conversations():
    conversations_dir = os.path.join(config_dir, "conversations")
    json_files = [f for f in os.listdir(conversations_dir) if f.endswith('.json')]
    return json_files