import argparse
import inquirer

def cli(interpreter):
  """
  Takes an instance of interpreter.
  Modifies it according to command line flags, then runs chat.
  """

  # Setup CLI
  parser = argparse.ArgumentParser(description='Chat with Open Interpreter.')
  
  parser.add_argument('-y',
                      '--yes',
                      action='store_true',
                      help='execute code without user confirmation')
  parser.add_argument('-f',
                      '--fast',
                      action='store_true',
                      help='use gpt-3.5-turbo instead of gpt-4')
  parser.add_argument('-l',
                      '--local',
                      action='store_true',
                      help='run fully local with code-llama')
  parser.add_argument('-d',
                      '--debug',
                      action='store_true',
                      help='prints extra information')
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

  # Run the chat method
  interpreter.chat()
