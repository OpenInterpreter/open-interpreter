"""
Right off the bat, to any contributors (a message from Killian):

First of all, THANK YOU. Open Interpreter is ALIVE, ALL OVER THE WORLD because of YOU.

While this project is rapidly growing, I've decided it's best for us to allow some technical debt.

The code here has duplication. It has imports in weird places. It has been spaghettified to add features more quickly.

In my opinion **this is critical** to keep up with the pace of demand for this project.

At the same time, I plan on pushing a significant re-factor of `interpreter.py` and `code_interpreter.py` ~ September 16th.

After the re-factor, Open Interpreter's source code will be much simpler, and much more fun to dive into.

Especially if you have ideas and **EXCITEMENT** about the future of this project, chat with me on discord: https://discord.gg/6p3fD6rBVm

- killian
"""

import argparse
import json
import os
from dotenv import load_dotenv
import requests
from packaging import version
import pkg_resources
from rich import print as rprint
from rich.markdown import Markdown
import inquirer

from interpreter.models.prompt_format import DEFAULT_PROMPT_FORMATS, PromptFormat

# Load .env file
load_dotenv()

def check_for_update():
    # Fetch the latest version from the PyPI API
    response = requests.get(f'https://pypi.org/pypi/open-interpreter/json')
    latest_version = response.json()['info']['version']

    # Get the current version using pkg_resources
    current_version = pkg_resources.get_distribution("open-interpreter").version

    return version.parse(latest_version) > version.parse(current_version)

