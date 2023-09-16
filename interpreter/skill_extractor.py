import os
import inquirer
from rich import print
from rich.markdown import Markdown
from rich.table import Table
from .code_block import CodeBlock
import json


skill_extractor_prompt = """Extract one skill object from a conversation history, which is a list of messages.
Follow the guidelines below:
1. Only extract the properties mentioned in the 'extract_formmated_skill' function
"""

skill_extractor_function_schema = {
    "name": "extract_formmated_skill",
    "description": "a function that extracts a skill from a conversation history",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "the name of the skill to be extracted, snake_case, should be same with the function name"
            },
            "skill_description": {
                "type": "string",
                "description": "the description of the skill to be extracted, try to summarize the function in no more than 6 sentences."
            },
            "skill_dependencies": {
                "type": "array",
                "description": "a list of dependencies that the skill requires to run, normally packages, not language specific. for python, it should be the packages in requirements.txt",
                "items": {
                    "type": "string"
                }
            },
            "skill_parameters": {
                "type": "array",
                "description": "a list of parameters that the skill requires to run use json schema",
                "items": {
                    "type": "object",
                    "properties": {
                        "param_name": {
                            "type": "string",
                            "description": "the name of the parameter"
                        },
                        "param_type": {
                            "type": "string",
                            "description": "the type of the parameter, only support string, integer, float, boolean, array, object"
                        },
                        "param_description": {
                            "type": "string",
                            "description": "the description of the parameter"
                        },
                        "param_required": {
                            "type": "boolean",
                            "description": "whether the parameter is required"
                        },
                        "param_default": {
                            "type": "string",
                            "description": "the default value of the parameter, it depends on the type of the parameter"
                        }
                    },
                    "required": ["param_name", "param_type", "param_description", "param_required", "param_default"]
                },
            },
            "skill_usage_example": {
                "type": "string",
                "description": "an example of how to use the skill"
            },
            "skill_return": {
                "type": "object",
                "description": "the return value of the skill",
                "properties": {
                    "return_name": {
                        "type": "string",
                        "description": "the name of the return value"
                    },
                    "return_type": {
                        "type": "string",
                        "description": "the type of the return value, only support string, integer, float, boolean, array, object"
                    },
                    "return_description": {
                        "type": "string",
                        "description": "the description of the return value"
                    }
                }
            },
            "skill_tags": {
                "type": "array",
                "description": "a list of tags that describe the skill",
                "items": {
                    "type": "string"
                }
            },
            "skill_program_language": {
                "type": "string",
                "description": "the programming language that the skill is written in",
                "enum": ["python", "R", "shell", "javascript", "applescript", "html"]
            },
            "skill_code": {
                "type": "string",
                "description": "the code of the skill, only one function is allowed"
            }
        }
    }
}

default_skill_lib_path = os.path.expanduser("~") + "/.cache/open_interpreter/skill_library/"


def save_skill_to_library(skill_json, save_path):
  if save_path == "":
    save_path = default_skill_lib_path + skill_json.get("skill_name", "no_skill_name_yet") + ".json"
  if not os.path.exists(os.path.dirname(save_path)):
    os.makedirs(os.path.dirname(save_path))
  with open(save_path, 'w') as f:
    json.dump(skill_json, f, indent=2)
  return save_path


def get_skill_from_library():
    """
    list all the skills in the skill library
    :return: a list of skills
    """
    current_skill_list = []
    for filename in os.listdir(default_skill_lib_path):
      if filename.endswith(".json"):
        current_skill_list.append(filename)
    print(Markdown("Current skill list:"))
    if len(current_skill_list) == 0:
      print(Markdown("No skill in the library, please add some skills first"))
      return ""
    questions = [inquirer.List('selected_skill', message="", choices=current_skill_list)]
    answers = inquirer.prompt(questions)
    return os.path.join(default_skill_lib_path, answers['selected_skill'])


def print_format_skill(skill_obj):
  # print in markdown format
  # 使用rich的Table来重写打印
  return_str = ""
  table = Table(title="Skill Details", header_style="bold magenta", show_lines=True)

  table.add_column("Name", style="cyan", no_wrap=True)
  table.add_column("Value", style="magenta")
  table.add_row("Name", skill_obj['skill_name'])
  table.add_row("Description", skill_obj['skill_description'])
  table.add_row("Dependencies", ', '.join(skill_obj['skill_dependencies']))
  table.add_row("Tags", ', '.join(skill_obj['skill_tags']))
  table.add_row("Return", skill_obj['skill_return']['return_name'])
  table.add_row("Usage Example", skill_obj.get('skill_usage_example', 'N/A'))
  table.add_row("Program Language", skill_obj.get('skill_program_language', 'N/A'))
  
  print(table)
  return_str += str(table) + "\n"

  table = Table(title="Parameters", header_style="bold magenta", show_lines=True)
  table.add_column("Parameters", style="cyan", no_wrap=True)
  table.add_column("Type", style="magenta")
  table.add_column("Description", style="green")
  table.add_column("Required", style="red")
  table.add_column("Default", style="blue")
  
  for param in skill_obj['skill_parameters']:
    table.add_row(param.get('param_name', 'N/A'), param.get('param_type', 'N/A'), param.get('param_description', 'N/A'), str(param.get('param_required', 'N/A')), param.get('param_default', 'N/A'))
  
  print(table)
  return_str += str(table) + "\n"

  active_block = CodeBlock()
  active_block.language = skill_obj.get('skill_program_language', 'text').lower()
  active_block.code = skill_obj.get('skill_code', '')

  table = Table(title="Metadata", header_style="bold magenta", show_lines=True)
  table.add_column("Metadata", style="cyan", no_wrap=True)
  table.add_column("Value", style="magenta")
  table.add_row("Created At", skill_obj['skill_metadata']['created_at'])
  table.add_row("Author", skill_obj['skill_metadata']['author'])
  table.add_row("Updated At", skill_obj['skill_metadata']['updated_at'])
  table.add_row("Usage Count", str(skill_obj['skill_metadata']['usage_count']))
  
  print(table)

  return active_block, return_str


# TODO: handle test writer agent
# answer = inquirer.prompt("Do you want to write a test case for this skill? (y/n)")
# if answer == "y":
#   print(Markdown("> Please write a test case for this skill"))
#   self.messages.append({
#     "role": "user", 
#     "content": (
#     "Please write a test case for this skill"
#     "Firstly, write a `create_testcase` function and output input parameters and expected output"
#     "Secondly, write a test function to test the skill. the name should be `test_{skill_name}`"
#     "the input parameters are `create_testcase` function and the skill function"
#     "the output is the test result. Normally it should be `True` or `False`"
#     "if there are exceptions, please return the exception message"
#     )
#   })
#   self.respond()
# else:
#   print(Markdown("> No test case is written for this skill"))