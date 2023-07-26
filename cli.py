import argparse
import interpreter

def main():
    parser = argparse.ArgumentParser(description='Chat with Open Interpreter.')
    parser.add_argument('--auto_exec', action='store_true', help='Enable auto execution')
    args = parser.parse_args()

    # Set safe_mode on the imported interpreter instance
    if args.auto_exec:
      print("\nYou are in auto execution mode. Generated code will execute without confirmation.\n")
      interpreter.auto_exec = True
    
    # Now run the chat method
    interpreter.chat()

if __name__ == "__main__":
    main()