def cli(interpreter):
  """
  Takes an instance of interpreter.
  Modifies it according to command line flags, then runs chat.
  """

  try:
    if check_for_update():
      print("A new version is available. Please run 'pip install --upgrade open-interpreter'.")
  except:
    # Fine if this fails
    pass

  # Load values from .env file with the new names
  AUTO_RUN = os.getenv('INTERPRETER_CLI_AUTO_RUN', 'False') == 'True'
  FAST_MODE = os.getenv('INTERPRETER_CLI_FAST_MODE', 'False') == 'True'
  LOCAL_RUN = os.getenv('INTERPRETER_CLI_LOCAL_RUN', 'False') == 'True'
  DEBUG = os.getenv('INTERPRETER_CLI_DEBUG', 'False') == 'True'
  USE_AZURE = os.getenv('INTERPRETER_CLI_USE_AZURE', 'False') == 'True'

  # Setup CLI
  parser = argparse.ArgumentParser(description='Chat with Open Interpreter.')
  
  parser.add_argument('-y',
                      '--yes',
                      action='store_true',
                      default=AUTO_RUN,
                      help='execute code without user confirmation')
  parser.add_argument('-f',
                      '--fast',
                      action='store_true',
                      default=FAST_MODE,
                      help='use gpt-3.5-turbo instead of gpt-4')
  parser.add_argument('-l',
                      '--local',
                      action='store_true',
                      default=LOCAL_RUN,
                      help='run fully local with code-llama')
  parser.add_argument('-p',
                      '--prompt_format',
                      type=str,
                      help='prompt format json file',
                      default=None,
                      required=False)
  parser.add_argument(
                      '--falcon',
                      action='store_true',
                      default=False,
                      help='run fully local with falcon-40b')
  parser.add_argument('-d',
                      '--debug',
                      action='store_true',
                      default=DEBUG,
                      help='prints extra information')
  
  parser.add_argument('--model',
                      type=str,
                      help='model name (for OpenAI compatible APIs) or HuggingFace repo',
                      default="",
                      required=False)
  
  parser.add_argument('--max_tokens',
                      type=int,
                      help='max tokens generated (for locally run models)')
  parser.add_argument('--context_window',
                      type=int,
                      help='context window in tokens (for locally run models)')
  
  parser.add_argument('--api_base',
                      type=str,
                      help='change your api_base to any OpenAI compatible api',
                      default="",
                      required=False)
  
  parser.add_argument('--use-azure',
                      action='store_true',
                      default=USE_AZURE,
                      help='use Azure OpenAI Services')
  
  parser.add_argument('--version',
                      action='store_true',
                      help='display current Open Interpreter version')

  args = parser.parse_args()


  if args.version:
    print("Open Interpreter", pkg_resources.get_distribution("open-interpreter").version)
    return

  if args.max_tokens:
    interpreter.max_tokens = args.max_tokens
  if args.context_window:
    interpreter.context_window = args.context_window

  # Modify interpreter according to command line flags
  if args.yes:
    interpreter.auto_run = True
  if args.fast:
    interpreter.model = "gpt-3.5-turbo"
  if args.local and not args.falcon:



    # Temporarily, for backwards (behavioral) compatability, we've moved this part of llama_2.py here.
    # This way, when folks hit interpreter --local, they get the same experience as before.
    
    rprint('', Markdown("**Open Interpreter** will use `Code Llama` for local execution. Use your arrow keys to set up the model."), '')
        
    models = {
        '7B': 'TheBloke/CodeLlama-7B-Instruct-GGUF',
        '13B': 'TheBloke/CodeLlama-13B-Instruct-GGUF',
        '34B': 'TheBloke/CodeLlama-34B-Instruct-GGUF'
    }
    
    parameter_choices = list(models.keys())
    questions = [inquirer.List('param', message="Parameter count (smaller is faster, larger is more capable)", choices=parameter_choices)]
    answers = inquirer.prompt(questions)
    chosen_param = answers['param']

    # THIS is more in line with the future. You just say the model you want by name:
    interpreter.model = models[chosen_param]
    interpreter.local = True

    if not args.prompt_format:
      print('', Markdown("**Open Interpreter** will use a default prompt format. Use your arrow keys to set up the model."), '')

      prompt_format_choices = [
        'falcon',
        'llama',
        'wizard-coder',
        'phindv2',
        'custom'
      ]

      questions = [inquirer.List('param', message="Prompt format", choices=prompt_format_choices)]
      answers = inquirer.prompt(questions)
      chosen_format = answers['param']
      if chosen_format == 'custom':
        while True:
          # ask the user for a prompt json file
          prompt_json_path = input("Path to prompt json file: ")
          if os.path.exists(prompt_json_path):
            with open(prompt_json_path, 'r') as f:
              try:
                interpreter.prompt_format = PromptFormat(json.load(f))
                break
              except:
                print("Invalid Prompt Format JSON file. Please try again.")
            break
          else:
            print("Invalid path. Please try again.")
      else:
        interpreter.prompt_format = DEFAULT_PROMPT_FORMATS[chosen_format]
    else:
      with open(args.prompt_format, 'r') as f:
        try:
          interpreter.prompt_format = PromptFormat(json.load(f))
        except Exception as e:
          print("Invalid Prompt Format JSON file. Please try again.\n", e)
          exit(1)
  
  if args.debug:
    interpreter.debug_mode = True
  if args.use_azure:
    interpreter.use_azure = True
    interpreter.local = False


  if args.model != "":
    interpreter.model = args.model

    # "/" in there means it's a HF repo we're going to run locally:
    if "/" in interpreter.model:
      interpreter.local = True

      if args.prompt_format:
        with open(args.prompt_format, 'r') as f:
          try:
            interpreter.prompt_format = PromptFormat(json.load(f))
          except Exception as e:
            print("Invalid Prompt Format JSON file. Please try again.\n", e)
            exit(1)

  if args.api_base:
    interpreter.api_base = args.api_base

  if args.falcon or args.model == "tiiuae/falcon-180B": # because i tweeted <-this by accident lol, we actually need TheBloke's quantized version of Falcon:

    # Temporarily, for backwards (behavioral) compatability, we've moved this part of llama_2.py here.
    # This way, when folks hit interpreter --falcon, they get the same experience as --local.
    
    rprint('', Markdown("**Open Interpreter** will use `Falcon` for local execution. Use your arrow keys to set up the model."), '')
        
    models = {
        '7B': 'TheBloke/CodeLlama-7B-Instruct-GGUF',
        '40B': 'YokaiKoibito/falcon-40b-GGUF',
        '180B': 'TheBloke/Falcon-180B-Chat-GGUF'
    }
    
    parameter_choices = list(models.keys())
    questions = [inquirer.List('param', message="Parameter count (smaller is faster, larger is more capable)", choices=parameter_choices)]
    answers = inquirer.prompt(questions)
    chosen_param = answers['param']

    if chosen_param == "180B":
      rprint(Markdown("> **WARNING:** To run `Falcon-180B` we recommend at least `100GB` of RAM."))

    # THIS is more in line with the future. You just say the model you want by name:
    interpreter.model = models[chosen_param]
    interpreter.local = True
    interpreter.prompt_format = DEFAULT_PROMPT_FORMATS['falcon']


  # ask the user if they want to pass a custom prompt format if we are in local mode
  if interpreter.local and interpreter.prompt_format is None:
    rprint(Markdown("**Open Interpreter** will use a default prompt format (llama2 chat). Use your arrow keys to select an alternative."))

    prompt_format_choices = [
      'falcon',
      'llama',
      'wizard-coder',
      'phindv2',
      'custom'
    ]

    questions = [inquirer.List('param', message="Prompt format", choices=prompt_format_choices)]
    answers = inquirer.prompt(questions)
    chosen_format = answers['param']
    if chosen_format == 'custom':
      while True:
        # ask the user for a prompt json file
        prompt_json_path = input("Path to prompt json file: ")
        if os.path.exists(prompt_json_path):
          with open(prompt_json_path, 'r') as f:
            try:
              interpreter.prompt_format = PromptFormat(json.load(f))
              break
            except Exception as e:
              print("Invalid Prompt Format JSON file. Please try again.\n", e)
          break
        else:
          print("Invalid path. Please try again.")
    else:
      interpreter.prompt_format = DEFAULT_PROMPT_FORMATS[chosen_format]

  # Run the chat method
  interpreter.chat()
