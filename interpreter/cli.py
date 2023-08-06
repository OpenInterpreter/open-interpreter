import argparse

def cli(interpreter):
  """
  Takes an instance of interpreter.
  Modifies it according to command line flags, then runs chat.
  """

  parser = argparse.ArgumentParser(description='Chat with Open Interpreter.')
  parser.add_argument('-y',
                      '--yes',
                      action='store_true',
                      help='execute code without user confirmation')
  parser.add_argument('-l',
                      '--local',
                      action='store_true',
                      help='run fully local with llama-2')
  args = parser.parse_args()

  if args.yes:
    interpreter.auto_run = True

  if args.local:
    interpreter.local = True

  # Now run the chat method
  interpreter.chat()
