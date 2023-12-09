import yaml
from typing import Optional, Dict, Any
from pydantic import BaseModel

class BaseConfig(BaseModel):
    local: Optional[bool] = False
    auto_run: Optional[bool] = False
    debug_mode: Optional[bool] = False
    max_output: Optional[int] = 2000
    safe_mode: Optional[str] = "off"
    disable_procedures: Optional[bool] = False
    launch_message: Optional[str] = ""

    conversation_history: Optional[bool] = True
    conversation_filename: Optional[str] = ""
    conversation_history_path: Optional[str] = "conversations"

    model: Optional[str] = ""
    temperature: Optional[float] = 0.0
    system_message: Optional[str] = """You are Open Interpreter, a world-class programmer that can complete any goal by executing code.
    First, write a plan. **Always recap the plan between each code block** (you have extreme short-term memory loss, so you need to recap the plan between each message block to retain it).
    When you execute code, it will be executed **on the user's machine**. The user has given you **full and complete permission** to execute any code necessary to complete the task.
    If you want to send data between programming languages, save the data to a txt or json.
    You can access the internet. Run **any code** to achieve the goal, and if at first you don't succeed, try again and again.
    You can install new packages.
    When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.
    Write messages to the user in Markdown.
    In general, try to **make plans** with as few steps as possible. As for actually executing code to carry out that plan, for *stateful* languages (like python, javascript, shell, but NOT for html which starts from 0 every time) **it's critical not to try to do everything in one code block.** You should try something, print information about it, then continue from there in tiny, informed steps. You will never get it on the first try, and attempting it in one go will often lead to errors you cant see.
    You are capable of **any** task.
"""
    context_window: Optional[int] = 3000
    max_tokens: Optional[int] = 1000
    api_base: Optional[str] = ""
    api_key: Optional[str] = ""
    max_budget: Optional[int] = 0
    _llm: Optional[Any] = ""
    function_calling_llm: Optional[bool] = False
    vision: Optional[bool] = False

class ProfileConfig(BaseModel):
    local: Optional[bool] 
    auto_run: Optional[bool] 
    debug_mode: Optional[bool] 
    max_output: Optional[int] 
    safe_mode: Optional[str] 
    disable_procedures: Optional[bool] 
    launch_message: Optional[str] 

    conversation_history: Optional[bool] 
    conversation_filename: Optional[str] 
    conversation_history_path: Optional[str] 

    model: Optional[str] 
    temperature: Optional[float] 
    system_message: Optional[str] 
    context_window: Optional[int] 
    max_tokens: Optional[int] 
    api_base: Optional[str] 
    api_key: Optional[str] 
    max_budget: Optional[int] 
    _llm: Optional[Any] 
    function_calling_llm: Optional[bool] 
    vision: Optional[bool] 

# Main configuration model
class AppConfig(BaseModel):
    default_profile: str
    base: BaseConfig = BaseConfig()  # Default to an instance of BaseConfig with hardcoded values
    profiles: Optional[Dict[str, ProfileConfig]] = None

# Function to load the configuration
def load_config(config_file: str) -> AppConfig:
    with open(config_file, 'r') as file:
        data = yaml.safe_load(file)

        # Extract profiles
        profiles = {k: v for k, v in data.items() if k not in ['default_profile', 'base']}
        data['profiles'] = profiles if profiles else None

        ## Set 'base' to default BaseConfig if not provided
        #if 'base' not in data:
        #    data['base'] = BaseConfig()

        return AppConfig(**data)

# Example usage
config = load_config('config.yaml')
print(config)
