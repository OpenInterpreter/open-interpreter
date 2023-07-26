import argparse
import interpreter

def cli():
    parser = argparse.ArgumentParser(description='Chat with Open Interpreter.')
    parser.add_argument('--no_confirm', action='store_true', help='Execute code without user confirmation')
    args = parser.parse_args()

    # Set safe_mode on the imported interpreter instance
    if args.no_confirm:
      interpreter.no_confirm = True
    else:
      print("\nGenerated code will require confirmation before executing. Run `interpreter --no_confirm` for instant code execution.\n")
    
    # Now run the chat method
    interpreter.chat()