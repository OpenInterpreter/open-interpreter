import argparse
import inquirer
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def cli(interpreter):
  """
  Takes an instance of interpreter.
  Modifies it according to command line flags, then runs chat.
  """

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
  parser.add_argument('-d',
                      '--debug',
                      action='store_true',
                      default=DEBUG,
                      help='prints extra information')
  parser.add_argument('--use-azure',
                      action='store_true',
                      default=USE_AZURE,
                      help='use Azure OpenAI Services')
  args = parser.parse_args()

  # Modify interpreter according to command line flags
  if args.yes:
    interpreter.auto_run = True
  if args.fast:
    interpreter.model = "gpt-3.5-turbo"
  if args.local:
    interpreter.local = True
  if args.debug:
    interpreter.debug_mode = True
  if args.use_azure:
    interpreter.use_azure = True
    interpreter.local = False

  # Run the chat method
  interpreter.chat()
